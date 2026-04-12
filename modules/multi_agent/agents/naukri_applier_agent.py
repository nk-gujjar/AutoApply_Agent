from typing import Any, Dict, List
from pathlib import Path

from modules.core.appliers.naukri_applier import NaukriApplier
from modules.core.scrapers.file_loader import parse_naukri_jobs_file
from modules.core.config.settings import config, logger

from ..base import BaseAgent
from ..models import AgentResult


class NaukriApplierAgent(BaseAgent):
    name = "naukri_applier"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        jobs: List[Dict[str, Any]] = payload.get("jobs") or []
        file_path = payload.get("file_path", str(config.JOBS_DIR / "naukri_jobs.txt"))

        if not jobs:
            # Rehydrate from cache if jobs were stored by fetch_jobs
            jobs = parse_naukri_jobs_file(Path(file_path))

        # But we only want to apply up to the `max_jobs` if it was specified
        max_jobs = payload.get("max_jobs")
        if max_jobs and isinstance(max_jobs, int) and len(jobs) > max_jobs:
            jobs = jobs[:max_jobs]

        if not jobs:
            return AgentResult(
                agent=self.name,
                success=False,
                error="No jobs found to apply. Fetch jobs first.",
            )

        logger.info("━" * 55)
        logger.info(f"  🚀 NaukriApplierAgent: Starting Easy Apply for {len(jobs)} jobs")
        logger.info("━" * 55)

        applier = NaukriApplier(email=config.NAUKRI_EMAIL, password=config.NAUKRI_PASSWORD)
        summary = await applier.run(jobs)

        # Build human-readable summary for chat
        summary_text = (
            f"✅ Application Summary\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Applied:            {summary.get('applied', 0)}\n"
            f"Already Applied:    {summary.get('already_applied', 0)}\n"
            f"Skipped (External): {summary.get('skipped_external', 0)}\n"
            f"Skipped (Blocked):  {summary.get('skipped_blocked', 0)}\n"
            f"Failed:             {summary.get('failed', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Processed:    {summary.get('total', 0)}"
        )

        return AgentResult(
            agent=self.name,
            success=True,
            data={
                "summary": summary,
                "summary_text": summary_text,
                "source": "payload" if payload.get("jobs") else file_path,
            },
        )
