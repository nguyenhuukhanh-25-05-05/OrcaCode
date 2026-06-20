from core.models import RiskLevel


DESTRUCTIVE_PATTERNS = [
    "rm -rf", "del /f", "rd /s", "format", "diskpart",
    "git reset --hard", "git clean -f", "drop table", "drop database",
    "truncate", "shutdown", "reboot",
]

HIGH_RISK_PATTERNS = [
    "git push --force", "git reset", "git rebase", "git merge",
    "ALTER TABLE", "ALTER COLUMN", "DROP COLUMN",
    "DELETE FROM", "UPDATE SET", "chmod 777", "sudo",
    "npm publish", "pip publish", "twine upload",
]

POTENTIALLY_DESTRUCTIVE_FILE_OPS = [
    "xóa file", "delete file", "xóa toàn bộ", "delete all",
    "rename", "move", "di chuyển", "đổi tên",
]


class RiskChecker:
    def check_command(self, command: str) -> RiskLevel:
        cmd = command.strip().lower()

        for pat in DESTRUCTIVE_PATTERNS:
            if cmd.startswith(pat) or pat in cmd:
                return RiskLevel("critical",
                    f"Lệnh phá hủy: {pat}", requires_approval=True)

        for pat in HIGH_RISK_PATTERNS:
            if pat in cmd:
                return RiskLevel("high",
                    f"Rủi ro cao: {pat}", requires_approval=True)

        return RiskLevel("low", "Lệnh an toàn", requires_approval=False)

    def check_file_operation(self, operation: str, path: str) -> RiskLevel:
        op = operation.strip().lower()
        path_lower = path.strip().lower()

        for pat in POTENTIALLY_DESTRUCTIVE_FILE_OPS:
            if pat in op:
                return RiskLevel("high",
                    f"Thao tác nguy hiểm với file: {pat}", requires_approval=True)

        if any(kw in op for kw in ("tạo", "create", "write", "ghi")):
            return RiskLevel("low",
                f"Tạo/ghi file mới: {path}", requires_approval=False)

        if any(kw in op for kw in ("sửa", "edit", "patch", "update")):
            return RiskLevel("medium",
                f"Sửa file có sẵn: {path}", requires_approval=False)

        if any(kw in op for kw in ("xóa", "delete", "remove")):
            return RiskLevel("high",
                f"Xóa file: {path}", requires_approval=True)

        return RiskLevel("low", f"Thao tác file: {path}", requires_approval=False)

    def check_plan(self, plan_text: str) -> list[RiskLevel]:
        risks = []
        plan = plan_text.strip().lower()

        if "rm -rf" in plan or "del /f" in plan:
            risks.append(RiskLevel("critical", "Phát hiện lệnh xóa dữ liệu trong kế hoạch"))

        if "git reset --hard" in plan:
            risks.append(RiskLevel("high", "Phát hiện git reset --hard — có thể mất commit"))

        if "drop table" in plan or "drop database" in plan:
            risks.append(RiskLevel("critical", "Phát hiện lệnh drop database trong kế hoạch"))

        if not risks:
            risks.append(RiskLevel("low", "Kế hoạch an toàn", requires_approval=False))

        return risks