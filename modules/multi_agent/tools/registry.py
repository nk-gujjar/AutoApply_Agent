from typing import Any, Awaitable, Callable, Dict, List

ToolCallable = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolCallable] = {}

    def register(self, name: str, tool: ToolCallable) -> None:
        self._tools[name] = tool

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    async def invoke(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered")
        return await self._tools[name](**kwargs)
