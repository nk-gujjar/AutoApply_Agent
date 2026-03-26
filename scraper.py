import asyncio
import re
import logging
from typing import List, Set
from datetime import datetime

from telethon import TelegramClient
import httpx
from bs4 import BeautifulSoup

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import config, create_llm

logger = logging.getLogger(__name__)


class TelegramScraper:

    def __init__(self):

        self.client = TelegramClient(
            "autoapply_session",
            config.TELEGRAM_API_ID,
            config.TELEGRAM_API_HASH
        )

        self.ignore_domains = [
            "youtube.com",
            "youtu.be",
            "whatsapp",
            "wa.me",
            "t.me",
            "telegram"
        ]

        self.llm = create_llm(temperature=0)

        # ---------- LLM prompt ---------- #

        self.jd_prompt = PromptTemplate(
            input_variables=["content"],
            template="""
You are analyzing a webpage for job application information.

If the page contains another job application link return:

LINK: <url>

If the page already contains the job description return:

JD:
<clean job description only>

Text:
{content}
"""
        )

        self.jd_chain = self.jd_prompt | self.llm | StrOutputParser()

    # ------------------------------------------------ #

    async def connect(self):
        await self.client.start()
        logger.info("Connected to Telegram")

    # ------------------------------------------------ #

    def extract_links(self, text: str) -> List[str]:

        urls = re.findall(r"https?://[^\s)>\]]+", text)

        valid_links = []

        for url in urls:
            if any(domain in url.lower() for domain in self.ignore_domains):
                continue

            valid_links.append(url)

        return list(set(valid_links))

    # ------------------------------------------------ #

    async def fetch_page(self, url):

        try:

            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True
            ) as client:

                r = await client.get(url)

            return r.text

        except Exception as e:

            logger.error(f"Failed to fetch {url}: {e}")
            return ""

    # ------------------------------------------------ #

    def clean_text(self, html):

        soup = BeautifulSoup(html, "html.parser")

        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.decompose()

        text = soup.get_text(separator="\n")

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        cleaned = []

        for line in lines:

            if len(line) < 40:
                continue

            if any(x in line.lower() for x in [
                "cookie",
                "privacy",
                "sign in",
                "login",
                "share",
                "follow",
                "advertisement"
            ]):
                continue

            cleaned.append(line)

        return "\n".join(cleaned[:120])

    # ------------------------------------------------ #

    async def analyze_page_with_llm(self, text):

        try:

            result = await self.jd_chain.ainvoke({
                "content": text
            })

            result = result.strip()

            if result.startswith("LINK:"):
                link = result.replace("LINK:", "").strip()
                return {"type": "link", "value": link}

            if result.startswith("JD:"):
                jd = result.replace("JD:", "").strip()
                return {"type": "jd", "value": jd}

        except Exception as e:

            logger.error(f"LLM analysis failed: {e}")

        return {"type": "jd", "value": text}

    # ------------------------------------------------ #

    async def resolve_final_job(self, url, depth=0):

        if depth > 2:
            return None

        html = await self.fetch_page(url)

        if not html:
            return None

        text = self.clean_text(html)

        result = await self.analyze_page_with_llm(text)

        if result["type"] == "link":

            new_link = result["value"]

            if new_link.startswith("http"):

                return await self.resolve_final_job(new_link, depth + 1)

        return {
            "apply_link": url,
            "job_description": result["value"]
        }

    # ------------------------------------------------ #

    async def process_link(self, link):

        job = await self.resolve_final_job(link)

        if not job:
            return None

        job["scraped_at"] = datetime.now().isoformat()

        return job

    # ------------------------------------------------ #

    async def scrape_channel(self, channel):

        jobs = []

        entity = await self.client.get_entity(channel)

        messages = await self.client.get_messages(entity, limit=5)

        for message in messages:

            if not message.text:
                continue

            links = self.extract_links(message.text)

            if not links:
                continue

            tasks = [self.process_link(link) for link in links]

            results = await asyncio.gather(*tasks)

            for job in results:

                if job:

                    jobs.append(job)

                    await self.save_job(job)

        return jobs

    # ------------------------------------------------ #

    async def save_job(self, job):

        file = config.DATA_DIR / "jobs_test.txt"

        with open(file, "a", encoding="utf-8") as f:

            f.write("================================\n")

            f.write(f"Apply Link:\n{job['apply_link']}\n\n")

            f.write("Job Description:\n")

            f.write(job["job_description"])

            f.write("\n================================\n\n")

    # ------------------------------------------------ #

    async def run(self):

        all_jobs = []

        for channel in config.TARGET_CHANNELS:

            if channel.strip():

                jobs = await self.scrape_channel(channel)

                all_jobs.extend(jobs)

        print(f"\nJobs Found: {len(all_jobs)}")


