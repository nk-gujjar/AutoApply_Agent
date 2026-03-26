"""
NaukriScraper — Login + Pagination + Hang-Free + External Apply Link
====================================================================

New in this version:
  5. EXTERNAL APPLY LINK — when a job redirects to an external company
     site, the actual destination URL is now captured and saved.

     Strategy A (static):  JS scans the DOM for anchor hrefs on
                           "Apply on company site" style buttons.
                           Works for jobs where Naukri embeds the URL
                           directly in the page HTML.

     Strategy B (click intercept): If Strategy A finds nothing, we
                           click the apply button and intercept the
                           new tab/popup that Naukri opens. We read
                           the URL from the new page, then immediately
                           close it — we never actually visit the site.
                           Works for JS-redirect jobs.

     The captured URL is stored in job["external_apply_link"] and
     written to the output .txt file as "External Apply Link".
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import config, create_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Hard timeouts (seconds) ──────────────────────────────────────────────── #
PAGE_TIMEOUT    = 25    # navigation
ELEM_TIMEOUT    = 8     # wait_for_selector
ACTION_TIMEOUT  = 5     # single JS evaluate / DOM read
NEW_TAB_TIMEOUT = 8     # how long to wait for a new tab to open after click

# ── Filters ──────────────────────────────────────────────────────────────── #
DEFAULT_FILTERS = {
    "min_ctc_lpa":          None,
    "max_ctc_lpa":          None,
    "min_exp_years":        None,
    "max_exp_years":        None,
    "locations":            [],
    "apply_type":           None,   # "easy_apply" | "external" | None = both
    "skip_already_applied": True,
}


# ── Utility ───────────────────────────────────────────────────────────────── #

async def _safe(coro, default=None, label: str = ""):
    """Hard-cap any awaitable to ACTION_TIMEOUT. Never raises."""
    try:
        return await asyncio.wait_for(coro, timeout=ACTION_TIMEOUT)
    except Exception as exc:
        if label:
            logger.debug(f"_safe({label}) → {type(exc).__name__}: {exc}")
        return default


# ─────────────────────────────────────────────────────────────────────────── #

class NaukriScraper:

    BASE_URL = "https://www.naukri.com/{role}-jobs"

    def __init__(self, filters: dict = None, max_jobs: int = 10):

        self.roles = [
            "ai-engineer",
            "machine-learning-engineer",
            "software-engineer",
            "sde",
            "backend-developer",
        ]

        self.output_file = Path("./data/naukri_jobs.txt")
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self.max_jobs = max_jobs
        self.filters  = {**DEFAULT_FILTERS, **(filters or {})}

        # ── LLM ──────────────────────────────────────────────────────── #
        self.llm = create_llm(temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["jd"],
            template="""Extract key information from this job description for CV tailoring.

Return ONLY this exact structure, no extra text:

Role:
Experience Required:
Key Skills:
Tech Stack:
CTC:
Main Responsibilities:

