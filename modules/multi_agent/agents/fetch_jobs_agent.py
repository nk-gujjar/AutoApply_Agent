from typing import Any, Dict, List

from modules.core.scrapers.fetch_job import fetch_jobs
from modules.core.scrapers.file_loader import load_cached_jobs
from modules.core.config.settings import logger

from ..base import BaseAgent
from ..models import AgentResult


class FetchJobsAgent(BaseAgent):
    name = "fetch_jobs"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        roles = payload.get("roles")
        filters = payload.get("filters")
        max_jobs = int(payload.get("max_jobs", 10))
        include_filtered = bool(payload.get("include_filtered", False))
        use_cache = bool(payload.get("use_cache", True))  # Default: use cache first

        jobs: List[Dict[str, Any]] = []
        source = "cache"

        # Try to load from cache first
        if use_cache:
            try:
                cached_jobs = load_cached_jobs(max_jobs=max_jobs)
                if cached_jobs:
                    jobs = cached_jobs
                    logger.info(f"✅ Loaded {len(jobs)} jobs from cache file")
                else:
                    logger.info("Cache file empty or not found, falling back to live scraping...")
                    source = "live_scrape"
                    jobs = await self._scrape_live(roles, filters, max_jobs, include_filtered)
            except Exception as exc:
                logger.warning(f"Failed to load from cache: {exc}, falling back to live scraping...")
                source = "live_scrape"
                jobs = await self._scrape_live(roles, filters, max_jobs, include_filtered)
        else:
            logger.info("Cache disabled, using live scraping...")
            source = "live_scrape"
            jobs = await self._scrape_live(roles, filters, max_jobs, include_filtered)

        return AgentResult(
            agent=self.name,
            success=True,
            data={
                "jobs": jobs,
                "count": len(jobs),
                "source": source,  # Track whether jobs came from cache or live scrape
            },
        )

    async def _scrape_live(
        self,
        roles: List[str] = None,
        filters: Dict[str, Any] = None,
        max_jobs: int = 10,
        include_filtered: bool = False,
    ) -> List[Dict[str, Any]]:
        """Perform live scraping from Naukri website."""
        jobs: List[Dict[str, Any]] = []
        async for job in fetch_jobs(
            roles=roles,
            filters=filters,
            max_jobs=max_jobs,
            include_filtered=include_filtered,
        ):
            jobs.append(job)
        return jobs
