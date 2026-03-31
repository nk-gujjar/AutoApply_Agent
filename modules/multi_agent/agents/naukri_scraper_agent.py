from typing import Any, Dict

from modules.core.scrapers.naukri_scraper import NaukriScraper

from ..base import BaseAgent
from ..models import AgentResult


class NaukriScraperAgent(BaseAgent):
    name = "naukri_scraper"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        max_jobs = int(payload.get("max_jobs", 10))
        filters = payload.get("filters") or {}

        scraper = NaukriScraper(filters=filters, max_jobs=max_jobs)
        jobs = await scraper.run()

        return AgentResult(
            agent=self.name,
            success=True,
            data={"jobs": jobs, "count": len(jobs)},
        )