Job Description:
{jd}
""",
        )
        self.jd_chain = self.prompt | self.llm | StrOutputParser()

    # ════════════════════════════════════════════════════════════════════ #
    #  LOGIN                                                                #
    # ════════════════════════════════════════════════════════════════════ #

    async def login(self, page) -> bool:
        logger.info("Logging in to Naukri...")
        ok = await self._goto(page, "https://www.naukri.com/nlogin/login")
        if not ok:
            logger.error("Cannot reach login page.")
            return False

        await asyncio.sleep(2)

        email_filled = False
        for sel in ["input#usernameField", "input[name='username']", "input[type='email']"]:
            try:
                await asyncio.wait_for(page.wait_for_selector(sel, state="visible"), timeout=5)
                await page.fill(sel, config.NAUKRI_EMAIL)
                email_filled = True
                break
            except Exception:
                continue

        if not email_filled:
            logger.error("Email field not found.")
            return False

        for sel in ["input#passwordField", "input[name='password']", "input[type='password']"]:
            try:
                await asyncio.wait_for(page.wait_for_selector(sel, state="visible"), timeout=5)
                await page.fill(sel, config.NAUKRI_PASSWORD)
                break
            except Exception:
                continue

        for sel in ["button[type='submit']", "button:has-text('Login')", "button:has-text('Sign in')"]:
            try:
                await page.click(sel, timeout=4000)
                break
            except Exception:
                continue

        await asyncio.sleep(4)
        success = "login" not in page.url.lower()
        logger.info(f"  Login {'✅' if success else '⚠️ may have failed'} — {page.url}")
        return success

    # ════════════════════════════════════════════════════════════════════ #
    #  LLM REWRITE                                                          #
    # ════════════════════════════════════════════════════════════════════ #

    async def rewrite_jd(self, jd_text: str) -> tuple:
        for attempt in range(3):
            try:
                result = await asyncio.wait_for(
                    self.jd_chain.ainvoke({"jd": jd_text[:3000]}),
                    timeout=30,
                )
                if result and len(result.strip()) > 20:
                    return result.strip(), True
            except asyncio.TimeoutError:
                logger.warning(f"  LLM attempt {attempt+1} timed out")
            except Exception as e:
                logger.warning(f"  LLM attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2 ** attempt)

        logger.warning("  All LLM retries failed — using raw text.")
        return jd_text[:2000], False

    # ════════════════════════════════════════════════════════════════════ #
    #  HTML CLEANING                                                         #
    # ════════════════════════════════════════════════════════════════════ #

    def clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
        return "\n".join(l for l in lines if len(l) >= 40 and "cookie" not in l.lower())

    # ════════════════════════════════════════════════════════════════════ #
    #  FILTER PARSERS                                                        #
    # ════════════════════════════════════════════════════════════════════ #

    def _parse_ctc_lpa(self, s: str):
        if not s:
            return None, None
        s = s.lower().replace(",", "")
        m = re.search(r"(\d+\.?\d*)\s*-?\s*(\d+\.?\d*)?\s*cr", s)
        if m:
            return float(m.group(1)) * 100, float(m.group(2) or m.group(1)) * 100
        m = re.search(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", s)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = re.search(r"(\d+\.?\d*)", s)
        if m:
            v = float(m.group(1))
            return v, v
        return None, None

    def _parse_exp_years(self, s: str):
        if not s:
            return None, None
        sl = s.lower()
        if "fresher" in sl:
            return 0, 0
        m = re.search(r"(\d+)\s*-\s*(\d+)", sl)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d+)", sl)
        if m:
            v = int(m.group(1))
            return v, v
        return None, None

    # ════════════════════════════════════════════════════════════════════ #
    #  FILTER GATE                                                           #
    # ════════════════════════════════════════════════════════════════════ #

    def _passes_filters(self, job: dict) -> tuple:
        f = self.filters

        if f["skip_already_applied"] and job.get("apply_status") == "already_applied":
            return False, "Already applied"

        if f["apply_type"] and job.get("apply_type") != f["apply_type"]:
            return False, f"apply_type mismatch (want={f['apply_type']}, got={job.get('apply_type')})"

        if f["locations"]:
            loc = (job.get("location") or "").lower()
            if not any(l.lower() in loc for l in f["locations"]):
                return False, f"Location mismatch ({job.get('location')})"

        lo_e, hi_e = self._parse_exp_years(job.get("experience", ""))
        if lo_e is not None:
            if f["min_exp_years"] is not None and hi_e < f["min_exp_years"]:
                return False, f"Exp too low ({job.get('experience')})"
            if f["max_exp_years"] is not None and lo_e > f["max_exp_years"]:
                return False, f"Exp too high ({job.get('experience')})"

        ctc_raw = job.get("ctc") or job.get("salary_card") or ""
        lo_c, hi_c = self._parse_ctc_lpa(ctc_raw)
        if lo_c is not None:
            if f["min_ctc_lpa"] is not None and hi_c < f["min_ctc_lpa"]:
                return False, f"CTC too low ({ctc_raw})"
            if f["max_ctc_lpa"] is not None and lo_c > f["max_ctc_lpa"]:
                return False, f"CTC too high ({ctc_raw})"

        return True, ""

    # ════════════════════════════════════════════════════════════════════ #
    #  NAVIGATION HELPERS                                                    #
    # ════════════════════════════════════════════════════════════════════ #

    async def _goto(self, page, url: str) -> bool:
        try:
            await asyncio.wait_for(
                page.goto(url, wait_until="domcontentloaded"),
                timeout=PAGE_TIMEOUT,
            )
            return True
        except Exception as e:
            logger.warning(f"_goto failed [{url[:80]}]: {type(e).__name__}")
            return False

    async def _wait_sel(self, page, selector: str, timeout: float = ELEM_TIMEOUT) -> bool:
        try:
            await asyncio.wait_for(
                page.wait_for_selector(selector, state="attached"),
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    # ════════════════════════════════════════════════════════════════════ #
    #  JS: EXTRACT CARDS FROM LISTING PAGE                                  #
    # ════════════════════════════════════════════════════════════════════ #

    _JS_CARDS = r"""
    () => {
        const getText = (root, ...sels) => {
            for (const s of sels) {
                const el = root.querySelector(s);
                if (el && el.innerText.trim()) return el.innerText.trim();
            }
            return '';
        };
        return Array.from(document.querySelectorAll('div.cust-job-tuple'))
            .map(card => {
                const a    = card.querySelector('a.title');
                const title = a ? a.innerText.trim() : '';
                const link  = a ? (a.href || '') : '';
                return {
                    title,
                    link,
                    company:     getText(card, '.comp-name', '[class*="comp-name"]', '[class*="company"]'),
                    location:    getText(card, '.locWdth',   '[class*="location"]',  '[class*="loc"]'),
                    experience:  getText(card, '.expwdth',   '[class*="exp"]'),
                    salary_card: getText(card, '.sal', '[class*="salary"]', '[class*="sal"]') || 'Not mentioned',
                };
            })
            .filter(j => j.link);
    }
    """

    # ════════════════════════════════════════════════════════════════════ #
    #  JS: EXTRACT JD PAGE DATA + EXTERNAL LINK (Strategy A — static)      #
    # ════════════════════════════════════════════════════════════════════ #

    _JS_JD_PAGE = r"""
    () => {
        // ── JD text ──────────────────────────────────────────────────
        const jdSelectors = [
            'div.styles_JDC__dang-inner-html__h0K4t',
            'section.styles_job-desc-container__txpYf',
            'div.job-desc', 'div#job-desc', 'div.jd-desc',
            'div.dang-inner-html', 'article',
        ];
        let jdText = '';
        for (const sel of jdSelectors) {
            const el = document.querySelector(sel);
            if (el && el.innerText.trim().length > 100) {
                jdText = el.innerText.trim();
                break;
            }
        }
        if (!jdText && document.body)
            jdText = document.body.innerText.slice(0, 4000);

        // ── Salary ───────────────────────────────────────────────────
        let salary = '';
        for (const sel of [
            'div.styles_jhc__salary__jdfEC',
            '[class*="salary"]', '[class*="ctc"]', '[class*="package"]'
        ]) {
            const el = document.querySelector(sel);
            if (el) {
                const t = el.innerText.trim();
                if (/[0-9]/.test(t) && /lac|lpa|lakh|cr|₹/i.test(t)) {
                    salary = t; break;
                }
            }
        }

        // ── Already applied ──────────────────────────────────────────
        const bodyText = document.body ? document.body.innerText : '';
        const alreadyApplied =
            /already\s+applied|application\s+submitted|you\s+have\s+applied/i
            .test(bodyText);

        // ── Apply type + external link (Strategy A) ──────────────────
        //
        // We scan every button/anchor. For external-type elements we also
        // read the href — this works when Naukri has the destination URL
        // directly in the anchor tag (common for "Apply on company site").
        //
        let applyType        = 'no_apply_button';
        let externalApplyLink = '';

        for (const el of document.querySelectorAll('button, a, input[type="button"]')) {
            const t    = (el.innerText || el.value || el.getAttribute('aria-label') || '')
                            .trim().toLowerCase();
            const cls  = (el.className || '').toLowerCase();
            const href = el.href  || '';          // keep original case for the URL
            const hrefL = href.toLowerCase();
            const id   = (el.id   || '').toLowerCase();

            if (!t.includes('apply') && !cls.includes('apply') && !id.includes('apply'))
                continue;

            // Already-applied state
            if (t === 'applied' || t.includes('already applied') ||
                cls.includes('already-applied') || cls.includes('applied-status')) {
                applyType = 'already_applied_btn';
                break;
            }

            // Easy Apply
            if (t.includes('easy apply') || cls.includes('easy') ||
                t.includes('1 click')     || id === 'apply-button') {
                applyType = 'easy_apply';
                break;
            }

            // External Apply — capture the href if it points away from naukri
            if (t.includes('apply on') || cls.includes('external') ||
                (href && !hrefL.includes('naukri.com') && hrefL.startsWith('http'))) {

                applyType = 'external';

                // Only store if it's a real external URL (not a naukri redirect stub)
                if (href && !hrefL.includes('naukri.com') && hrefL.startsWith('http')) {
                    externalApplyLink = href;
                }
                break;
            }

            // Generic Apply / Apply Now
            if (t === 'apply' || t === 'apply now') {
                applyType = 'easy_apply';
                break;
            }
        }

        return { jdText, salary, alreadyApplied, applyType, externalApplyLink };
    }
    """

    # ════════════════════════════════════════════════════════════════════ #
    #  STRATEGY B — click intercept to capture JS-redirected external URL  #
    # ════════════════════════════════════════════════════════════════════ #

    async def _intercept_external_link(self, context, page) -> str:
        """
        For jobs where the external URL is hidden behind a JS onclick handler
        (not in the DOM as an href), we:
          1. Listen for a new page/tab event on the context.
          2. Click the apply button.
          3. Capture the URL of the new tab that Naukri opens.
          4. Close the new tab immediately — we never navigate there.

        Returns the captured URL string, or "" if nothing opened.
        """
        captured_url = ""
        new_tab_event = asyncio.Event()

        async def _on_page(new_page):
            nonlocal captured_url
            try:
                # Wait for the page to commit its URL (not just about:blank)
                await asyncio.wait_for(
                    new_page.wait_for_load_state("commit"),
                    timeout=NEW_TAB_TIMEOUT,
                )
                url = new_page.url
                # Only accept if it's a real external URL
                if url and url.startswith("http") and "naukri.com" not in url.lower():
                    captured_url = url
                    logger.info(f"  🔗 Intercepted external URL: {url[:100]}")
            except Exception as e:
                logger.debug(f"  _on_page intercept error: {e}")
            finally:
                await _safe(new_page.close(), label="intercept_tab_close")
                new_tab_event.set()

        # Register listener BEFORE clicking
        context.on("page", _on_page)

        try:
            # Find and click the apply button via JS (no locator timeout)
            clicked = await _safe(
                page.evaluate(r"""
                    () => {
                        for (const el of document.querySelectorAll('button, a')) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('apply')) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """),
                default=False,
                label="click_apply_btn",
            )

            if clicked:
                # Give Naukri up to NEW_TAB_TIMEOUT seconds to open the tab
                try:
                    await asyncio.wait_for(
                        new_tab_event.wait(),
                        timeout=NEW_TAB_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.debug("  No new tab opened within timeout")
            else:
                logger.debug("  Could not find apply button to click")

        finally:
            # Always remove the listener so it doesn't fire on future pages
            context.remove_listener("page", _on_page)

        return captured_url

    # ════════════════════════════════════════════════════════════════════ #
    #  SCROLL HELPER                                                         #
    # ════════════════════════════════════════════════════════════════════ #

    async def scroll_page(self, page):
        for _ in range(3):
            await _safe(page.mouse.wheel(0, 3000), label="scroll")
            await asyncio.sleep(1.0)

    # ════════════════════════════════════════════════════════════════════ #
    #  SCRAPE ONE LISTING PAGE                                               #
    # ════════════════════════════════════════════════════════════════════ #

    async def _scrape_listing_page(self, page, role: str, page_no: int) -> list:
        url = self.BASE_URL.format(role=role)
        if page_no > 1:
            url = f"{url}?pageNo={page_no}"

        logger.info(f"  Listing → {url}")

        ok = await self._goto(page, url)
        if not ok:
            return []

        found = await self._wait_sel(page, "div.cust-job-tuple")
        if not found:
            logger.info(f"  No cards on page {page_no} for [{role}]")
            return []

        await self.scroll_page(page)

        cards = await _safe(
            page.evaluate(self._JS_CARDS),
            default=[],
            label="extract_cards",
        )
        logger.info(f"  Extracted {len(cards or [])} cards (page {page_no})")
        return cards or []

    # ════════════════════════════════════════════════════════════════════ #
    #  FETCH FULL JD + APPLY INFO FOR ONE JOB                               #
    # ════════════════════════════════════════════════════════════════════ #

    async def fetch_job_details(self, context, link: str) -> dict:
        details = {
            "jd_summary":          "(Could not fetch)",
            "jd_llm_used":         False,
            "ctc":                 "Not mentioned",
            "apply_type":          "unknown",
            "apply_status":        "unknown",
            "external_apply_link": "",   # ← NEW
        }

        page = await context.new_page()
        try:
            ok = await self._goto(page, link)
            if not ok:
                return details

            await asyncio.sleep(1.5)   # let JS settle

            # ── Strategy A: pure JS extraction ───────────────────── #
            data = await _safe(
                page.evaluate(self._JS_JD_PAGE),
                default={},
                label="jd_page_js",
            )

            if not data:
                logger.warning(f"  JS extraction empty for {link[:60]}")
                return details

            # Apply status / type
            if data.get("alreadyApplied") or data.get("applyType") == "already_applied_btn":
                details["apply_status"] = "already_applied"
                details["apply_type"]   = "unknown"
            else:
                details["apply_status"] = "apply"
                details["apply_type"]   = data.get("applyType", "unknown")

            # CTC
            if data.get("salary"):
                details["ctc"] = data["salary"]

            # External link from Strategy A
            ext_link = data.get("externalApplyLink", "")

            # ── Strategy B: click intercept (only for external jobs  ── #
            # where Strategy A didn't find a URL in the DOM)
            if details["apply_type"] == "external" and not ext_link:
                logger.info("  External job — trying click intercept for URL...")
                ext_link = await self._intercept_external_link(context, page)

            if ext_link:
                details["external_apply_link"] = ext_link
                logger.info(f"  External apply link: {ext_link[:80]}")

            # ── JD text ───────────────────────────────────────────── #
            jd_raw = data.get("jdText", "")
            if not jd_raw:
                html   = await _safe(page.content(), default="", label="page.content")
                jd_raw = self.clean_html(html) if html else ""

            if jd_raw:
                summary, llm_used = await self.rewrite_jd(jd_raw)
                details["jd_summary"]  = summary
                details["jd_llm_used"] = llm_used
            else:
                details["jd_summary"] = "(Empty page)"

        except Exception as e:
            logger.error(f"  fetch_job_details unexpected: {e}")
        finally:
            await _safe(page.close(), label="page.close")

        return details

    # ════════════════════════════════════════════════════════════════════ #
    #  MAIN ORCHESTRATION                                                    #
    # ════════════════════════════════════════════════════════════════════ #

    async def scrape_jobs(self) -> list:
        all_jobs = []

        async with async_playwright() as pw:

            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )

            # Block images / fonts — ~40% faster page loads
            _blocked = re.compile(
                r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|otf)(\?|$)", re.I
            )
            async def _block(route, request):
                if _blocked.search(request.url):
                    await route.abort()
                else:
                    await route.continue_()
            await context.route("**/*", _block)

            # Login
            login_page = await context.new_page()
            await self.login(login_page)
            await login_page.close()

            listing_page = await context.new_page()

            for role in self.roles:

                if len(all_jobs) >= self.max_jobs:
                    break

                page_no = 1

                while len(all_jobs) < self.max_jobs:

                    cards = await self._scrape_listing_page(listing_page, role, page_no)

                    if not cards:
                        logger.info(f"  No more cards for [{role}] after page {page_no}")
                        break

                    for card in cards:

                        if len(all_jobs) >= self.max_jobs:
                            break

                        card["role_category"] = role
                        card["page_no"]       = page_no

                        logger.info(
                            f"  ↳ [{len(all_jobs)+1}/{self.max_jobs}] "
                            f"{card['title']} @ {card['company']}"
                        )

                        details = await self.fetch_job_details(context, card["link"])
                        card.update(details)

                        # Best CTC: detail page wins, card as fallback
                        if not card.get("ctc") or card["ctc"] == "Not mentioned":
                            card["ctc"] = card.get("salary_card", "Not mentioned")

                        card["scraped_at"] = datetime.now().isoformat()

                        passes, reason = self._passes_filters(card)
                        card["filter_status"] = "passed" if passes else f"filtered_out: {reason}"

                        await self.save_job(card)

                        if passes:
                            all_jobs.append(card)
                            ext = f" ext={card['external_apply_link'][:40]}" if card.get("external_apply_link") else ""
                            logger.info(
                                f"  ✅ SAVED  apply={card['apply_type']} "
                                f"status={card['apply_status']}{ext} "
                                f"ctc={card['ctc']}"
                            )
                        else:
                            logger.info(f"  ⛔ FILTERED: {reason}")

                    page_no += 1

            await browser.close()

        return all_jobs

    # ════════════════════════════════════════════════════════════════════ #
    #  SAVE TO FILE                                                          #
    # ════════════════════════════════════════════════════════════════════ #

    async def save_job(self, job: dict):
        with open(self.output_file, "a", encoding="utf-8") as f:
            sep = "=" * 65
            f.write(f"\n{sep}\n")
            f.write(f"Title              : {job.get('title',                'N/A')}\n")
            f.write(f"Company            : {job.get('company',              'N/A')}\n")
            f.write(f"Location           : {job.get('location',             'N/A')}\n")
            f.write(f"Experience         : {job.get('experience',           'N/A')}\n")
            f.write(f"CTC / Salary       : {job.get('ctc',                 'Not mentioned')}\n")
            f.write(f"Apply Type         : {job.get('apply_type',           'unknown')}\n")
            f.write(f"Apply Status       : {job.get('apply_status',         'unknown')}\n")

            # ── External apply link (only written when present) ──────── #
            ext = job.get("external_apply_link", "")
            if ext:
                f.write(f"External Apply Link: {ext}\n")
            else:
                f.write(f"External Apply Link: N/A\n")

            f.write(f"JD Source          : {'LLM Summary' if job.get('jd_llm_used') else 'Raw Text'}\n")
            f.write(f"Filter Status      : {job.get('filter_status',        'N/A')}\n")
            f.write(f"Role Category      : {job.get('role_category',        'N/A')}\n")
            f.write(f"Listing Page       : {job.get('page_no',              1)}\n")
            f.write(f"Scraped At         : {job.get('scraped_at',           'N/A')}\n")
            f.write(f"Naukri Link        : {job.get('link',                 'N/A')}\n")
            f.write(f"\n--- Job Details ({'LLM-extracted' if job.get('jd_llm_used') else 'Raw'}) ---\n")
            f.write(job.get("jd_summary", "(No JD available)"))
            f.write(f"\n{sep}\n")

    # ════════════════════════════════════════════════════════════════════ #
    #  ENTRY                                                                 #
    # ════════════════════════════════════════════════════════════════════ #

    async def run(self):
        logger.info("=== NaukriScraper Starting ===")
        logger.info(f"Max jobs : {self.max_jobs}")
        logger.info(f"Filters  : {self.filters}")
        jobs = await self.scrape_jobs()
        logger.info(f"=== Done. Qualifying jobs scraped: {len(jobs)} ===")
        return jobs


# ── CLI ───────────────────────────────────────────────────────────────────── #

async def main():
    scraper = NaukriScraper(
        filters={
            # "min_ctc_lpa":   10,
            # "max_ctc_lpa":   40,
            # "min_exp_years": 1,
            # "max_exp_years": 5,
            # "apply_type":    "easy_apply",
            # "locations":     ["Bengaluru", "Remote"],
            "skip_already_applied": True,
        },
        max_jobs=20,
    )
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())