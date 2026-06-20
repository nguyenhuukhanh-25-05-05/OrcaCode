import difflib


def create_diff(old_text: str, new_text: str, file_path: str = "") -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{file_path}" if file_path else "",
        tofile=f"b/{file_path}" if file_path else "",
        n=3,
    )
    return "".join(diff)


def format_diff_simple(old_text: str, new_text: str, file_path: str = "") -> str:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    result = []
    if file_path:
        result.append(f"📄 {file_path}")
        result.append("")
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in old_lines[i1:i2][-2:]:
                result.append(f"  {line}")
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                result.append(f"- {line}")
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result.append(f"+ {line}")
        elif tag == "replace":
            for line in old_lines[i1:i2]:
                result.append(f"- {line}")
            for line in new_lines[j1:j2]:
                result.append(f"+ {line}")
    return "\n".join(result)


def compute_diff(old_text: str, new_text: str) -> str:
    return create_diff(old_text, new_text)


def compute_diff_lines(old_lines: list[str], new_lines: list[str]) -> list["DiffLine"]:
    from core.models import DiffLine
    result: list[DiffLine] = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx in range(i1, i2):
                result.append(DiffLine("context", old_lines[idx], idx + 1, idx + 1))
        elif tag == "replace":
            for idx in range(i1, i2):
                result.append(DiffLine("removed", old_lines[idx], idx + 1, None))
            for idx in range(j1, j2):
                result.append(DiffLine("added", new_lines[idx], None, idx + 1))
        elif tag == "delete":
            for idx in range(i1, i2):
                result.append(DiffLine("removed", old_lines[idx], idx + 1, None))
        elif tag == "insert":
            for idx in range(j1, j2):
                result.append(DiffLine("added", new_lines[idx], None, idx + 1))
    return result
