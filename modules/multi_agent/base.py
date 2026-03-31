from abc import ABC, abstractmethod
from typing import Any, Dict

from .models import AgentResult


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