# ------------------------------------------------ #

async def main():

    scraper = TelegramScraper()

    await scraper.connect()

    await scraper.run()

    await scraper.client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())



# """
# Telegram Scraper Module
# Uses Telethon to monitor Telegram channels for job postings
# Filters messages based on specified criteria
# """

# import asyncio
# import re
# import logging
# from typing import List, Dict, Optional, Set
# from datetime import datetime, timedelta
# from telethon import TelegramClient, events
# from telethon.tl.types import Message
# import json

# from config import config

# logger = logging.getLogger(__name__)

# class TelegramScraper:
#     """Scraper to monitor Telegram channels for job postings"""
    
#     def __init__(self):
#         self.client = TelegramClient(
#             'autoapply_session',
#             config.TELEGRAM_API_ID,
#             config.TELEGRAM_API_HASH
#         )
#         self.bot_token = config.TELEGRAM_BOT_TOKEN

#         self.processed_messages: Set[int] = set()
#         self.job_keywords = self._compile_job_keywords()
#         self.experience_patterns = self._compile_experience_patterns()
#         self.ctc_patterns = self._compile_ctc_patterns()
        
#     def _compile_job_keywords(self) -> List[re.Pattern]:
#         """Compile regex patterns for job roles"""
#         patterns = []
#         for role in config.TARGET_ROLES:
#             # Create case-insensitive patterns for job roles
#             pattern = re.compile(rf'\b{re.escape(role.strip())}\b', re.IGNORECASE)
#             patterns.append(pattern)
#         return patterns
    
#     def _compile_experience_patterns(self) -> List[re.Pattern]:
#         """Compile regex patterns for experience requirements"""
#         patterns = [
#             re.compile(r'(\d+)[\s\-\+]*(?:to|-)?\s*(\d+)?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)', re.IGNORECASE),
#             re.compile(r'(\d+)\+?\s*(?:years?|yrs?)', re.IGNORECASE),
#             re.compile(r'(?:experience|exp)[\s\:]*(\d+)[\s\-\+]*(?:to|-)?\s*(\d+)?\s*(?:years?|yrs?)', re.IGNORECASE),
#             re.compile(r'fresher|freshers|0\s*(?:years?|yrs?)', re.IGNORECASE),
#         ]
#         return patterns
    
#     def _compile_ctc_patterns(self) -> List[re.Pattern]:
#         """Compile regex patterns for CTC/salary requirements"""
#         patterns = [
#             re.compile(r'(\d+)[\s\-]*(?:to|-)?\s*(\d+)?\s*(?:lpa|lakhs?|L)', re.IGNORECASE),
#             re.compile(r'(?:ctc|salary|package)[\s\:]*(\d+)[\s\-]*(?:to|-)?\s*(\d+)?\s*(?:lpa|lakhs?|L)', re.IGNORECASE),
#             re.compile(r'₹[\s]*(\d+)[\s\-]*(?:to|-)?\s*(\d+)?\s*(?:lpa|lakhs?|L)', re.IGNORECASE),
#         ]
#         return patterns
    
#     async def connect(self):
#         """Connect to Telegram using bot token"""
#         try:
#             await self.client.start()
#             logger.info("Connected to Telegram successfully using BOT TOKEN")
#             return True
#         except Exception as e:
#             logger.error(f"Failed to connect to Telegram: {e}")
#             return False
    
#     async def disconnect(self):
#         """Disconnect from Telegram"""
#         await self.client.disconnect()
#         logger.info("Disconnected from Telegram")
    
#     def extract_job_info(self, message_text: str) -> Optional[Dict]:
#         """Extract job information from message text"""
        
#         # Check if message contains job-related keywords
#         role_matches = []
#         for pattern in self.job_keywords:
#             matches = pattern.findall(message_text)
#             role_matches.extend(matches)
        
#         if not role_matches:
#             return None
        
#         # Extract experience requirements
#         experience_info = self._extract_experience(message_text)
        
#         # Extract CTC information
#         ctc_info = self._extract_ctc(message_text)
        
#         # Extract URLs
#         urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message_text)
        
