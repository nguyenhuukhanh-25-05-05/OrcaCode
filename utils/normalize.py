import re


def normalize_line(line: str) -> str:
    line = line.rstrip("\n").rstrip("\r")
    line = re.sub(r"[ \t]+", " ", line)
    line = line.strip()
    return line.lower()


def normalize_text(text: str) -> list[str]:
    return [normalize_line(l) for l in text.splitlines()]


def detect_indentation(lines: list[str]) -> str:
    for line in lines:
        stripped = line.lstrip()
        if stripped and (line.startswith(" ") or line.startswith("\t")):
            return line[:len(line) - len(stripped)]
    return "    "
