"""Unit tests for PatchService - fuzzy matching, write, read, parse."""
import os, tempfile

from core.services.patch_service import PatchService


def setup_service():
    return PatchService(".")


def test_parse_write_file():
    ps = setup_service()
    calls = ps.parse_tool_calls('<WRITE_FILE path="test.txt">\nhello\n</WRITE_FILE>')
    assert len(calls) == 1
    assert calls[0]["type"] == "write_file"
    assert calls[0]["path"] == "test.txt"
    assert calls[0]["content"] == "hello"


def test_parse_patch_file():
    ps = setup_service()
    resp = '<PATCH_FILE path="test.py">\n------- SEARCH\nold\n=======\nnew\n+++++++ REPLACE\n</PATCH_FILE>'
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 1
    assert calls[0]["type"] == "patch_file"
    assert calls[0]["search"] == "old"
    assert calls[0]["replace"] == "new"


def test_parse_run_command():
    ps = setup_service()
    calls = ps.parse_tool_calls('<RUN_COMMAND>\npython --version\n</RUN_COMMAND>')
    assert len(calls) == 1
    assert calls[0]["type"] == "run_command"
    assert calls[0]["command"] == "python --version"


def test_parse_multiple_calls():
    ps = setup_service()
    resp = (
        '<WRITE_FILE path="a.txt">\na\n</WRITE_FILE>\n'
        '<RUN_COMMAND>\nls\n</RUN_COMMAND>\n'
        '<PATCH_FILE path="b.py">\n------- SEARCH\nx\n=======\ny\n+++++++ REPLACE\n</PATCH_FILE>'
    )
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 3
    types = [c["type"] for c in calls]
    assert "write_file" in types
    assert "run_command" in types
    assert "patch_file" in types


def test_parse_empty():
    ps = setup_service()
    assert ps.parse_tool_calls("just a normal message") == []
    assert ps.parse_tool_calls("") == []


def test_write_and_read_file():
    ps = setup_service()
    tmp = tempfile.mktemp(suffix=".txt")
    try:
        result = ps.write_file(tmp, "hello world")
        assert result.success
        assert result.message.startswith("Written")
        content = ps.read_file(tmp)
        assert content == "hello world"
    finally:
        try: os.unlink(tmp)
        except: pass


def test_read_nonexistent():
    ps = setup_service()
    assert ps.read_file("_nonexistent_file_xyz.txt") is None


def test_exact_patch():
    ps = setup_service()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("def foo():\n    return 1\n")
        tmp = f.name
    try:
        result = ps.apply_patch(tmp, "def foo():\n    return 1", "def foo():\n    return 2")
        assert result.success
        assert result.score >= 0.99
        content = open(tmp, encoding="utf-8").read()
        assert "return 2" in content
    finally:
        try: os.unlink(tmp)
        except: pass


def test_fuzzy_patch():
    ps = setup_service()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("def hello():\n    print(\"old version\")\n    return True\n")
        tmp = f.name
    try:
        result = ps.apply_patch(
            tmp,
            "def hello():\n    print(\"old version\")\n    return True",
            "def hello():\n    print(\"new version\")\n    return False"
        )
        assert result.success, f"Fuzzy patch failed: {result.message}"
        content = open(tmp, encoding="utf-8").read()
        assert "new version" in content
    finally:
        try: os.unlink(tmp)
        except: pass


def test_patch_file_not_found():
    ps = setup_service()
    result = ps.apply_patch("_nonexistent.py", "old", "new")
    assert not result.success
    assert "not found" in result.message


def test_empty_search_block():
    ps = setup_service()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("x = 1\n")
        tmp = f.name
    try:
        result = ps.apply_patch(tmp, "", "new")
        assert not result.success
        assert "Empty" in result.message
    finally:
        try: os.unlink(tmp)
        except: pass


def test_parse_multiple_search_replace_in_one_patch():
    ps = setup_service()
    resp = (
        '<PATCH_FILE path="style.css">\n'
        '------- SEARCH\nbody { background: white; }\n=======\nbody { background: black; }\n+++++++ REPLACE\n'
        '------- SEARCH\nh1 { color: black; }\n=======\nh1 { color: white; }\n+++++++ REPLACE\n'
        '</PATCH_FILE>'
    )
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 2
    assert calls[0]["type"] == "patch_file"
    assert calls[0]["path"] == "style.css"
    assert calls[0]["search"] == "body { background: white; }"
    assert calls[0]["replace"] == "body { background: black; }"
    assert calls[1]["search"] == "h1 { color: black; }"
    assert calls[1]["replace"] == "h1 { color: white; }"


def test_parse_aider_style_diff():
    ps = setup_service()
    resp = (
        '<PATCH_FILE path="script.js">\n'
        '<<<<<<< SEARCH\nlet x = 1;\n=======\nlet x = 2;\n>>>>>>> REPLACE\n'
        '</PATCH_FILE>'
    )
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 1
    assert calls[0]["type"] == "patch_file"
    assert calls[0]["search"] == "let x = 1;"
    assert calls[0]["replace"] == "let x = 2;"


def test_parse_unclosed_write_file():
    ps = setup_service()
    resp = '<WRITE_FILE path="index.html">\n<!DOCTYPE html><html><body><h1>test'
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 1
    assert calls[0]["type"] == "write_file"
    assert calls[0]["path"] == "index.html"
    assert calls[0]["content"] == "<!DOCTYPE html><html><body><h1>test"


def test_parse_unclosed_patch_file():
    ps = setup_service()
    resp = (
        '<PATCH_FILE path="main.py">\n'
        '------- SEARCH\nprint("hello")\n=======\nprint("world")\n+++++++ REPLACE\n'
        '------- SEARCH\nx = 1\n=======\nx = 2' # Cut off here, no +++++++ REPLACE or </PATCH_FILE>
    )
    calls = ps.parse_tool_calls(resp)
    assert len(calls) == 1
    assert calls[0]["type"] == "patch_file"
    assert calls[0]["search"] == 'print("hello")'
    assert calls[0]["replace"] == 'print("world")'
