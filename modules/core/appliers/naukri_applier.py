import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import async_playwright
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from modules.core.config.settings import config, create_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BLOCKED_COMPANIES = [
    "infosys", "wipro", "tcs", "tech mahindra", "hcl", "cognizant",
]

REASON_STUCK            = "stuck_on_question"
REASON_TIMEOUT          = "page_timeout"
REASON_DNS              = "dns_error"
REASON_NO_APPLY_BTN     = "no_apply_button"
REASON_NOTHING_HANDLED  = "nothing_handled_after_click"
REASON_EXTERNAL         = "external_apply"
REASON_ALREADY_APPLIED  = "already_applied"
REASON_UNKNOWN          = "unknown_error"


def load_jobs_from_file(filepath: str) -> list[dict]:
    jobs = []
    current_job = {}
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line.startswith("Title:"):
            current_job["title"] = line.replace("Title:", "").strip()
        elif line.startswith("Company:"):
            current_job["company"] = line.replace("Company:", "").strip()
        elif line.startswith("Location:"):
            current_job["location"] = line.replace("Location:", "").strip()
        elif line.startswith("Experience:"):
            current_job["experience"] = line.replace("Experience:", "").strip()
        elif line.startswith("Apply Link:"):
            current_job["link"] = line.replace("Apply Link:", "").strip()
        elif line.startswith("=================================") and current_job.get("link"):
            jobs.append(current_job)
            current_job = {}
    return jobs


