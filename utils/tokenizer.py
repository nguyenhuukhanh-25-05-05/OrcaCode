import re


def tokenize_lines(text: str) -> list[str]:
    return text.splitlines(keepends=False)


def tokenize_words(line: str) -> list[str]:
    return re.findall(r'\w+|[^\w\s]', line)


def tokenize_symbols(text: str) -> list[str]:
    symbols = []
    for line in text.splitlines():
        tokens = re.findall(
            r'(?:def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+)'
            r'|\w+\s*=|=>|->|\(|\)|\{|\}',
            line
        )
        symbols.extend(tokens)
    return symbols


def count_lines(text: str) -> int:
    return len(text.splitlines())
