from typing import Any, Dict, List

from modules.core.cv.cv_engine import CVEngine

from ..base import BaseAgent
from ..models import AgentResult


class ResumeRewriteAgent(BaseAgent):
    name = "resume_rewrite"

    def __init__(self) -> None:
        self.cv_engine = CVEngine()

    def _normalize_job_payload(self, raw_job: Any) -> Dict[str, Any] | None:
        """Normalize a job payload into a dict shape expected by CVEngine."""
        if isinstance(raw_job, dict):
            job = dict(raw_job)
            title = str(job.get("title") or "Software Engineer").strip()
            skills = job.get("skills_required")

            if isinstance(skills, str):
                job["skills_required"] = [
                    item.strip() for item in skills.replace("\n", ",").split(",") if item.strip()
                ]
            elif isinstance(skills, list):
                job["skills_required"] = [str(item).strip() for item in skills if str(item).strip()]
            elif skills is None:
                job["skills_required"] = []
            else:
                skill = str(skills).strip()
                job["skills_required"] = [skill] if skill else []

            job["title"] = title
            return job

        if isinstance(raw_job, str):
            description = raw_job.strip()
            if not description:
                return None
            return {
                "title": "Software Engineer",
                "description": description,
                "skills_required": [],
            }

        return None

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        raw_jobs = payload.get("jobs")
        normalized_jobs: List[Dict[str, Any]] = []

        if isinstance(raw_jobs, list):
            for item in raw_jobs:
                normalized = self._normalize_job_payload(item)
                if normalized:
                    normalized_jobs.append(normalized)
        else:
            normalized = self._normalize_job_payload(raw_jobs)
            if normalized:
                normalized_jobs.append(normalized)

        if not normalized_jobs:
            fallback = self._normalize_job_payload(payload.get("job"))
            if fallback:
                normalized_jobs = [fallback]
            else:
                normalized_jobs = [
                    {
                        "title": "Software Engineer",
                        "skills_required": ["Python", "LLM", "LangChain"],
                    }
                ]

        output: List[Dict[str, Any]] = []
        for job in normalized_jobs:
            cv_path = await self.cv_engine.generate_cv_for_job(job)
            output.append({"job": job, "cv_path": str(cv_path)})

        return AgentResult(
            agent=self.name,
            success=True,
            data={"generated": output, "count": len(output)},
        )
