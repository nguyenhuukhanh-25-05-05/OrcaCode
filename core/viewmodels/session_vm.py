from core.models import SessionState, SearchResult


class SessionViewModel:
    def __init__(self, state: SessionState):
        self._state = state

    @property
    def history(self) -> list[dict]:
        return self._state.conversation_history

    def add_message(self, role: str, content: str) -> None:
        self._state.conversation_history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        self._state.conversation_history.clear()

    def last_message(self) -> str:
        if self._state.conversation_history:
            return self._state.conversation_history[-1].get("content", "")
        return ""

    def set_context(self, results: list[SearchResult]) -> None:
        self._state.current_context = results

    def approve_command(self, command: str) -> None:
        self._state.approved_commands.add(command)

    def is_command_approved(self, command: str) -> bool:
        return command in self._state.approved_commands

    def increment_auto_approve(self) -> None:
        self._state.consecutive_auto_approve += 1

    def reset_auto_approve(self) -> None:
        self._state.consecutive_auto_approve = 0

    def save_execution_context(self, messages: list[dict], modified_files: set[str], mode: str, approved_plan: str = "") -> None:
        self._state.execution_messages = messages
        self._state.execution_modified_files = list(modified_files)
        self._state.execution_mode = mode
        if approved_plan:
            self._state.execution_approved_plan = approved_plan

    def load_execution_context(self) -> dict | None:
        if not self._state.execution_messages:
            return None
        return {
            "messages": self._state.execution_messages,
            "modified_files": set(self._state.execution_modified_files),
            "mode": self._state.execution_mode,
            "approved_plan": self._state.execution_approved_plan,
        }

    def clear_execution_context(self) -> None:
        self._state.execution_messages.clear()
        self._state.execution_modified_files.clear()
        self._state.execution_approved_plan = ""
        self._state.execution_mode = ""

    def summary(self) -> str:
        return (
            f"Session: {len(self._state.conversation_history)} msgs, "
            f"{len(self._state.current_context)} files, "
            f"{len(self._state.approved_commands)} approved, "
            f"{len(self._state.execution_messages)} exec msgs"
        )

    def estimate_tokens(self) -> int:
        text = " ".join(m.get("content", "") for m in self._state.conversation_history)
        return len(text) // 3
