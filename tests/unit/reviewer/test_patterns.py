"""Tests for bug pattern detector."""

from core.reviewer.patterns import BugPatternDetector
from core.reviewer.models import ReviewCategory, ReviewSeverity


def test_detect_empty_except():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", """
try:
    do_something()
except:
    pass
""")
    assert len(issues) >= 1
    assert any("except" in i.message.lower() for i in issues)


def test_detect_bare_except():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", """
try:
    x = 1 / 0
except:
    pass
""")
    bare = [i for i in issues if "bare" in i.message.lower() or "except:" in i.message]
    assert len(bare) >= 1


def test_detect_mutable_default():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "def foo(items=[]):\n    pass")
    mutable = [i for i in issues if "mutable" in i.message.lower()]
    assert len(mutable) >= 1


def test_detect_none_comparison():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "if x == None:\n    pass")
    none_issues = [i for i in issues if "None" in i.message]
    assert len(none_issues) >= 1


def test_detect_print():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "print('hello world')")
    print_issues = [i for i in issues if "print" in i.message.lower()]
    assert len(print_issues) >= 1


def test_detect_console_log():
    detector = BugPatternDetector()
    issues = detector.scan_file("app.js", "console.log('debug');")
    log_issues = [i for i in issues if "console.log" in i.message.lower()]
    assert len(log_issues) >= 1


def test_detect_todo():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "# TODO: implement this")
    todo = [i for i in issues if "TODO" in i.message]
    assert len(todo) >= 1


def test_detect_debugger():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "breakpoint()")
    debugger = [i for i in issues if "debugger" in i.message.lower() or "breakpoint" in i.message.lower()]
    assert len(debugger) >= 1


def test_detect_hardcoded_path():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", 'path = "/var/log/app"')
    path_issues = [i for i in issues if "hardcoded" in i.message.lower()]
    assert len(path_issues) >= 1


def test_scan_no_issues():
    detector = BugPatternDetector()
    issues = detector.scan_file("clean.py", "def add(a, b):\n    return a + b\n")
    assert len(issues) == 0


def test_scan_files_dict():
    detector = BugPatternDetector()
    files = {
        "good.py": "def add(a, b):\n    return a + b\n",
        "bad.py": "def foo(items=[]):\n    pass\n",
    }
    result = detector.scan_files(files)
    assert result.count >= 1
    assert not result.passed


def test_scan_empty_file():
    detector = BugPatternDetector()
    issues = detector.scan_file("empty.py", "")
    assert len(issues) == 0


def test_ast_assert_without_message():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "assert x == 1")
    assert_issues = [i for i in issues if "assert" in i.message.lower()]
    assert len(assert_issues) >= 1


def test_ast_issue_has_location():
    detector = BugPatternDetector()
    issues = detector.scan_file("test.py", "except:\n    pass\n")
    located = [i for i in issues if i.line > 0]
    assert len(located) >= 1
