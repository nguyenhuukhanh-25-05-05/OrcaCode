"""Unit tests for StructuralValidator – structural integrity checks."""
from core.services.structural_validator import StructuralValidator


sv = StructuralValidator()


# ── HTML ────────────────────────────────────────────────────────────────


def test_html_tag_balance():
    bad = "<html><body><div></body></html>"
    errors = sv.validate("index.html", None, bad)
    assert any("div" in e and "Unbalanced" in e for e in errors)

    good = "<html><body><div></div></body></html>"
    assert sv.validate("page.htm", None, good) == []


def test_html_missing_doctype():
    old = "<!DOCTYPE html><html></html>"
    new = "<html></html>"
    errors = sv.validate("index.html", old, new)
    assert any("DOCTYPE" in e for e in errors)

    # Không cảnh báo nếu old cũng không có DOCTYPE
    errors2 = sv.validate("index.html", "<html></html>", "<html></html>")
    assert not any("DOCTYPE" in e for e in errors2)


def test_html_missing_script_section():
    old = '<html><script src="app.js"></script></html>'
    new = "<html></html>"
    errors = sv.validate("page.html", old, new)
    assert any("<script>" in e for e in errors)

    # Cũng kiểm tra <style>
    old_style = "<html><style>body{}</style></html>"
    new_no_style = "<html></html>"
    errors2 = sv.validate("page.html", old_style, new_no_style)
    assert any("<style>" in e for e in errors2)


# ── Python ──────────────────────────────────────────────────────────────


def test_python_syntax_error():
    bad = "def foo(\n"
    errors = sv.validate("app.py", None, bad)
    assert any("SyntaxError" in e for e in errors)


def test_python_missing_function():
    old = "def foo():\n    pass\n\ndef bar():\n    pass\n"
    new = "def foo():\n    pass\n"
    errors = sv.validate("module.py", old, new)
    assert any("bar" in e for e in errors)
    assert not any("foo" in e for e in errors)


def test_python_new_file_no_old():
    new = "class MyClass:\n    pass\n"
    errors = sv.validate("new.py", None, new)
    assert errors == []


# ── JavaScript / TypeScript ─────────────────────────────────────────────


def test_js_bracket_balance():
    bad = "function test() { if (true) { console.log('hi') }"
    errors = sv.validate("app.js", None, bad)
    # Thiếu 1 dấu }
    assert any("curly braces" in e for e in errors)

    good = "function test() { if (true) { console.log('hi') } }"
    assert not any("curly braces" in e for e in sv.validate("app.js", None, good))


def test_js_missing_symbols():
    old = (
        "function alpha() {}\n"
        "function beta() {}\n"
        "function gamma() {}\n"
        "const delta = 1;\n"
    )
    # Giữ lại 1 symbol, xoá 3 → 75% mất → cảnh báo
    new = "function alpha() {}\n"
    errors = sv.validate("lib.ts", old, new)
    assert any("symbols removed" in e for e in errors)

    # Cũng hoạt động với .jsx, .tsx, .mjs, .cjs
    for ext in (".jsx", ".tsx", ".mjs", ".cjs"):
        errs = sv.validate(f"file{ext}", old, new)
        assert any("symbols removed" in e for e in errs)


# ── CSS ─────────────────────────────────────────────────────────────────


def test_css_bracket_balance():
    bad = "body { color: red; .inner { font-size: 12px; }"
    errors = sv.validate("style.css", None, bad)
    assert any("Unbalanced braces" in e for e in errors)

    good = "body { color: red; } .inner { font-size: 12px; }"
    assert sv.validate("style.scss", None, good) == []


# ── JSON ────────────────────────────────────────────────────────────────


def test_json_valid():
    assert sv.validate("data.json", None, '{"key": "value"}') == []


def test_json_invalid():
    errors = sv.validate("data.json", None, '{"key": }')
    assert any("JSONDecodeError" in e for e in errors)


# ── Unknown extension ──────────────────────────────────────────────────


def test_unknown_extension_returns_empty():
    assert sv.validate("readme.md", None, "# Hello") == []
    assert sv.validate("image.png", None, "binary data") == []
    assert sv.validate("Makefile", None, "all: build") == []
