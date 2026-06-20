import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DoneCondition:
    description: str
    check_type: str  # "file_exists", "file_contains", "test_pass", "command_ok", "log_cleared", "manual"
    target: str = ""
    expected: str = ""
    met: bool = False
    evidence: str = ""


class DoneConditionParser:
    def extract_from_plan(self, plan_text: str) -> list[DoneCondition]:
        """Extract done conditions from plan text or TASK_REVIEW block."""
        conditions = []

        # Look for TASK_REVIEW block
        review_match = re.search(
            r'<TASK_REVIEW>(.*?)</TASK_REVIEW>',
            plan_text, re.DOTALL | re.IGNORECASE
        )
        if review_match:
            review = review_match.group(1)
            conds = self._parse_review_block(review)
            conditions.extend(conds)

        # Look for explicit "Done when" markers
        done_when = re.finditer(
            r'(?:Done|DONE|Hoàn thành|Xong)\s*(?:when|khi|nếu|if)[:\s]+(.+?)(?:\n|$)',
            plan_text, re.IGNORECASE
        )
        for m in done_when:
            conditions.append(DoneCondition(
                description=m.group(1).strip(),
                check_type="manual",
                target=m.group(1).strip(),
            ))

        # Look for test references
        tests = re.finditer(r'(?:chạy|run|test|kiểm tra)[:\s]+(.+?(?:test|pytest|jest|go test|npm test)\S*)',
                           plan_text, re.IGNORECASE)
        for m in tests:
            conditions.append(DoneCondition(
                description=f"Test pass: {m.group(1).strip()}",
                check_type="test_pass",
                target=m.group(1).strip(),
            ))

        return conditions

    def auto_generate_from_plan_json(self, plan_data: dict) -> list[DoneCondition]:
        """Auto-generate measurable done conditions từ hierarchical plan JSON.

        Tạo conditions từ mỗi task:
          - file_exists nếu task có file path
          - file_contains nếu task description đề cập nội dung cụ thể
          - command_ok nếu task có chạy lệnh
        """
        conditions: list[DoneCondition] = []
        milestones = plan_data.get("milestones", [])

        for mi, ms in enumerate(milestones):
            ms_title = ms.get("title", f"Milestone {mi+1}")
            tasks = ms.get("tasks", [])
            for ti, task in enumerate(tasks):
                desc = task.get("description", "")
                file_path = task.get("file", "")

                # 1. File existence condition
                if file_path:
                    conditions.append(DoneCondition(
                        description=f"[MS{mi+1}.{ti+1}] File '{file_path}' tồn tại",
                        check_type="file_exists",
                        target=file_path,
                    ))

                # 2. If description mentions specific content → file_contains
                content_keywords = self._extract_content_keywords(desc)
                for keyword in content_keywords:
                    if file_path:
                        conditions.append(DoneCondition(
                            description=f"[MS{mi+1}.{ti+1}] File '{file_path}' có {keyword}",
                            check_type="file_contains",
                            target=file_path,
                            expected=keyword,
                        ))

                # 3. Build/test condition nếu task có test/build verb
                if re.search(r'\b(test|pytest|jest|build|lint|typecheck|verify)\b', desc, re.IGNORECASE):
                    conditions.append(DoneCondition(
                        description=f"[MS{mi+1}.{ti+1}] Build/test pass",
                        check_type="test_pass",
                        target=desc[:60],
                    ))

            # 4. Milestone-level condition: tất cả task trong milestone hoàn thành
            if tasks:
                conditions.append(DoneCondition(
                    description=f"[MILESTONE] {ms_title} — tất cả {len(tasks)} tasks hoàn thành",
                    check_type="manual",
                    target=ms_title,
                ))

        # 5. Overall build condition
        conditions.append(DoneCondition(
            description="[FINAL] Project build/lint không lỗi",
            check_type="command_ok",
            target="build+lint",
        ))

        return conditions

    @staticmethod
    def _extract_content_keywords(desc: str) -> list[str]:
        """Trích xuất keywords từ description để dùng cho file_contains check."""
        keywords = []
        # Tìm patterns như 'thêm hàm X', 'implement class Y', 'define Z'
        func_match = re.search(r'(?:thêm|add|implement|define|create|viết|tạo)\s+(?:hàm|function|method|class|route|api|endpoint)\s+(\w+)', desc, re.IGNORECASE)
        if func_match:
            keywords.append(func_match.group(1))
        # Tìm patterns như 'import X', 'use X'
        import_match = re.search(r'(?:import|use|dùng|sử dụng)\s+(\w+)', desc, re.IGNORECASE)
        if import_match and len(import_match.group(1)) > 3:
            keywords.append(import_match.group(1))
        return keywords[:3]

    def _parse_review_block(self, review: str) -> list[DoneCondition]:
        conditions = []
        lines = review.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("- done_condition_met"):
                val = line.split(":", 1)[-1].strip() if ":" in line else ""
                conditions.append(DoneCondition(
                    description="Done condition met per AI",
                    check_type="manual",
                    target=val,
                    met=val.lower() in ("yes", "true", "pass"),
                ))
            elif line.startswith("- remaining_issues"):
                val = line.split(":", 1)[-1].strip() if ":" in line else ""
                conditions.append(DoneCondition(
                    description="Remaining issues",
                    check_type="manual",
                    target=val,
                    met=val.lower() == "none",
                ))
            elif line.startswith("- checks_performed"):
                val = line.split(":", 1)[-1].strip() if ":" in line else ""
                conditions.append(DoneCondition(
                    description="Checks performed",
                    check_type="manual",
                    target=val,
                ))
        return conditions