#         # Check if job meets our criteria
#         if not self._meets_criteria(experience_info, ctc_info):
#             return None
        
#         job_info = {
#             'roles': role_matches,
#             'experience': experience_info,
#             'ctc': ctc_info,
#             'urls': urls,
#             'raw_text': message_text,
#             'extracted_at': datetime.now().isoformat()
#         }
        
#         return job_info
    
#     def _extract_experience(self, text: str) -> Dict:
#         """Extract experience requirements from text"""
#         for pattern in self.experience_patterns:
#             matches = pattern.findall(text)
#             if matches:
#                 if isinstance(matches[0], tuple):
#                     min_exp = int(matches[0][0]) if matches[0][0] else 0
#                     max_exp = int(matches[0][1]) if matches[0][1] else min_exp
#                 else:
#                     min_exp = int(matches[0])
#                     max_exp = min_exp
                
#                 return {
#                     'min_years': min_exp,
#                     'max_years': max_exp,
#                     'raw_match': matches[0]
#                 }
        
#         # Check for fresher positions
#         if re.search(r'fresher|freshers|0\s*(?:years?|yrs?)', text, re.IGNORECASE):
#             return {
#                 'min_years': 0,
#                 'max_years': 0,
#                 'raw_match': 'fresher'
#             }
        
#         return {
#             'min_years': None,
#             'max_years': None,
#             'raw_match': None
#         }
    
#     def _extract_ctc(self, text: str) -> Dict:
#         """Extract CTC information from text"""
#         for pattern in self.ctc_patterns:
#             matches = pattern.findall(text)
#             if matches:
#                 if isinstance(matches[0], tuple):
#                     min_ctc = int(matches[0][0]) if matches[0][0] else None
#                     max_ctc = int(matches[0][1]) if matches[0][1] else min_ctc
#                 else:
#                     min_ctc = int(matches[0])
#                     max_ctc = min_ctc
                
#                 return {
#                     'min_lpa': min_ctc,
#                     'max_lpa': max_ctc,
#                     'raw_match': matches[0]
#                 }
        
#         return {
#             'min_lpa': None,
#             'max_lpa': None,
#             'raw_match': None
#         }
    
#     def _meets_criteria(self, experience_info: Dict, ctc_info: Dict) -> bool:
#         """Check if job meets our filtering criteria"""
        
#         # Check experience criteria
#         if experience_info['min_years'] is not None:
#             if experience_info['min_years'] > config.MAX_EXPERIENCE:
#                 return False
#             if experience_info['max_years'] is not None and experience_info['max_years'] < config.MIN_EXPERIENCE:
#                 return False
        
#         # Check CTC criteria
#         if ctc_info['min_lpa'] is not None:
#             if ctc_info['min_lpa'] < config.MIN_CTC:
#                 return False
        
#         return True
    
#     async def scrape_channel_history(self, channel_username: str, days_back: int = 7) -> List[Dict]:
#         """Scrape recent messages from a channel"""
#         jobs = []
        
#         try:
#             entity = await self.client.get_entity(channel_username)
            
#             # Calculate date limit
#             date_limit = datetime.now() - timedelta(days=days_back)
            
#             async for message in self.client.iter_messages(entity, offset_date=date_limit):
#                 if message.message and message.id not in self.processed_messages:
#                     job_info = self.extract_job_info(message.message)
#                     if job_info:
#                         job_info.update({
#                             'channel': channel_username,
#                             'message_id': message.id,
#                             'message_date': message.date.isoformat(),
#                             'message_link': f"https://t.me/{channel_username.replace('@', '')}/{message.id}"
#                         })
#                         jobs.append(job_info)
#                         self.processed_messages.add(message.id)
#                         logger.info(f"Found job posting in {channel_username}: {job_info['roles']}")
            
#         except Exception as e:
#             logger.error(f"Error scraping channel {channel_username}: {e}")
        
#         return jobs
    
#     async def setup_real_time_monitoring(self, channels: List[str]):
#         """Setup real-time monitoring for new messages"""
        
#         @self.client.on(events.NewMessage(chats=channels))
#         async def handle_new_message(event):
#             message = event.message
#             if message.message and message.id not in self.processed_messages:
#                 job_info = self.extract_job_info(message.message)
#                 if job_info:
#                     channel_username = await self.get_channel_username(event.chat_id)
#                     job_info.update({
#                         'channel': channel_username,
#                         'message_id': message.id,
#                         'message_date': message.date.isoformat(),
#                         'message_link': f"https://t.me/{channel_username.replace('@', '')}/{message.id}"
#                     })
                    
