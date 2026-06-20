"""Plugin Service - custom tool registry for extensible tool system."""


class ToolDef:
    def __init__(self, name: str, description: str, handler: callable, auto_approve: bool = False):
        self.name = name
        self.description = description
        self.handler = handler
        self.auto_approve = auto_approve


class PluginService:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, name: str, description: str, handler: callable, auto_approve: bool = False):
        self._tools[name] = ToolDef(name, description, handler, auto_approve)

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools.values())

    def format_for_prompt(self) -> str:
        if not self._tools:
            return ""
        lines = ["### 4. Plugin tools:"]
        for t in self._tools.values():
            lines.append(f"<{t.name}/> — {t.description}")
        return "\n".join(lines)

    def execute(self, name: str, **kwargs) -> dict:
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "summary": f"Unknown plugin tool: {name}"}
        try:
            result = tool.handler(**kwargs)
            return {"success": True, "summary": str(result)}
        except Exception as e:
            return {"success": False, "summary": f"Plugin error ({name}): {e}"}
