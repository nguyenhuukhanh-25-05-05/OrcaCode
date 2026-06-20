import re
from pathlib import Path
from typing import Optional


class WorldModel:
    """Maps user tasks to affected components, dependencies, and risks."""

    COMMON_PATTERNS = {
        "login": {"files": ["auth", "login", "session", "user"], "type": "feature"},
        "auth": {"files": ["auth", "login", "register", "oauth", "jwt", "session"], "type": "feature"},
        "api": {"files": ["api", "route", "endpoint", "controller"], "type": "backend"},
        "database": {"files": ["db", "database", "model", "migration", "schema"], "type": "backend"},
        "ui": {"files": ["view", "component", "page", "template", "layout"], "type": "frontend"},
        "test": {"files": ["test", "spec", "mock"], "type": "testing"},
        "deploy": {"files": ["docker", "ci", "cd", "deploy", "action"], "type": "infra"},
    }

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)

    def analyze(self, task: str, context: Optional[dict] = None) -> dict:
        """Analyze a task and return world model: affected components, dependencies, risks."""
        task_lower = task.lower()
        context = context or {}

        # 1. Identify affected components
        components = self._identify_components(task_lower)
        dependencies = self._find_dependencies(components)
        risks = self._assess_risks(task_lower, components)

        return {
            "task": task,
            "components": components,
            "dependencies": dependencies,
            "risks": risks,
            "scope": self._estimate_scope(components),
        }

    def _identify_components(self, task: str) -> list[dict]:
        found = []
        for keyword, info in self.COMMON_PATTERNS.items():
            if keyword in task:
                found.append({
                    "name": keyword,
                    "type": info["type"],
                    "likely_files": info["files"],
                    "confidence": "high" if task.count(keyword) > 1 else "medium",
                })
        return found

    def _find_dependencies(self, components: list[dict]) -> list[str]:
        deps = set()
        for comp in components:
            if comp["type"] == "frontend":
                deps.add("backend API")
            elif comp["type"] == "backend":
                deps.add("database")
            elif comp["type"] == "feature":
                deps.update(["frontend UI", "backend logic", "database"])
        return list(deps)

    def _assess_risks(self, task: str, components: list[dict]) -> list[dict]:
        risks = []
        high_risk_keywords = ["delete", "xóa", "drop", "reset", "force", "override"]
        for kw in high_risk_keywords:
            if kw in task:
                risks.append({
                    "level": "high",
                    "description": f"Phát hiện từ khóa '{kw}' — có thể gây mất dữ liệu",
                })
        if len(components) >= 3:
            risks.append({
                "level": "medium",
                "description": f"Nhiều component ảnh hưởng ({len(components)}) — cần kiểm tra side effects",
            })
        if not risks:
            risks.append({
                "level": "low",
                "description": "Không phát hiện rủi ro đặc biệt",
            })
        return risks

    def _estimate_scope(self, components: list[dict]) -> str:
        if len(components) == 0:
            return "unknown"
        elif len(components) <= 1:
            return "small"
        elif len(components) <= 3:
            return "medium"
        else:
            return "large"

    def components_summary(self, components: list[dict]) -> str:
        if not components:
            return "Không xác định được component ảnh hưởng"
        lines = []
        for c in components:
            lines.append(f"- {c['name']} ({c['type']}, {c['confidence']})")
            lines.append(f"  Files: {', '.join(c['likely_files'])}")
        return "\n".join(lines)

    def dep_summary(self, deps: list[str]) -> str:
        if not deps:
            return "Không có dependency đặc biệt"
        return "\n".join(f"- {d}" for d in deps)

    def risk_summary(self, risks: list[dict]) -> str:
        if not risks:
            return "Không phát hiện rủi ro"
        return "\n".join(f"[{r['level'].upper()}] {r['description']}" for r in risks)