import asyncio
import json
import logging
import re
import random
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from modules.core.config.settings import config, create_llm
from modules.core.forms.fill_form import FormFiller

# Setup logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #
#  Prompts & Decision Logic                                          #
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #

PAGE_DECISION_PROMPT = """
You are an AI Job Application Assistant.
CANDIDATE PROFILE:
{profile_summary}

CURRENT URL: {url}
PAGE TEXT (First 3000 chars):
{page_text}

INTERACTIVE ELEMENTS:
{elements}

TASK:
Analyze the page and decide the next step.
1. "cookie": If there's a cookie consent banner (Accept/Agree).
2. "navigate": If you need to click "Apply", "Apply Now", or "Next" to reach the form.
3. "fill_form": If you see actual input fields (Name, Email, Resume Upload).
4. "done": If the page confirms submission or says "Already Applied".

Return ONLY JSON:
{{
  "action": "cookie" | "navigate" | "fill_form" | "done",
  "selector": "CSS selector or exact button text",
  "reason": "Why this step?"
}}
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #
#  Parser for naukri_jobs.txt                                        #
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #

def load_external_jobs(filepath="./data/naukri_jobs.txt"):
    path = Path(filepath)
    if not path.exists():
        logger.error(f"File not found: {filepath}")
        return []

    content = path.read_text(encoding="utf-8")
    blocks = re.compile(r"={10,}", re.MULTILINE).split(content)
    jobs = []

    for block in blocks:
        if "Apply Type" not in block: continue
        job = {}
        for line in block.strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                job[key.strip().lower().replace(" ", "_")] = val.strip()
        
        # Standardize link key
        link = job.get("external_apply_link")
        if link and link != "N/A":
            job["link"] = link
            jobs.append(job)
            
    logger.info(f"Loaded {len(jobs)} jobs from {filepath}")
    return jobs

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #
#  Main Applier Class                                                #
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ #

class ExternalApplier:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.llm = create_llm(temperature=0)
        self.resume_path = Path("./output/resume.pdf")
        self.form_filler = FormFiller(llm=self.llm, resume_path=str(self.resume_path))
        
        # Load profile for LLM context
        p_path = Path("./personal.txt")
        self.profile_summary = p_path.read_text() if p_path.exists() else "Nitesh Kumar, AI Engineer, 3 years exp."

        self.decision_chain = (
            PromptTemplate.from_template(PAGE_DECISION_PROMPT) 
            | self.llm 
            | StrOutputParser()
        )

    async def get_page_elements(self, page):
        """Extracts visible interactive elements for LLM context."""
        return await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button, a, input, select'))
                .filter(el => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                })
                .map(el => `[${el.tagName}] Text: "${el.innerText.trim() || el.placeholder || el.name}" | Sel: ${el.id ? '#'+el.id : '.'+el.className.split(' ')[0]}`)
                .slice(0, 40).join('\\n');
        }""")

    async def apply_to_job(self, context, job):
        page = await context.new_page()
        url = job.get("link")
        
        try:
            logger.info(f"🌐 Opening: {job.get('company')} | {url}")
            # Use 'networkidle' to ensure Cloudflare/WAF finishes checks
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            for step in range(8): # Limit interactions per job
                await asyncio.sleep(2)
                page_text = (await page.content())[:3000]
                elements = await self.get_page_elements(page)

                # Get LLM decision
                resp = await self.decision_chain.ainvoke({
                    "profile_summary": self.profile_summary,
                    "url": page.url,
                    "page_text": page_text,
                    "elements": elements
                })
                
                try:
                    decision = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())
                except:
                    decision = {"action": "fill_form"} # Default fallback

                action = decision.get("action")
                selector = decision.get("selector")

                if action == "done" or "thank you" in page_text.lower():
                    logger.info("✅ Success detected or LLM marked as Done.")
                    return "success"

                elif action in ["cookie", "navigate"]:
                    logger.info(f"🖱️ Action: {action} | Targeting: {selector}")
                    try:
                        # Try finding by selector, then by text
                        target = page.locator(selector).first
                        if await target.count() == 0:
                            target = page.get_by_role("button", name=selector, exact=False).first
                        
                        await target.click(timeout=5000)
                        await page.wait_for_load_state("networkidle")
                    except Exception as e:
                        logger.warning(f"Click failed: {e}")

                elif action == "fill_form":
                    logger.info("📝 Form detected. Starting FormFiller...")
                    filled = await self.form_filler.fill_classic_form(page)
                    if filled:
                        if self.dry_run:
                            logger.info("[Dry Run] Form filled. Stopping.")
                            return "dry_run"
                        await self.form_filler.submit_form(page)
                        await asyncio.sleep(5) # Wait for confirmation page
                    else:
                        logger.warning("FormFiller couldn't find fields.")
                        break

            return "exhausted"

        except Exception as e:
            logger.error(f"❌ Connection/Navigation Error: {e}")
            return "failed"
        finally:
            await page.close()

    async def run(self):
        jobs = load_external_jobs()
        if not jobs: return

        async with async_playwright() as p:
            # Launch with Anti-Bot Arguments
            browser = await p.chromium.launch(
                headless=False, # Must be False for many career sites
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
                ]
            )
            
            # Context with Realistic Identity
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                device_scale_factor=1,
            )

            for job in jobs[:10]:
                await self.apply_to_job(context, job)
                # Random delay to look human
                await asyncio.sleep(random.uniform(5, 12))

            await browser.close()

if __name__ == "__main__":
    applier = ExternalApplier(dry_run=False)
    asyncio.run(applier.run())