#                     # Save job info to file for processing
#                     await self.save_job_info(job_info)
#                     self.processed_messages.add(message.id)
#                     logger.info(f"New job posting detected: {job_info['roles']}")
        
#         logger.info(f"Real-time monitoring setup for channels: {channels}")
    
#     async def get_channel_username(self, chat_id: int) -> str:
#         """Get channel username from chat ID"""
#         try:
#             entity = await self.client.get_entity(chat_id)
#             return f"@{entity.username}" if entity.username else str(chat_id)
#         except:
#             return str(chat_id)
    
#     # async def save_job_info(self, job_info: Dict):
#     #     """Save job information to file"""
#     #     jobs_file = config.DATA_DIR / "pending_jobs.json"
        
#     #     # Load existing jobs
#     #     existing_jobs = []
#     #     if jobs_file.exists():
#     #         try:
#     #             with open(jobs_file, 'r') as f:
#     #                 existing_jobs = json.load(f)
#     #         except:
#     #             existing_jobs = []
        
#     #     # Add new job
#     #     existing_jobs.append(job_info)
        
#     #     # Save updated jobs
#     #     with open(jobs_file, 'w') as f:
#     #         json.dump(existing_jobs, f, indent=2)


#     async def save_job_info(self, job_info: Dict):
#         """Save job information to a TXT file for testing"""

#         jobs_file = config.DATA_DIR / "jobs_test.txt"

#         with open(jobs_file, "a", encoding="utf-8") as f:
#             f.write("========================================\n")
#             f.write(f"Channel: {job_info.get('channel')}\n")
#             f.write(f"Message ID: {job_info.get('message_id')}\n")
#             f.write(f"Roles: {job_info.get('roles')}\n")
#             f.write(f"Experience: {job_info.get('experience')}\n")
#             f.write(f"CTC: {job_info.get('ctc')}\n")
#             f.write(f"Apply Links: {job_info.get('urls')}\n")
#             f.write(f"Message Link: {job_info.get('message_link')}\n")
#             f.write("\nJob Description:\n")
#             f.write(job_info.get("raw_text", ""))
#             f.write("\n========================================\n\n")
    

#     async def run_batch_scraping(self, days_back: int = 7):

#         all_jobs = []

#         for channel in config.TARGET_CHANNELS:
#             if channel.strip():

#                 jobs = await self.scrape_channel_history(channel.strip(), days_back)

#                 for job in jobs:
#                     await self.save_job_info(job)

#                 all_jobs.extend(jobs)

#         logger.info(f"Batch scraping completed. Found {len(all_jobs)} job postings")

#         return all_jobs


#     # async def run_batch_scraping(self, days_back: int = 7) -> List[Dict]:
#     #     """Run batch scraping on all configured channels"""
#     #     all_jobs = []
        
#     #     for channel in config.TARGET_CHANNELS:
#     #         if channel.strip():
#     #             jobs = await self.scrape_channel_history(channel.strip(), days_back)
#     #             all_jobs.extend(jobs)
        
#     #     logger.info(f"Batch scraping completed. Found {len(all_jobs)} job postings")
#     #     return all_jobs

# # Example usage and testing
# async def test_scraper():
#     """Test the scraper functionality"""
#     scraper = TelegramScraper()
    
#     if await scraper.connect():
#         # Test with sample text
#         sample_texts = [
#             "Hiring SDE with 2-3 years experience. CTC: 15-20 LPA. Apply here: https://example.com",
#             "Looking for Python Developer, 0-2 years exp, 12 LPA package",
#             "Senior Software Engineer needed, 5+ years, 25 LPA"
#         ]
        
#         for text in sample_texts:
#             result = scraper.extract_job_info(text)
#             print(f"Text: {text}")
#             print(f"Result: {result}")
#             print("-" * 50)
        
#         await scraper.disconnect()

# # if __name__ == "__main__":
# #     asyncio.run(test_scraper())

# async def main():

#     scraper = TelegramScraper()

#     if await scraper.connect():

#         jobs = await scraper.run_batch_scraping(days_back=7)

#         print("\nJobs Found:\n")

#         for job in jobs:
#             print(job)
#             print("-" * 60)

#         await scraper.disconnect()


# if __name__ == "__main__":
#     asyncio.run(main())