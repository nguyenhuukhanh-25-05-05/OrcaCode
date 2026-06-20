from core.models import PatchResult, DiffLine
from utils.diff import compute_diff_lines


class PatchViewModel:
    def __init__(self):
        self.current_result: PatchResult | None = None
        self.history: list[PatchResult] = []

    def set_operation(self, result: PatchResult) -> None:
        self.current_result = result
        if result:
            self.history.append(result)

    def last_diff_lines(self) -> list[DiffLine]:
        if not self.current_result or not self.current_result.diff:
            return []
        parts = self.current_result.diff.splitlines(keepends=True)
        old_lines: list[str] = []
        new_lines: list[str] = []
        for line in parts:
            if line.startswith("- "):
                old_lines.append(line[2:])
            elif line.startswith("+ "):
                new_lines.append(line[2:])
        return compute_diff_lines(old_lines, new_lines)

    def has_changes(self) -> bool:
        return self.current_result is not None and self.current_result.success

    def reset(self) -> None:
        self.current_result = None

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.history if r.success)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.history if not r.success)