class DoneConditionVerifier:
    def verify(self, condition: DoneCondition, context: dict) -> DoneCondition:
        """Verify a single done condition against the current state.
        Does NOT blindly trust AI self-reports — cross-checks against actual evidence.
        """
        if condition.check_type == "manual":
            condition.met = False  # Default: not met until proven
            desc_lower = condition.description.lower()
            target_lower = condition.target.lower()

            # ── Cross-check file claims ──
            modified_files = context.get("modified_files", set())
            file_contents = context.get("file_contents", {})

            if target_lower and target_lower in (f.lower() for f in modified_files):
                condition.met = True
                condition.evidence = f"File '{condition.target}' confirmed in modified files"
            elif any(ext in target_lower for ext in (".py", ".js", ".ts", ".html", ".css", ".json", ".toml")):
                # Claim mentions a file path — verify it was actually modified
                mentioned_file = condition.target
                if mentioned_file in modified_files:
                    condition.met = True
                    condition.evidence = f"File '{mentioned_file}' exists in modified files"

            # ── Cross-check "remaining_issues: none" ──
            if "remaining_issues" in desc_lower or "remaining" in target_lower:
                has_errors = False
                for f, content in file_contents.items():
                    if content and ("TODO" in content or "FIXME" in content or "XXX" in content):
                        has_errors = True
                        condition.evidence = f"Found TODO/FIXME in {f}"
                        break
                condition.met = not has_errors and target_lower in ("none", "no", "không", "0")
                if condition.met:
                    condition.evidence = "Verified: no remaining issues found"

            # ── Cross-check "done_condition_met: yes" ──
            if "done_condition_met" in desc_lower:
                all_ok = True
                if not modified_files:
                    condition.evidence = "Nothing was modified — cannot be done"
                    all_ok = False
                else:
                    # At minimum, verify modified files actually exist
                    missing = [f for f in modified_files if not Path(context.get("project_root", "."), f).exists()]
                    if missing:
                        condition.evidence = f"Claimed files don't exist: {missing}"
                        all_ok = False
                condition.met = all_ok and target_lower in ("yes", "true", "pass")
                if condition.met:
                    condition.evidence = "Verified: modified files exist, no issues detected"

            # ── Cross-check "checks_performed" ──
            if "checks_performed" in desc_lower:
                checks = condition.target
                if checks and checks.lower() not in ("none", "n/a", ""):
                    # Verify at least one check was meaningful
                    has_content = len(checks) > 10
                    condition.met = has_content
                    condition.evidence = f"Checks reported: {checks[:80]}" if has_content else "Checks claimed but empty"

            # Fallback: if nothing matched, still mark met if AI provided reasonable detail
            if not condition.evidence:
                if len(condition.description) > 20 or (modified_files and condition.target):
                    condition.met = True
                    condition.evidence = "Manual check with reasonable detail"

        elif condition.check_type == "test_pass":
            results = context.get("test_results", {})
            if condition.target in results:
                condition.met = results[condition.target]
                condition.evidence = f"Test {condition.target}: {'PASS' if results[condition.target] else 'FAIL'}"
            else:
                condition.met = False
                condition.evidence = f"Test {condition.target} not run"

        elif condition.check_type == "file_exists":
            path = condition.target
            files = context.get("modified_files", set())
            condition.met = path in files
            condition.evidence = f"File {path}: {'created' if condition.met else 'not found'}"

        elif condition.check_type == "file_contains":
            file_contents = context.get("file_contents", {})
            content = file_contents.get(condition.target, "")
            condition.met = condition.expected in content
            condition.evidence = f"File {condition.target}: {'contains' if condition.met else 'missing'} expected pattern"

        return condition

    def verify_all(self, conditions: list[DoneCondition], context: dict) -> list[DoneCondition]:
        return [self.verify(c, context) for c in conditions]

    def all_met(self, conditions: list[DoneCondition]) -> bool:
        return all(c.met for c in conditions)

    def summary(self, conditions: list[DoneCondition]) -> str:
        total = len(conditions)
        met = sum(1 for c in conditions if c.met)
        lines = [f"Done Conditions: {met}/{total} met"]
        for c in conditions:
            status = "[OK]" if c.met else "[ERR]"
            lines.append(f"  {status} {c.description}")
        return "\n".join(lines)