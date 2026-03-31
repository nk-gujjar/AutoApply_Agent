from typing import Any, Awaitable, Callable, Dict, List

MCPTool = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class MCPServer:
    def __init__(self) -> None:
        self._tools: Dict[str, MCPTool] = {}

    def register_tool(self, name: str, handler: MCPTool) -> None:
        self._tools[name] = handler

    async def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    async def call_tool(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            return {"ok": False, "error": f"Unknown MCP tool: {name}"}

        try:
            result = await self._tools[name](payload)
            return {"ok": True, "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
