"""
FetchJob.py
===========
Provides a single async generator:

    async for job in fetch_jobs(roles, filters, max_jobs):
        print(job)          # do whatever you want per job

Each `yield` returns one fully-enriched job dict the moment it is ready:
    {
        title, company, location, experience,
        salary_card,            # salary shown on listing card
        ctc,                    # salary extracted from JD page (preferred)
        apply_type,             # "easy_apply" | "external" | "no_apply_button"
        apply_status,           # "apply" | "already_applied"
        jd_summary,             # LLM summary OR raw text (fallback)
        jd_llm_used,            # True if LLM succeeded
        filter_status,          # "passed" | "filtered_out: <reason>"
        role_category,          # which role slug produced this job
        page_no,                # listing page number (1, 2, ...)
        link,                   # direct job URL
        scraped_at,             # ISO timestamp
    }

Usage
-----
    import asyncio
    from FetchJob import fetch_jobs

    async def main():
        async for job in fetch_jobs(max_jobs=5):
            print(job["title"], "|", job["apply_type"], "|", job["ctc"])

    asyncio.run(main())

    # ── With filters ──────────────────────────────────────────────────
    async for job in fetch_jobs(
        roles=["ai-engineer", "sde"],
        filters={
            "min_ctc_lpa":   10,
            "max_ctc_lpa":   40,
            "min_exp_years": 1,
            "max_exp_years": 5,
            "apply_type":    "easy_apply",      # or "external" or None
            "locations":     ["Bengaluru"],
            "skip_already_applied": True,
        },
        max_jobs=20,
        include_filtered=False,   # set True to also yield filtered-out jobs
    ):
        print(job)
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import AsyncGenerator

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from modules.core.config.settings import config, create_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Timeouts ─────────────────────────────────────────────────────────────── #
PAGE_TIMEOUT   = 25   # seconds — page navigation hard cap
ELEM_TIMEOUT   = 8    # seconds — wait_for_selector hard cap
ACTION_TIMEOUT = 5    # seconds — single JS evaluate hard cap

# ── Default roles ─────────────────────────────────────────────────────────── #
DEFAULT_ROLES = [
    "ai-engineer",
    "machine-learning-engineer",
    "software-engineer",
    "sde",
    "backend-developer",
]

# ── Default filters (all off) ─────────────────────────────────────────────── #
DEFAULT_FILTERS: dict = {
    "min_ctc_lpa":          None,
    "max_ctc_lpa":          None,
    "min_exp_years":        None,
    "max_exp_years":        None,
    "locations":            [],
    "apply_type":           None,   # "easy_apply" | "external" | None
    "skip_already_applied": True,
}

BASE_URL = "https://www.naukri.com/{role}-jobs"


# ═══════════════════════════════════════════════════════════════════════════ #
#  Internal helpers                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

async def _safe(coro, default=None, label: str = ""):
    """Await with ACTION_TIMEOUT. Returns default on any failure — never raises."""
    try:
        return await asyncio.wait_for(coro, timeout=ACTION_TIMEOUT)
    except Exception as exc:
        if label:
            logger.debug(f"_safe({label}) swallowed {type(exc).__name__}: {exc}")
        return default


async def _goto(page, url: str) -> bool:
    try:
        await asyncio.wait_for(
            page.goto(url, wait_until="domcontentloaded"),
            timeout=PAGE_TIMEOUT,
        )
        return True
    except Exception as e:
        logger.warning(f"_goto failed [{url[:80]}]: {type(e).__name__}")
        return False


async def _wait_sel(page, selector: str, timeout: float = ELEM_TIMEOUT) -> bool:
    try:
        await asyncio.wait_for(
            page.wait_for_selector(selector, state="attached"),
            timeout=timeout,
        )
        return True
    except Exception:
        return False


# ── CTC / Exp parsers (for filters) ──────────────────────────────────────── #

def _parse_ctc_lpa(s: str):
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


def _parse_exp_years(s: str):
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


def _passes_filters(job: dict, filters: dict) -> tuple:
    f = filters

    if f["skip_already_applied"] and job.get("apply_status") == "already_applied":
        return False, "Already applied"

    if f["apply_type"] and job.get("apply_type") != f["apply_type"]:
        return False, f"apply_type mismatch (want={f['apply_type']}, got={job.get('apply_type')})"

    if f["locations"]:
        loc = (job.get("location") or "").lower()
        if not any(l.lower() in loc for l in f["locations"]):
            return False, f"Location mismatch ({job.get('location')})"

    lo_e, hi_e = _parse_exp_years(job.get("experience", ""))
    if lo_e is not None:
        if f["min_exp_years"] is not None and hi_e < f["min_exp_years"]:
            return False, f"Exp too low ({job.get('experience')})"
        if f["max_exp_years"] is not None and lo_e > f["max_exp_years"]:
            return False, f"Exp too high ({job.get('experience')})"

    ctc_raw = job.get("ctc") or job.get("salary_card") or ""
    lo_c, hi_c = _parse_ctc_lpa(ctc_raw)
    if lo_c is not None:
        if f["min_ctc_lpa"] is not None and hi_c < f["min_ctc_lpa"]:
            return False, f"CTC too low ({ctc_raw})"
        if f["max_ctc_lpa"] is not None and lo_c > f["max_ctc_lpa"]:
            return False, f"CTC too high ({ctc_raw})"

    return True, ""


# ── JS snippets ───────────────────────────────────────────────────────────── #

_JS_EXTRACT_CARDS = r"""
() => {
    const getText = (root, ...selectors) => {
        for (const sel of selectors) {
            const el = root.querySelector(sel);
            if (el && el.innerText.trim()) return el.innerText.trim();
        }
        return '';
    };

    return Array.from(document.querySelectorAll('div.cust-job-tuple'))
        .map(card => {
            const titleEl  = card.querySelector('a.title');
            const title    = titleEl ? titleEl.innerText.trim() : '';
            const link     = titleEl ? (titleEl.href || '') : '';
            const company  = getText(card, '.comp-name', '[class*="comp-name"]', '[class*="company"]');
            const location = getText(card, '.locWdth',   '[class*="location"]',  '[class*="loc"]');
            const experience = getText(card, '.expwdth', '[class*="exp"]');
            const salary_card = getText(card, '.sal', '[class*="salary"]', '[class*="sal"]') || 'Not mentioned';
            return { title, link, company, location, experience, salary_card };
        })
        .filter(j => j.link);
}
"""

_JS_EXTRACT_JD_PAGE = r"""
() => {
    // ── JD text ──────────────────────────────────────────────────────────
    const jdSelectors = [
        'div.styles_JDC__dang-inner-html__h0K4t',
        'section.styles_job-desc-container__txpYf',
        'div.job-desc', 'div#job-desc', 'div.jd-desc',
        'div.dang-inner-html', 'article',
    ];
    let jdText = '';
    for (const sel of jdSelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim().length > 100) { jdText = el.innerText.trim(); break; }
    }
    if (!jdText && document.body) jdText = document.body.innerText.slice(0, 4000);

    // ── Salary ────────────────────────────────────────────────────────────
    let salary = '';
    for (const sel of ['div.styles_jhc__salary__jdfEC','[class*="salary"]','[class*="ctc"]','[class*="package"]']) {
        const el = document.querySelector(sel);
        if (el) {
            const t = el.innerText.trim();
            if (/[0-9]/.test(t) && /lac|lpa|lakh|cr|₹/i.test(t)) { salary = t; break; }
        }
    }

    // ── Already applied ───────────────────────────────────────────────────
    const bodyText = document.body ? document.body.innerText : '';
    const alreadyApplied = /already\s+applied|application\s+submitted|you\s+have\s+applied/i.test(bodyText);

    // ── Apply type ────────────────────────────────────────────────────────
    let applyType = 'no_apply_button';
    for (const el of document.querySelectorAll('button, a, input[type="button"]')) {
        const t   = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().toLowerCase();
        const cls = (el.className || '').toLowerCase();
        const href = (el.href || '').toLowerCase();
        const id   = (el.id   || '').toLowerCase();

        if (!t.includes('apply') && !cls.includes('apply') && !id.includes('apply')) continue;

        if (t === 'applied' || t.includes('already applied') || cls.includes('already-applied')) {
            applyType = 'already_applied_btn'; break;
        }
        if (t.includes('easy apply') || cls.includes('easy') || t.includes('1 click') || id === 'apply-button') {
            applyType = 'easy_apply'; break;
        }
        if (t.includes('apply on') || cls.includes('external') ||
            (href && !href.includes('naukri.com') && href.startsWith('http'))) {
            applyType = 'external'; break;
        }
        if (t === 'apply' || t === 'apply now') { applyType = 'easy_apply'; break; }
    }

    return { jdText, salary, alreadyApplied, applyType };
}
"""


# ═══════════════════════════════════════════════════════════════════════════ #
#  Login                                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

async def _login(page) -> bool:
    """Log in to Naukri. Returns True if successful."""
    logger.info("Logging in to Naukri...")
    ok = await _goto(page, "https://www.naukri.com/nlogin/login")
    if not ok:
        logger.error("Cannot reach Naukri login page.")
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
    logger.info(f"Login {'✅ success' if success else '⚠️ may have failed'} — URL: {page.url}")
    return success


# ═══════════════════════════════════════════════════════════════════════════ #
#  LLM rewrite                                                                #
# ═══════════════════════════════════════════════════════════════════════════ #

async def _rewrite_jd(chain, jd_text: str) -> tuple:
    """Returns (summary_text, llm_used: bool)."""
    for attempt in range(3):
        try:
            result = await asyncio.wait_for(
                chain.ainvoke({"jd": jd_text[:3000]}),
                timeout=30,
            )
            if result and len(result.strip()) > 20:
                return result.strip(), True
        except asyncio.TimeoutError:
            logger.warning(f"LLM attempt {attempt+1} timed out")
        except Exception as e:
            logger.warning(f"LLM attempt {attempt+1} failed: {e}")
        await asyncio.sleep(2 ** attempt)

    logger.warning("All LLM retries failed — using raw text.")
    return jd_text[:2000], False


# ═══════════════════════════════════════════════════════════════════════════ #
#  Fetch single job's full details                                            #
# ═══════════════════════════════════════════════════════════════════════════ #

async def _fetch_job_details(context, link: str, jd_chain) -> dict:
    """Open job page, extract everything in one JS call, rewrite JD via LLM."""
    details = {
        "jd_summary":   "(Could not fetch)",
        "jd_llm_used":  False,
        "ctc":          "Not mentioned",
        "apply_type":   "unknown",
        "apply_status": "unknown",
    }
    page = await context.new_page()
    try:
        ok = await _goto(page, link)
        if not ok:
            return details

        await asyncio.sleep(1.5)

        data = await _safe(page.evaluate(_JS_EXTRACT_JD_PAGE), default={}, label="jd_page_js")

        if not data:
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

        # JD text
        jd_raw = data.get("jdText", "")
        if not jd_raw:
            html   = await _safe(page.content(), default="", label="page.content")
            if html:
                soup   = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                lines  = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
                jd_raw = "\n".join(l for l in lines if len(l) >= 40 and "cookie" not in l.lower())

        if jd_raw:
            summary, llm_used = await _rewrite_jd(jd_chain, jd_raw)
            details["jd_summary"]  = summary
            details["jd_llm_used"] = llm_used
        else:
            details["jd_summary"] = "(Empty page)"

    except Exception as e:
        logger.error(f"_fetch_job_details unexpected: {e}")
    finally:
        await _safe(page.close(), label="page.close")

    return details


# ═══════════════════════════════════════════════════════════════════════════ #
#  MAIN PUBLIC GENERATOR                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

async def fetch_jobs(
    roles:            list   = None,
    filters:          dict   = None,
    max_jobs:         int    = 10,
    include_filtered: bool   = False,
) -> AsyncGenerator[dict, None]:
    """
    Async generator — yields one fully-enriched job dict per iteration.

    Parameters
    ----------
    roles            : list of Naukri role slugs to search.
                       Defaults to DEFAULT_ROLES if None.
    filters          : dict of filter criteria (see DEFAULT_FILTERS above).
                       Keys not provided fall back to DEFAULT_FILTERS.
    max_jobs         : stop after yielding this many *passing* jobs.
                       The generator paginates automatically.
    include_filtered : if True, also yield jobs that failed filters
                       (they have filter_status starting with "filtered_out:").

    Yields
    ------
    dict with keys:
        title, company, location, experience, salary_card, ctc,
        apply_type, apply_status, jd_summary, jd_llm_used,
        filter_status, role_category, page_no, link, scraped_at
    """
    _roles   = roles   or DEFAULT_ROLES
    _filters = {**DEFAULT_FILTERS, **(filters or {})}

    # ── LLM chain (built once, reused for every job) ───────────────── #
    llm = create_llm(temperature=0)
    prompt = PromptTemplate(
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
    jd_chain = prompt | llm | StrOutputParser()

    # ── Browser setup ──────────────────────────────────────────────── #
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

        # Block images/fonts — cuts load time ~40%
        _blocked = re.compile(
            r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|otf)(\?|$)", re.I
        )
        async def _block_handler(route, request):
            if _blocked.search(request.url):
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", _block_handler)

        # ── Login ─────────────────────────────────────────────────── #
        login_page = await context.new_page()
        await _login(login_page)
        await login_page.close()

        # ── Scrape ────────────────────────────────────────────────── #
        listing_page = await context.new_page()
        yielded = 0   # count of *passing* jobs yielded

        for role in _roles:

            if yielded >= max_jobs:
                break

            page_no = 1

            while yielded < max_jobs:

                # ── Build listing URL with page number ─────────────── #
                url = BASE_URL.format(role=role)
                if page_no > 1:
                    url = f"{url}?pageNo={page_no}"

                logger.info(f"── {role}  page {page_no}  →  {url}")

                ok = await _goto(listing_page, url)
                if not ok:
                    break

                found = await _wait_sel(listing_page, "div.cust-job-tuple")
                if not found:
                    logger.info(f"  No cards on page {page_no} for [{role}] — moving to next role")
                    break

                # Scroll to trigger lazy-load
                for _ in range(3):
                    await _safe(listing_page.mouse.wheel(0, 3000), label="scroll")
                    await asyncio.sleep(1.0)

                cards = await _safe(
                    listing_page.evaluate(_JS_EXTRACT_CARDS),
                    default=[],
                    label="extract_cards",
                )

                if not cards:
                    logger.info(f"  JS returned 0 cards for [{role}] page {page_no}")
                    break

                logger.info(f"  {len(cards)} cards extracted")

                for card in cards:

                    if yielded >= max_jobs:
                        break

                    card["role_category"] = role
                    card["page_no"]       = page_no

                    logger.info(
                        f"  ↳ [{yielded+1}] {card['title']} @ {card['company']}"
                    )

                    # Fetch full details
                    details = await _fetch_job_details(context, card["link"], jd_chain)
                    card.update(details)

                    # Best CTC: detail page wins, listing card as fallback
                    if not card.get("ctc") or card["ctc"] == "Not mentioned":
                        card["ctc"] = card.get("salary_card", "Not mentioned")

                    card["scraped_at"] = datetime.now().isoformat()

                    # Filter check
                    passes, reason = _passes_filters(card, _filters)
                    card["filter_status"] = "passed" if passes else f"filtered_out: {reason}"

                    if passes:
                        yielded += 1
                        logger.info(
                            f"  ✅ [{yielded}/{max_jobs}] "
                            f"apply={card['apply_type']} "
                            f"status={card['apply_status']} "
                            f"ctc={card['ctc']}"
                        )
                        yield card

                    else:
                        logger.info(f"  ⛔ FILTERED: {reason}")
                        if include_filtered:
                            yield card

                page_no += 1   # paginate to next listing page for this role

        await browser.close()


# ═══════════════════════════════════════════════════════════════════════════ #
#  Quick standalone test                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

async def _demo():
    count = 0
    async for job in fetch_jobs(
        roles=["ai-engineer", "sde"],
        filters={
            # "min_ctc_lpa":   10,
            # "max_ctc_lpa":   40,
            # "min_exp_years": 1,
            # "max_exp_years": 5,
            # "apply_type":    "easy_apply",
            # "locations":     ["Bengaluru"],
            "skip_already_applied": True,
        },
        max_jobs=5,
    ):
        count += 1
        print(f"\n{'='*60}")
        print(f"#{count}  {job['title']}  |  {job['company']}")
        print(f"    Location   : {job['location']}")
        print(f"    Experience : {job['experience']}")
        print(f"    CTC        : {job['ctc']}")
        print(f"    Apply Type : {job['apply_type']}")
        print(f"    Applied?   : {job['apply_status']}")
        print(f"    LLM used?  : {job['jd_llm_used']}")
        print(f"    Link       : {job['link']}")
        print(f"\n{job['jd_summary'][:400]}...")


if __name__ == "__main__":
    asyncio.run(_demo())