"""
fillForm.py
-----------
Handles filling of traditional HTML forms on job application pages.
Works alongside NaukriApplier.py — call fill_classic_form() when
a classic form (not chatbot) is detected after clicking Apply.

Usage inside NaukriApplier.apply_to_job():
    from fillForm import FormFiller
    filler = FormFiller(llm=self.llm, resume_path="./data/resume.pdf")
    success = await filler.fill_classic_form(page)
"""

import asyncio
import logging
import random
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import Page

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Candidate profile — kept in sync with NaukriApplier.answer_prompt  #
# ------------------------------------------------------------------ #

CANDIDATE_PROFILE = """
Name: Nitesh Kumar
Location: Bengaluru (open to relocate anywhere in India)
Total experience: 3 years
Skills: Python, GenAI, LLMs, RAG, LangChain, Machine Learning, AWS Cloud
Current CTC: 10 LPA
Expected CTC: 15 LPA
Notice period: 30 days
Email: (use whatever is in the form context)
Phone: (use whatever is in the form context)
"""


# ------------------------------------------------------------------ #

class FormFiller:

    def __init__(self, llm, resume_path: str = "./data/resume.pdf"):
        self.llm         = llm
        self.resume_path = Path(resume_path)

        self.field_prompt = PromptTemplate(
            input_variables=["profile", "label", "field_type", "options"],
            template="""
You are filling a job application form on behalf of the candidate below.

Candidate profile:
{profile}

Form field:
- Label / placeholder: {label}
- Field type: {field_type}
- Available options (for select / radio): {options}

Rules:
- Return ONLY the bare value — no explanation, no punctuation, no quotes.
- For select/radio, return EXACTLY one of the available options as written.
- For checkbox: return "yes" or "no".
- For file upload fields: return "UPLOAD_RESUME".
- If the answer cannot be found in the profile, return "SKIP".
- Keep text answers short and factual (≤ 8 words for open text).

What value should be entered?
"""
        )

        self.field_chain = self.field_prompt | self.llm | StrOutputParser()

    # ------------------------------------------------------------------ #
    # Human-like interactions                                              #
    # ------------------------------------------------------------------ #

    async def _human_type(self, locator, text: str):
        """Type character by character with randomised delays."""
        await locator.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))
        for char in text:
            await locator.type(char, delay=random.randint(45, 155))
        await asyncio.sleep(random.uniform(0.1, 0.35))

    async def _human_click(self, page: Page, locator):
        """Move mouse naturally to element then click."""
        try:
            box = await locator.bounding_box()
            if box:
                x = box["x"] + box["width"]  * random.uniform(0.25, 0.75)
                y = box["y"] + box["height"] * random.uniform(0.25, 0.75)
                await page.mouse.move(x, y, steps=random.randint(8, 22))
                await asyncio.sleep(random.uniform(0.08, 0.30))
                await page.mouse.click(x, y)
                return
        except Exception:
            pass
        await locator.click()

    # ------------------------------------------------------------------ #
    # LLM decision                                                         #
    # ------------------------------------------------------------------ #

    async def _ask_llm(
        self,
        label: str,
        field_type: str,
        options: list[str] | None = None,
    ) -> str:
        options_str = ", ".join(options) if options else "N/A"
        try:
            result = await self.field_chain.ainvoke({
                "profile":     CANDIDATE_PROFILE,
                "label":       label,
                "field_type":  field_type,
                "options":     options_str,
            })
            return result.strip()
        except Exception as e:
            logger.warning(f"LLM failed for '{label}': {e}")
            return "SKIP"

    # ------------------------------------------------------------------ #
    # CAPTCHA pause (human solves it)                                      #
    # ------------------------------------------------------------------ #

    async def wait_for_captcha(self, page: Page) -> bool:
        """
        Detect common CAPTCHA iframes/elements and pause for manual solving.
        Automated CAPTCHA bypass is intentionally NOT implemented.
        """
        selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            ".g-recaptcha",
            "#captcha",
            "[class*='captcha']",
            "[id*='captcha']",
        ]
        for sel in selectors:
            try:
                if await page.locator(sel).count() > 0:
                    print(
                        "\n⚠️  CAPTCHA detected. Please solve it in the browser, "
                        "then press ENTER here to continue..."
                    )
                    input()
                    return True
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------ #
    # HTML parsing                                                         #
    # ------------------------------------------------------------------ #

    def _resolve_label(self, soup, tag) -> str:
        """Find the human-readable label for an input element."""
        tag_id = tag.get("id")
        if tag_id:
            lbl = soup.find("label", {"for": tag_id})
            if lbl:
                return lbl.get_text(strip=True)

        # Walk up to a wrapping <label>
        parent = tag.parent
        for _ in range(4):
            if parent and parent.name == "label":
                return parent.get_text(separator=" ", strip=True)
            if parent:
                parent = parent.parent

        return tag.get("aria-label", tag.get("placeholder", tag.get("name", "")))

    def _css_selector(self, tag) -> str:
        """Build a reliable CSS selector, preferring id > name > placeholder."""
        if tag.get("id"):
            return f"#{tag['id']}"
        if tag.get("name"):
            return f"[name='{tag['name']}']"
        if tag.get("placeholder"):
            return f"[placeholder='{tag['placeholder']}']"
        return tag.name

    def _extract_fields(self, html: str) -> list[dict]:
        """
        Parse all fillable form fields from page HTML.
        Returns a list of field descriptors.
        """
        soup   = BeautifulSoup(html, "html.parser")
        fields = []

        # ── text / email / tel / number / textarea ──
        for tag in soup.find_all(["input", "textarea"]):
            t = tag.get("type", "text").lower()
            if t in ("hidden", "submit", "button", "image", "reset", "file"):
                continue
            label = self._resolve_label(soup, tag)
            fields.append({
                "kind":       "text",
                "input_type": t,
                "label":      label or tag.get("name", ""),
                "selector":   self._css_selector(tag),
                "required":   tag.has_attr("required"),
            })

        # ── <select> dropdowns ──
        for tag in soup.find_all("select"):
            label   = self._resolve_label(soup, tag)
            options = [
                o.get_text(strip=True)
                for o in tag.find_all("option")
                if o.get("value", "").strip()
            ]
            fields.append({
                "kind":     "select",
                "label":    label or tag.get("name", ""),
                "options":  options,
                "selector": self._css_selector(tag),
                "required": tag.has_attr("required"),
            })

        # ── radio groups ──
        seen_names: set[str] = set()
        for tag in soup.find_all("input", {"type": "radio"}):
            name = tag.get("name", "")
            if name in seen_names:
                continue
            seen_names.add(name)
            label   = self._resolve_label(soup, tag)
            options = [
                r.get("value", "")
                for r in soup.find_all("input", {"type": "radio", "name": name})
            ]
            fields.append({
                "kind":     "radio",
                "name":     name,
                "label":    label or name,
                "options":  options,
                "required": tag.has_attr("required"),
            })

        # ── file upload inputs ──
        for tag in soup.find_all("input", {"type": "file"}):
            label = self._resolve_label(soup, tag)
            fields.append({
                "kind":     "file",
                "label":    label or tag.get("name", "resume"),
                "selector": self._css_selector(tag),
                "required": tag.has_attr("required"),
            })

        return fields

    # ------------------------------------------------------------------ #
    # Per-field handlers                                                   #
    # ------------------------------------------------------------------ #

    async def _fill_text(self, page: Page, field: dict, value: str):
        sel     = field["selector"]
        locator = page.locator(sel).first
        try:
            await self._human_click(page, locator)
            # Clear existing value
            await locator.triple_click()
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.08)
            await page.keyboard.press("Delete")
            await self._human_type(locator, value)
            logger.info(f"  [TEXT ] '{field['label']}' → '{value[:60]}'")
        except Exception as e:
            logger.warning(f"  [TEXT ] fill failed '{field['label']}': {e}")

    async def _fill_select(self, page: Page, field: dict, value: str):
        sel     = field["selector"]
        locator = page.locator(sel).first
        try:
            await self._human_click(page, locator)
            await locator.select_option(label=value)
            logger.info(f"  [SELECT] '{field['label']}' → '{value}'")
        except Exception as e:
            # Try by value if label fails
            try:
                await locator.select_option(value=value)
                logger.info(f"  [SELECT] '{field['label']}' → '{value}' (by value)")
            except Exception:
                logger.warning(f"  [SELECT] failed '{field['label']}': {e}")

    async def _fill_radio(self, page: Page, field: dict, value: str):
        name = field["name"]
        try:
            # Try to click the radio whose value matches
            radio = page.locator(f"input[type='radio'][name='{name}'][value='{value}']").first
            if await radio.count() > 0:
                await self._human_click(page, radio)
                logger.info(f"  [RADIO] '{field['label']}' → '{value}'")
                return
            # Fallback: click first radio in the group
            first = page.locator(f"input[type='radio'][name='{name}']").first
            if await first.count() > 0:
                await self._human_click(page, first)
                logger.info(f"  [RADIO] '{field['label']}' → first option (fallback)")
        except Exception as e:
            logger.warning(f"  [RADIO] failed '{field['label']}': {e}")

    async def _fill_file(self, page: Page, field: dict):
        sel = field["selector"]
        try:
            await page.locator(sel).first.set_input_files(str(self.resume_path))
            logger.info(f"  [FILE ] '{field['label']}' → resume uploaded ✓")
        except Exception as e:
            logger.warning(f"  [FILE ] upload failed '{field['label']}': {e}")

    # ------------------------------------------------------------------ #
    # Main entry point                                                     #
    # ------------------------------------------------------------------ #

    async def fill_classic_form(self, page: Page) -> bool:
        """
        Detect and fill all form fields on the current page.

        Steps:
          1. CAPTCHA check — pauses for human if detected
          2. Parse HTML for all form fields
          3. Ask LLM for each field value
          4. Fill with human-like mouse + typing behaviour
          5. Final CAPTCHA check before returning

        Returns True if at least one field was filled, False otherwise.
        """
        await self.wait_for_captcha(page)

        html   = await page.content()
        fields = self._extract_fields(html)

        if not fields:
            logger.info("fill_classic_form: no form fields detected on page.")
            return False

        logger.info(f"fill_classic_form: {len(fields)} fields detected.")
        filled_count = 0

        for field in fields:
            await asyncio.sleep(random.uniform(0.4, 1.1))   # human pacing

            kind  = field["kind"]
            label = field["label"]

            # ── FILE UPLOAD ──
            if kind == "file":
                if self.resume_path.exists():
                    await self._fill_file(page, field)
                    filled_count += 1
                else:
                    logger.warning(f"  [FILE ] resume not found: {self.resume_path}")
                continue

            # ── SELECT ──
            if kind == "select":
                options = field.get("options", [])
                value   = await self._ask_llm(label, "select", options)

                if value == "SKIP" or value not in options:
                    if not field["required"]:
                        logger.info(f"  [SELECT] '{label}' skipped (optional, no match)")
                        continue
                    # Required but LLM missed → pick first non-empty option
                    value = options[0] if options else None
                    if not value:
                        continue
                    logger.info(f"  [SELECT] '{label}' defaulting to first option: '{value}'")

                await self._fill_select(page, field, value)
                filled_count += 1
                continue

            # ── RADIO ──
            if kind == "radio":
                options = field.get("options", [])
                value   = await self._ask_llm(label, "radio", options)
                if value == "SKIP":
                    if not field["required"]:
                        continue
                    value = options[0] if options else ""
                await self._fill_radio(page, field, value)
                filled_count += 1
                continue

            # ── TEXT / EMAIL / TEL / TEXTAREA ──
            value = await self._ask_llm(label, field.get("input_type", "text"))

            if value == "SKIP":
                if not field["required"]:
                    logger.info(f"  [TEXT ] '{label}' skipped (optional)")
                    continue
                # Required but no data — ask terminal user (last resort)
                value = input(f"\n[INPUT NEEDED] Enter value for required field '{label}': ").strip()
                if not value:
                    continue

            await self._fill_text(page, field, value)
            filled_count += 1

        logger.info(f"fill_classic_form: filled {filled_count}/{len(fields)} fields.")

        # Final CAPTCHA check
        await self.wait_for_captcha(page)

        return filled_count > 0

    # ------------------------------------------------------------------ #
    # Submit helper (mirrors NaukriApplier's approach)                    #
    # ------------------------------------------------------------------ #

    async def submit_form(self, page: Page) -> bool:
        """
        Find and click the form submit button.
        Tries several selectors in order of specificity.
        Returns True if a button was clicked.
        """
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "a:has-text('Apply Now')",
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    logger.info(f"Submitting via: {sel}")
                    await self._human_click(page, btn)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    logger.info("Form submitted ✓")
                    return True
            except Exception:
                continue
        logger.warning("No submit button found.")
        return False