class NaukriApplier:

    def __init__(self, email: str, password: str):
        self.email         = email
        self.password      = password
        self.login_url     = "https://www.naukri.com/nlogin/login"
        self.applied_file  = config.JOBS_DIR / "applied_jobs.txt"
        self.failed_file   = config.JOBS_DIR / "failed_jobs.txt"
        self.external_file = config.JOBS_DIR / "external_jobs.txt"
        self.skipped_file  = config.JOBS_DIR / "skipped_jobs.txt"

        self.llm = create_llm(temperature=0)

        self.answer_prompt = PromptTemplate(
            input_variables=["question"],
            template="""
You are filling out a job application chatbot for a software engineer.
Answer ONLY with a short direct value. No explanation. No punctuation.

Candidate profile:
- Name: Nitesh Kumar
- Location: Bengaluru (open to relocate anywhere in India)
- Total experience: 3 years
- Skills: Python, GenAI, LLMs, RAG, LangChain, Machine Learning, AWS Cloud
- Current CTC: 10 LPA
- Expected CTC: 15 LPA
- Notice period: 30 days

Rules:
- Yes/No questions                         → Yes or No
- Relocation / willing to relocate         → Yes
- Currently in [any city]?                 → Yes, willing to relocate
- Years of experience (any skill)          → 3
- Notice period (days)                     → 30
- Expected CTC (lakhs/LPA)                 → 15
- Current CTC (lakhs/LPA)                  → 10
- Skill rating 1-10                        → 8
- Percentage / proficiency                 → 80
- Location preference                      → Bengaluru
- Short open text                          → max 8 words

Question: {question}
Answer:"""
        )
        self.answer_chain = self.answer_prompt | self.llm | StrOutputParser()

    # ------------------------------------------------ #

    def is_blocked(self, company: str) -> bool:
        return any(b.lower() in company.lower() for b in BLOCKED_COMPANIES)

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^a-z0-9]", "_", name.lower())[:40]

    async def get_llm_answer(self, question: str) -> str:
        try:
            answer = await self.answer_chain.ainvoke({"question": question})
            return answer.strip()
        except Exception as e:
            logger.warning(f"LLM answer failed: {e}")
            return "Yes"

    # ------------------------------------------------ #

    async def login(self, page):
        logger.info("Logging in to Naukri...")
        await page.goto(self.login_url)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

        for sel in ["input#usernameField", "input[name='username']", "input[type='email']"]:
            try:
                await page.wait_for_selector(sel, timeout=4000)
                await page.fill(sel, self.email)
                logger.info(f"Email filled: {sel}")
                break
            except Exception:
                continue

        for sel in ["input#passwordField", "input[name='password']", "input[type='password']"]:
            try:
                await page.wait_for_selector(sel, timeout=4000)
                await page.fill(sel, self.password)
                logger.info(f"Password filled: {sel}")
                break
            except Exception:
                continue

        for sel in ["button[type='submit']", "button:has-text('Login')"]:
            try:
                await page.click(sel, timeout=4000)
                break
            except Exception:
                continue

        await page.wait_for_timeout(4000)
        logger.info(f"Logged in. URL: {page.url}")

    # ------------------------------------------------ #

    async def is_already_applied(self, page) -> bool:
        """
        Detect if this job was already applied to.
        Covers: button text, CSS classes, and page text indicators.
        """
        # Button/element based checks
        already_selectors = [
            "button.already-applied",
            ".applied-status",
            "button:has-text('Applied')",
            "button:has-text('Already Applied')",
            "span:has-text('Already Applied')",
            "div:has-text('Already Applied')",
            # Naukri sometimes shows a green tick with "Applied" text
            "span.applied",
            "div.applied",
            "label:has-text('Applied')",
        ]
        for sel in already_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    logger.info(f"Already applied detected via: {sel}")
                    return True
            except Exception:
                continue

        # Page text scan
        try:
            body_text = (await page.locator("body").inner_text()).lower()
            phrases = ["you have already applied", "already applied to this job", "application submitted"]
            for phrase in phrases:
                if phrase in body_text:
                    logger.info(f"Already applied detected via text: '{phrase}'")
                    return True
        except Exception:
            pass

        return False

    # ------------------------------------------------ #

    async def get_last_bot_question(self, page) -> str:
        """Extract latest question from chatbot."""
        try:
            spans = page.locator("li.botItem div.botMsg div span")
            count = await spans.count()
            for i in range(count - 1, -1, -1):
                text = (await spans.nth(i).inner_text()).strip()
                if (
                    text and len(text) > 10
                    and "thank you" not in text.lower()
                    and "kindly answer" not in text.lower()
                    and not text.lower().startswith("hi ")
                ):
                    return text
        except Exception as e:
            logger.warning(f"get_last_bot_question error: {e}")
        return ""

    # ------------------------------------------------ #

    async def type_into_contenteditable(self, page, text: str) -> bool:
        """Fill Naukri's contenteditable div input."""
        selectors = [
            "div.textArea[contenteditable='true']",
            "div[contenteditable='true'][data-placeholder]",
            "div[id^='userInput__']",
        ]
        for sel in selectors:
            try:
                inp = page.locator(sel)
                if await inp.count() > 0 and await inp.first.is_visible():
                    await inp.first.click()
                    await page.wait_for_timeout(200)
                    await inp.first.evaluate("el => el.innerText = ''")
                    await page.wait_for_timeout(100)
                    await inp.first.type(text, delay=50)
                    logger.info(f"Typed [{sel}]: {text}")
                    return True
            except Exception:
                continue
        return False

    async def send_message(self, page) -> bool:
        """Press Enter or click send button."""
        try:
            inp = page.locator("div.textArea[contenteditable='true']")
            if await inp.count() > 0 and await inp.first.is_visible():
                await inp.first.press("Enter")
                await page.wait_for_timeout(800)
                return True
        except Exception:
            pass
        for sel in ["span.chatBot-send", "span[class*='send']", "button[class*='send']"]:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    await page.wait_for_timeout(800)
                    return True
            except Exception:
                continue
        return False

    # ------------------------------------------------ #

    async def dump_chatbot_html(self, page, label: str):
        """
        Save chatbot container HTML to file for debugging.
        This helps identify exact selectors when chips/buttons aren't found.
        """
        try:
            html = await page.locator("div.chatbot_MessageContainer").inner_html()
            path = config.DEBUG_DIR / f"chatbot_debug_{label}.html"
            path.write_text(html, encoding="utf-8")
            logger.info(f"Chatbot HTML dumped → {path}")
        except Exception as e:
            logger.warning(f"HTML dump failed: {e}")

        # Also screenshot
        try:
            await page.screenshot(path=str(config.DEBUG_DIR / f"chatbot_debug_{label}.png"), full_page=False)
        except Exception:
            pass

    # ------------------------------------------------ #

    async def handle_chips(self, page, answer: str, label: str = "") -> bool:
        """
        Handle Yes/No and option chips.
        Naukri renders these as clickable elements — exact selectors vary.
        We try every possible pattern and also use JavaScript as fallback.
        """

        # ── Strategy 1: Known CSS selectors ──
        chip_selectors = [
            # Footer area chips
            "div.footerInputBoxWrapper button",
            "div.footerWrapper button",
            "div.footerWrapper span[class*='chip']",
            "div[class*='chip'] button",
            "div[class*='chips'] button",
            # Inline options inside message list
            "li.userItem button",
            "li.botItem button",
            "ul li button",
            "div[class*='option'] button",
            "div[class*='option'] span",
            # Generic clickable inside chatbot
            "div.chatbot_MessageContainer button",
            "div.chatbot_MessageContainer span[role='button']",
            "div.chatbot_MessageContainer a[role='button']",
            # Naukri-specific chip classes
            "span.ssrc__chip",
            "div.ssrc__chip",
            "button.ssrc__chip",
            "span[class*='Chip']",
            "button[class*='Chip']",
            "div[class*='Chip']",
        ]

        for sel in chip_selectors:
            try:
                chips = page.locator(sel)
                count = await chips.count()
                if count == 0:
                    continue

                visible_chips = []
                for i in range(count):
                    if await chips.nth(i).is_visible():
                        visible_chips.append(i)

                if not visible_chips:
                    continue

                logger.info(f"Found {len(visible_chips)} visible chips via: {sel}")

                # Try to match answer
                for i in visible_chips:
                    chip_text = (await chips.nth(i).inner_text()).strip().lower()
                    if answer.lower() in chip_text or chip_text in answer.lower():
                        await chips.nth(i).click()
                        logger.info(f"Clicked matching chip: '{chip_text}'")
                        await page.wait_for_timeout(1500)
                        return True

                # Default: first visible chip
                first_text = (await chips.nth(visible_chips[0]).inner_text()).strip()
                await chips.nth(visible_chips[0]).click()
                logger.info(f"Clicked first visible chip (default): '{first_text}'")
                await page.wait_for_timeout(1500)
                return True

            except Exception:
                continue

        # ── Strategy 2: JavaScript scan for all clickable elements in chatbot ──
        logger.info("Trying JS-based clickable element scan...")
        try:
            result = await page.evaluate("""
                () => {
                    const container = document.querySelector('div.chatbot_MessageContainer');
                    if (!container) return [];
                    
                    const clickables = [];
                    const tags = container.querySelectorAll('button, span[role="button"], a, div[role="button"], li[role="option"]');
                    
                    tags.forEach((el, idx) => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            clickables.push({
                                index: idx,
                                tag: el.tagName,
                                text: el.innerText.trim(),
                                className: el.className,
                                rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}
                            });
                        }
                    });
                    return clickables;
                }
            """)

            logger.info(f"JS scan found {len(result)} clickable elements:")
            for el in result:
                logger.info(f"  [{el['tag']}] text='{el['text']}' class='{el['className']}'")

            # Try to click matching element
            if result:
                # Find best match
                best_idx = None
                for el in result:
                    if el['text'] and answer.lower() in el['text'].lower():
                        best_idx = el['index']
                        break

                # Default to first non-empty clickable
                if best_idx is None:
                    for el in result:
                        if el['text'] and el['text'] not in ('', ' '):
                            best_idx = el['index']
                            break

                if best_idx is not None:
                    await page.evaluate(f"""
                        () => {{
                            const container = document.querySelector('div.chatbot_MessageContainer');
                            const tags = container.querySelectorAll('button, span[role="button"], a, div[role="button"], li[role="option"]');
                            if (tags[{best_idx}]) tags[{best_idx}].click();
                        }}
                    """)
                    logger.info(f"JS-clicked element at index {best_idx}")
                    await page.wait_for_timeout(1500)
                    return True

        except Exception as e:
            logger.warning(f"JS scan failed: {e}")

        # ── Strategy 3: Dump HTML for debugging ──
        if label:
            await self.dump_chatbot_html(page, label)

        return False

    # ------------------------------------------------ #

    async def handle_chatbot(self, page, job_label: str = "") -> tuple[bool, str]:
        """Returns (success, reason)"""

        logger.info("Handling Naukri chatbot...")

        try:
            await page.wait_for_selector("div.chatbot_MessageContainer", timeout=10000)
        except Exception:
            return False, REASON_UNKNOWN

        max_rounds    = 25
        last_question = ""
        stuck_count   = 0

        for round_num in range(max_rounds):

            await page.wait_for_timeout(2000)

            # ── Still open? ──
            if await page.locator("div.chatbot_MessageContainer").count() == 0:
                logger.info("Chatbot closed — applied.")
                return True, "success"

            # ── Completion check ──
            try:
                all_text = (await page.locator("div.chatbot_MessageContainer").inner_text()).lower()
                if any(p in all_text for p in [
                    "successfully applied", "application submitted",
                    "thank you for applying", "your application has been"
                ]):
                    logger.info("Completion message detected.")
                    return True, "success"
            except Exception:
                pass

            # ── Get question ──
            question = await self.get_last_bot_question(page)
            logger.info(f"[Round {round_num+1}] Q: '{question}'")

            # ── Stuck detection ──
            if question and question == last_question:
                stuck_count += 1
                if stuck_count >= 3:
                    logger.warning(f"Stuck on: '{question}'")
                    # Dump HTML so we can debug the chip selectors
                    await self.dump_chatbot_html(page, f"{self._safe_name(job_label)}_stuck")
                    return False, REASON_STUCK
            else:
                stuck_count = 0
            last_question = question

            # ── LLM answer ──
            answer = await self.get_llm_answer(question) if question else "Yes"
            logger.info(f"[Round {round_num+1}] A: '{answer}'")

            # ── Check input type ──
            input_box_visible = False
            try:
                inp = page.locator("div.textArea[contenteditable='true']")
                input_box_visible = (
                    await inp.count() > 0 and await inp.first.is_visible()
                )
            except Exception:
                pass

            if input_box_visible:
                typed = await self.type_into_contenteditable(page, answer)
                if typed:
                    await self.send_message(page)
                else:
                    logger.warning(f"[Round {round_num+1}] Could not type — trying chips.")
                    chip_clicked = await self.handle_chips(
                        page, answer, f"{self._safe_name(job_label)}_r{round_num+1}"
                    )
                    if not chip_clicked:
                        await self._try_skip(page)
            else:
                logger.info(f"[Round {round_num+1}] No text input → trying chips.")
                chip_clicked = await self.handle_chips(
                    page, answer, f"{self._safe_name(job_label)}_r{round_num+1}"
                )
                if not chip_clicked:
                    await self._try_skip(page)

        logger.warning("Max rounds reached.")
        await self.dump_chatbot_html(page, f"{self._safe_name(job_label)}_maxrounds")
        return False, REASON_STUCK

    # ------------------------------------------------ #

    async def _try_skip(self, page):
        for sel in ["button:has-text('Skip')", "span:has-text('Skip')", "button:has-text('Next')"]:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    logger.info(f"Skipped: {sel}")
                    await page.wait_for_timeout(1500)
                    return
            except Exception:
                continue
        await page.wait_for_timeout(2000)

    # ------------------------------------------------ #

    async def apply_to_job(self, context, job: dict) -> tuple[str, str]:

        page = await context.new_page()

        try:
            logger.info(f"Applying: {job['title']} @ {job['company']}")

            # ── Navigate ──
            try:
                await page.goto(job["link"], timeout=30000)
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception as e:
                err = str(e)
                if "ERR_NAME_NOT_RESOLVED" in err or "net::" in err:
                    return "failed", REASON_DNS
                elif "Timeout" in err:
                    return "failed", REASON_TIMEOUT
                else:
                    return "failed", REASON_UNKNOWN

            await page.wait_for_timeout(3000)

            # ── Already applied? (check BEFORE looking for apply button) ──
            if await self.is_already_applied(page):
                return "already_applied", REASON_ALREADY_APPLIED

            # ── Find Apply button ──
            apply_btn = page.locator(
                "button#apply-button, button.apply-button, "
                "a[title='Apply'], button:has-text('Apply Now'), button:has-text('Apply')"
            )

            if await apply_btn.count() == 0:
                # One more check — maybe it's already applied but selector missed
                if await self.is_already_applied(page):
                    return "already_applied", REASON_ALREADY_APPLIED

                logger.warning("Apply button not found.")
                await page.screenshot(path=str(config.DEBUG_DIR / f"debug_{self._safe_name(job['company'])}.png"))
                return "failed", REASON_NO_APPLY_BTN

            # ── Watch for external tab (Easy Apply only — skip external redirects) ──
            new_page_opened = False
            new_page_ref    = None

            async def handle_new_page(new_page):
                nonlocal new_page_opened, new_page_ref
                new_page_opened = True
                new_page_ref    = new_page

            context.on("page", handle_new_page)
            await apply_btn.first.click()
            await page.wait_for_timeout(3000)
            context.remove_listener("page", handle_new_page)

            if new_page_opened and new_page_ref:
                logger.info(f"⏭️  External redirect detected → {new_page_ref.url}")
                logger.info(f"⏭️  Skipping (Easy Apply only mode)")
                await new_page_ref.close()
                return "skipped", REASON_EXTERNAL

            # ── Chatbot ──
            if await page.locator("div.chatbot_MessageContainer").count() > 0:
                success, reason = await self.handle_chatbot(page, job["company"])
                return ("applied" if success else "failed"), reason

            # ── Classic modal ──
            for selector in ["div.apply-modal", "div[class*='applyModal']", "div[class*='apply-flow']"]:
                modal = page.locator(selector)
                if await modal.count() > 0:
                    submit = modal.locator(
                        "button:has-text('Apply'), button:has-text('Submit'), button[type='submit']"
                    )
                    if await submit.count() > 0:
                        await submit.first.click()
                        await page.wait_for_timeout(2000)
                        return "applied", "success"

            # ── Late chatbot (some jobs delay it) ──
            await page.wait_for_timeout(4000)
            if await page.locator("div.chatbot_MessageContainer").count() > 0:
                success, reason = await self.handle_chatbot(page, job["company"])
                return ("applied" if success else "failed"), reason

            logger.warning("Nothing handled after Apply click.")
            await page.screenshot(path=str(config.DEBUG_DIR / f"debug_{self._safe_name(job['company'])}.png"))
            return "failed", REASON_NOTHING_HANDLED

        except Exception as e:
            err = str(e)
            if "ERR_NAME_NOT_RESOLVED" in err or "net::" in err:
                reason = REASON_DNS
            elif "Timeout" in err:
                reason = REASON_TIMEOUT
            else:
                reason = REASON_UNKNOWN
            logger.error(f"Error [{reason}]: {e}")
            return "failed", reason

        finally:
            await page.close()

    # ------------------------------------------------ #

    async def log_result(self, job: dict, status: str, reason: str = ""):
        mapping = {
            "applied":         self.applied_file,
            "already_applied": self.applied_file,
            "external":        self.external_file,
            "skipped":         self.skipped_file,
        }
        target = mapping.get(status, self.failed_file)
        reason_str = f" | reason: {reason}" if reason and status == "failed" else ""
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"[{status.upper()}] {job['title']} | {job['company']} | {job['link']}{reason_str}\n")

    # ------------------------------------------------ #

    async def run(self, jobs: list) -> dict:
        """Run Easy Apply on jobs and return a summary dict."""

        for path in [self.applied_file, self.failed_file, self.external_file, self.skipped_file]:
            path.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "applied": 0,
            "already_applied": 0,
            "skipped_external": 0,
            "skipped_blocked": 0,
            "failed": 0,
            "total": 0,
            "details": [],
        }

        # Deduplicate
        seen, unique_jobs = set(), []
        for job in jobs:
            if job["link"] not in seen:
                seen.add(job["link"])
                unique_jobs.append(job)
            else:
                logger.info(f"  ↳ Duplicate skipped: {job['title']} @ {job['company']}")

        # Filter blocked and external
        filtered = []
        for job in unique_jobs:
            apply_type = str(job.get("apply_type", "")).lower()

            if self.is_blocked(job.get("company", "")):
                logger.info(f"  ⛔ Blocked company skipped: {job['company']}")
                await self.log_result(job, "skipped", "blocked_company")
                summary["skipped_blocked"] += 1
                summary["details"].append({"title": job.get("title"), "company": job.get("company"), "status": "skipped", "reason": "blocked_company"})
            elif apply_type != "easy_apply":
                logger.info(f"  ⏭️ Non-easy apply job skipped: {job['title']} @ {job['company']} (type: {apply_type})")
                await self.log_result(job, "skipped", f"not_easy_apply_{apply_type}")
                summary["skipped_external"] += 1
                summary["details"].append({"title": job.get("title"), "company": job.get("company"), "status": "skipped", "reason": "not_easy_apply"})
            else:
                filtered.append(job)

        summary["total"] = len(filtered) + summary["skipped_blocked"] + summary["skipped_external"]

        logger.info("")
        logger.info("━" * 55)
        logger.info(f"  🚀 Easy Apply — {len(filtered)} jobs to process")
        logger.info("━" * 55)

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 800})

            page = await context.new_page()
            await self.login(page)
            await page.close()

            for i, job in enumerate(filtered):
                progress = f"[{i+1}/{len(filtered)}]"
                logger.info(f"")
                logger.info(f"  {progress} 📋 {job['title']} @ {job['company']}")
                logger.info(f"  {' ' * len(progress)} 🔗 {job['link'][:80]}...")

                status, reason = await self.apply_to_job(context, job)
                await self.log_result(job, status, reason)

                # Track results
                detail = {"title": job.get("title"), "company": job.get("company"), "status": status, "reason": reason}
                summary["details"].append(detail)

                if status == "applied":
                    summary["applied"] += 1
                    logger.info(f"  {' ' * len(progress)} ✅ Applied successfully")
                elif status == "already_applied":
                    summary["already_applied"] += 1
                    logger.info(f"  {' ' * len(progress)} ℹ️  Already applied")
                elif status == "skipped" and reason == REASON_EXTERNAL:
                    summary["skipped_external"] += 1
                    logger.info(f"  {' ' * len(progress)} ⏭️  Skipped (External — Easy Apply only)")
                elif status == "failed":
                    summary["failed"] += 1
                    logger.info(f"  {' ' * len(progress)} ❌ Failed: {reason}")
                else:
                    summary["failed"] += 1
                    logger.info(f"  {' ' * len(progress)} ⚠️  {status}: {reason}")

                await asyncio.sleep(3)

            await browser.close()

        # Print final summary to terminal
        logger.info("")
        logger.info("━" * 55)
        logger.info("  📊 Application Summary")
        logger.info("━" * 55)
        logger.info(f"  ✅ Applied:            {summary['applied']}")
        logger.info(f"  ℹ️  Already Applied:    {summary['already_applied']}")
        logger.info(f"  ⏭️  Skipped (External): {summary['skipped_external']}")
        logger.info(f"  ⛔ Skipped (Blocked):  {summary['skipped_blocked']}")
        logger.info(f"  ❌ Failed:             {summary['failed']}")
        logger.info(f"  ───────────────────────")
        logger.info(f"  📦 Total Processed:    {summary['total']}")
        logger.info("━" * 55)
        logger.info(f"  Logs → {self.applied_file}")
        logger.info(f"         {self.failed_file}")
        logger.info("━" * 55)

        return summary


# ------------------------------------------------ #

async def main():
    jobs = load_jobs_from_file("./data/naukri_jobs.txt")
    logger.info(f"Loaded {len(jobs)} jobs from file.")
    applier = NaukriApplier(
        email=config.NAUKRI_EMAIL,
        password=config.NAUKRI_PASSWORD
    )
    await applier.run(jobs)


if __name__ == "__main__":
    asyncio.run(main())