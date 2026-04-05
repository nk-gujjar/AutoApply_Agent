import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from telethon import TelegramClient
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

from modules.core.config.settings import config, create_llm, logger


class TelegramJobScraper:
    """Fetches Telegram channel posts and parses them into structured job records."""

    def __init__(self, output_file: str | None = None, session_name: str | None = None):
        self._validate_telegram_config()

        session = (session_name or config.TELEGRAM_SESSION_NAME or "tg_user_session").strip()
        if not session:
            session = "tg_user_session"

        self.client = TelegramClient(
            session=session,
            api_id=config.TELEGRAM_API_ID,
            api_hash=config.TELEGRAM_API_HASH,
        )

        self.output_file = Path(output_file) if output_file else config.DATA_DIR / "telegram_jobs.txt"
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self.llm = create_llm(temperature=0)

    def _validate_telegram_config(self) -> None:
        missing = []
        if not config.TELEGRAM_API_ID:
            missing.append("TELEGRAM_API_ID")
        if not config.TELEGRAM_API_HASH:
            missing.append("TELEGRAM_API_HASH")

        if missing:
            raise ValueError(
                "Missing Telegram configuration values: " + ", ".join(missing)
            )

    @staticmethod
    def _extract_urls(message: Any) -> List[str]:
        urls: List[str] = []

        if getattr(message, "entities", None):
            for entity in message.entities:
                if isinstance(entity, MessageEntityTextUrl):
                    urls.append(entity.url)
                elif isinstance(entity, MessageEntityUrl):
                    start = entity.offset
                    end = entity.offset + entity.length
                    urls.append((message.raw_text or "")[start:end])

        raw_text = getattr(message, "raw_text", "") or ""
        found = re.findall(r"https?://[^\s\)\]\>\"\']+", raw_text)
        urls.extend(found)

        deduped: List[str] = []
        seen = set()
        for url in urls:
            if url and url not in seen:
                seen.add(url)
                deduped.append(url)

        return deduped

    def _prompt(self, message: str) -> str:
        return (
            "You are a job-posting parser for a recruitment agent.\n"
            "Given the raw Telegram message below, extract all jobs present in it.\n"
            "If one message contains multiple jobs, create one object per job.\n"
            "If a field is missing for a job, use N/A.\n\n"
            "Return ONLY valid JSON in this exact schema (no markdown, no extra text):\n"
            "{\"jobs\":[{\"role\":\"...\",\"company\":\"...\",\"location\":\"...\",\"experience\":\"...\",\"key_skills\":\"...\",\"tech_stack\":\"...\",\"ctc\":\"...\",\"apply_link\":\"...\",\"summary\":\"...\"}]}\n\n"
            f"Raw Message:\n{message}"
        )

    async def _parse_message(self, raw_text: str) -> List[Dict[str, str]]:
        for attempt in range(3):
            try:
                prompt = self._prompt(raw_text[:3000])
                response = await self.llm.ainvoke(prompt)
                text = response.content if hasattr(response, "content") else str(response)

                if text and len(text.strip()) > 20:
                    parsed_jobs = self._struct_to_jobs(text.strip())
                    if parsed_jobs:
                        return parsed_jobs
            except Exception as exc:
                logger.warning("Telegram parse retry %s failed: %s", attempt + 1, exc)
                await asyncio.sleep(2)

        return [self._fallback_job(raw_text)]

    @staticmethod
    def _fallback_job(raw_text: str) -> Dict[str, str]:
        return {
            "role": "N/A",
            "company": "N/A",
            "location": "N/A",
            "experience": "N/A",
            "key_skills": "N/A",
            "tech_stack": "N/A",
            "ctc": "N/A",
            "apply_link": "N/A",
            "summary": raw_text[:400],
        }

    @classmethod
    def _struct_to_jobs(cls, llm_output: str) -> List[Dict[str, str]]:
        text = llm_output.strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return []

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []

        normalized: List[Dict[str, str]] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue

            normalized.append(
                {
                    "role": str(item.get("role") or "N/A"),
                    "company": str(item.get("company") or "N/A"),
                    "location": str(item.get("location") or "N/A"),
                    "experience": str(item.get("experience") or "N/A"),
                    "key_skills": str(item.get("key_skills") or "N/A"),
                    "tech_stack": str(item.get("tech_stack") or "N/A"),
                    "ctc": str(item.get("ctc") or "N/A"),
                    "apply_link": str(item.get("apply_link") or "N/A"),
                    "summary": str(item.get("summary") or "N/A"),
                }
            )

        return normalized

    async def save_job(self, job: Dict[str, Any]) -> None:
        with self.output_file.open("a", encoding="utf-8") as handle:
            handle.write("=================================\n")
            handle.write(f"Channel:    @{job['channel']}\n")
            handle.write(f"Message ID: {job['message_id']}\n")
            handle.write(f"Job Index:  {job.get('message_job_index', 1)}\n")
            handle.write(f"Scraped At: {job['scraped_at']}\n\n")

            handle.write(f"Role:       {job['role']}\n")
            handle.write(f"Company:    {job['company']}\n")
            handle.write(f"Location:   {job['location']}\n")
            handle.write(f"Experience: {job['experience']}\n")
            handle.write(f"Key Skills: {job['key_skills']}\n")
            handle.write(f"Tech Stack: {job['tech_stack']}\n")
            handle.write(f"CTC:        {job['ctc']}\n")
            handle.write(f"Apply Link: {job['apply_link']}\n\n")

            handle.write(f"Summary:\n{job['summary']}\n")
            handle.write("=================================\n\n")

    async def fetch_messages(self, channel: str, limit: int = 20) -> List[Dict[str, Any]]:
        channel_name = (channel or "").strip().lstrip("@")
        if not channel_name:
            raise ValueError("Telegram channel is required")

        jobs: List[Dict[str, Any]] = []

        async with self.client:
            if config.PHONE_NUMBER:
                await self.client.start(phone=config.PHONE_NUMBER)

            me = await self.client.get_me()
            if getattr(me, "bot", False):
                raise ValueError(
                    "Current Telegram session is authenticated as a bot. "
                    "Use a user account session (phone OTP login) by changing TELEGRAM_SESSION_NAME "
                    "or removing existing session files and retrying."
                )

            entity = await self.client.get_entity(channel_name)
            logger.info("Fetching %s Telegram messages from @%s", limit, channel_name)

            async for message in self.client.iter_messages(entity, limit=limit):
                raw_text = (getattr(message, "raw_text", "") or "").strip()
                if len(raw_text) < 30:
                    continue

                urls = self._extract_urls(message)
                parsed_jobs = await self._parse_message(raw_text)

                for index, parsed in enumerate(parsed_jobs, start=1):
                    if parsed.get("apply_link") in {"N/A", "", None} and urls:
                        url_index = min(index - 1, len(urls) - 1)
                        parsed["apply_link"] = urls[url_index]

                    job = {
                        **parsed,
                        "raw_text": raw_text,
                        "urls": urls,
                        "message_id": message.id,
                        "message_job_index": index,
                        "channel": channel_name,
                        "scraped_at": datetime.utcnow().isoformat(),
                    }

                    await self.save_job(job)
                    jobs.append(job)

        logger.info("Total Telegram jobs parsed from @%s: %s", channel_name, len(jobs))
        return jobs

    async def run(self, channel: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self.fetch_messages(channel=channel, limit=limit)
