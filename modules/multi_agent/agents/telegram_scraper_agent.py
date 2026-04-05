import asyncio
from typing import Any, Dict

from modules.core.config.settings import config
from modules.core.scrapers.telegram_job_scraper import TelegramJobScraper

from ..base import BaseAgent
from ..models import AgentResult


class TelegramScraperAgent(BaseAgent):
    name = "telegram_scraper"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        configured_channels = [ch.strip() for ch in config.TARGET_CHANNELS if ch.strip()]
        default_channel = configured_channels[0] if configured_channels else ""

        channel = str(payload.get("channel") or default_channel).strip()
        limit = int(payload.get("max_jobs", payload.get("limit", 20)))

        if not channel:
            return AgentResult(
                agent=self.name,
                success=False,
                error="Missing required payload field: channel",
            )

        requested_session = str(payload.get("session_name") or "").strip()
        session_candidates = [
            requested_session,
            config.TELEGRAM_SESSION_NAME,
            "tg_user_session",
            "tg_session",
        ]
        session_candidates = [candidate for candidate in session_candidates if candidate]

        unique_sessions = []
        for session_name in session_candidates:
            if session_name not in unique_sessions:
                unique_sessions.append(session_name)

        attempts = 5
        last_error = "Unknown Telegram scraper error"

        for attempt in range(1, attempts + 1):
            session_name = unique_sessions[(attempt - 1) % len(unique_sessions)] if unique_sessions else "tg_user_session"

            try:
                scraper = TelegramJobScraper(session_name=session_name)
                requested_count = max(1, min(limit, 100))
                jobs = await scraper.run(channel=channel, limit=requested_count)
                jobs = jobs[:requested_count]

                return AgentResult(
                    agent=self.name,
                    success=True,
                    data={
                        "jobs": jobs,
                        "count": len(jobs),
                        "channel": channel.lstrip("@"),
                        "source": "telegram",
                        "attempt": attempt,
                        "session_name": session_name,
                    },
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < attempts:
                    await asyncio.sleep(1)

        return AgentResult(
            agent=self.name,
            success=False,
            error=f"Telegram scraping failed after {attempts} retries. Last error: {last_error}",
            data={
                "channel": channel.lstrip("@"),
                "attempts": attempts,
            },
        )
