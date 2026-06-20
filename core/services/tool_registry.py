"""Tool Registry — dynamic tool registration and dispatch.

Usage:
    registry = ToolRegistry()
    registry.register("write_file", handler=my_write_fn, description="Write content to a file")
    registry.register("run_command", handler=my_run_fn, description="Execute a shell command")

    result = registry.execute("write_file", {"path": "test.txt", "content": "hello"})
    # Returns {"summary": "...", "success": True} or {"summary": "Tool not found: ...", "success": False}
"""

from typing import Callable


class ToolNotFoundError(KeyError):
    """Raised when AI calls an unregistered tool."""
    pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, handler: Callable, description: str = "") -> None:
        self._tools[name] = {
            "handler": handler,
            "description": description,
        }

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def list_tools(self) -> list[dict]:
        return [
            {"name": k, "description": v["description"]}
            for k, v in self._tools.items()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def execute(self, name: str, params: dict) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self._tools.keys())
            raise ToolNotFoundError(
                f"Tool '{name}' không tồn tại trong Registry. "
                f"Các tool khả dụng: [{available}]"
            )
        return tool["handler"](params)
