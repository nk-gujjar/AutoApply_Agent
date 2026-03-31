from typing import Any, Dict

from modules.core.appliers.external_apply import ExternalApplier

from ..base import BaseAgent
from ..models import AgentResult


class ExternalApplierAgent(BaseAgent):
    name = "external_applier"

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        dry_run = bool(payload.get("dry_run", False))
        applier = ExternalApplier(dry_run=dry_run)
        await applier.run()

        return AgentResult(
            agent=self.name,
            success=True,
            data={"dry_run": dry_run},
        )
