from typing import Any, Dict, List

from modules.core.cv.cv_engine import CVEngine

from ..base import BaseAgent
from ..models import AgentResult


class ResumeRewriteAgent(BaseAgent):
    name = "resume_rewrite"

    def __init__(self) -> None:
        self.cv_engine = CVEngine()

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        jobs: List[Dict[str, Any]] = payload.get("jobs") or []
        default_job: Dict[str, Any] = payload.get("job") or {
            "title": "Software Engineer",
            "skills_required": ["Python", "LLM", "LangChain"],
        }

        if not jobs:
            jobs = [default_job]

        output: List[Dict[str, Any]] = []
        for job in jobs:
            cv_path = await self.cv_engine.generate_cv_for_job(job)
            output.append({"job": job, "cv_path": str(cv_path)})

        return AgentResult(
            agent=self.name,
            success=True,
            data={"generated": output, "count": len(output)},
        )
