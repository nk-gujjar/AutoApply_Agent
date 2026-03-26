from typing import Any, Dict, List

from modules.core.appliers.naukri_applier import NaukriApplier, load_jobs_from_file
from modules.core.config.settings import config

from ..base import BaseAgent
from ..models import AgentResult


class NaukriApplierAgent(BaseAgent):
    name = "naukri_applier"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        jobs: List[Dict[str, Any]] = payload.get("jobs") or []
        file_path = payload.get("file_path", "./data/naukri_jobs.txt")

        if not jobs:
            jobs = load_jobs_from_file(file_path)

        applier = NaukriApplier(email=config.NAUKRI_EMAIL, password=config.NAUKRI_PASSWORD)
        await applier.run(jobs)

        return AgentResult(
            agent=self.name,
            success=True,
            data={"count": len(jobs), "source": "payload" if payload.get("jobs") else file_path},
        )
