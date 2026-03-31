from typing import Any, Dict, List

from .server import MCPServer


class MCPClient:
    def __init__(self, server: MCPServer) -> None:
        self.server = server

    async def list_tools(self) -> List[str]:
        return await self.server.list_tools()

    async def call_tool(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.server.call_tool(name, payload)
