"""Unit tests for ContextService - search, keyword extraction, context building."""
from core.services.context_service import ContextService


def test_service_init():
    cs = ContextService(".")
    assert cs.max_files == 5
    assert cs.max_lines == 100


def test_custom_init():
    cs = ContextService("/tmp", max_files=3, max_lines=50)
    assert cs.max_files == 3
    assert cs.max_lines == 50


def test_keyword_extraction():
    cs = ContextService(".")
    kw = cs._extract_keywords("Sua ham login trong src/auth.py")
    assert "login" in kw
    assert "src/auth.py" in kw or "auth.py" in kw


def test_keyword_stopwords_removed():
    cs = ContextService(".")
    kw = cs._extract_keywords("fix file trong cho voi cua")
    assert all(w not in kw for w in ["fix", "file", "trong", "cho", "voi", "cua"])


def test_keyword_english():
    cs = ContextService(".")
    kw = cs._extract_keywords("Fix the login function in auth.py")
    assert "login" in kw
    assert "auth.py" in kw


def test_keyword_path_priority():
    cs = ContextService(".")
    kw = cs._extract_keywords("fix src/app/auth.py")
    # Path-like keywords should be first
    if kw:
        assert "." in kw[0] or "/" in kw[0] or "\\" in kw[0]


def test_format_context_empty():
    cs = ContextService(".")
    result = cs.format_context([])
    assert "Project:" in result


def test_read_nonexistent_file():
    cs = ContextService(".")
    content = cs.read_file_context("_nonexistent_file_xyz.txt")
    assert content == ""


def test_binary_detection():
    cs = ContextService(".")
    from pathlib import Path
    assert cs._is_binary(Path(__file__)) is False


def test_build_context_no_keywords():
    cs = ContextService(".")
    result = cs.build_context("")
    assert result is not None


def test_explicit_path_extraction(tmp_path):
    # Setup test file
    test_file = tmp_path / "index.html"
    test_file.write_text("hello world", encoding="utf-8")
    
    cs = ContextService(str(tmp_path))
    # Prompt containing file path
    context = cs.build_context("đọc file index.html đi bạn")
    assert "[index.html]" in context
    assert "hello world" in context


def test_python_fallback_search(tmp_path):
    # Setup files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "auth.py").write_text("def login(): pass", encoding="utf-8")
    (src_dir / "style.css").write_text("body { color: red; }", encoding="utf-8")
    
    cs = ContextService(str(tmp_path))
    # Force fallback to python search
    cs.rg_available = False
    
    # 1. Filename search
    fn_results = cs.search("auth", cs.LEVEL_FILE)
    assert len(fn_results) == 1
    assert "auth.py" in fn_results[0].file_path
    
    # 2. Content search
    cnt_results = cs.search("color", cs.LEVEL_CONTENT)
    assert len(cnt_results) == 1
    assert "style.css" in cnt_results[0].file_path
    
    # 3. Symbol search
    sym_results = cs.search("login", cs.LEVEL_SYMBOL)
    assert len(sym_results) == 1
    assert "auth.py" in sym_results[0].file_path


def test_small_project_fallback_loading(tmp_path):
    # Setup files
    (tmp_path / "index.html").write_text("index content", encoding="utf-8")
    (tmp_path / "style.css").write_text("css content", encoding="utf-8")
    
    cs = ContextService(str(tmp_path))
    # Search with prompt that has zero keyword matches
    context = cs.build_context("xyzabc")
    
    assert "[index.html]" in context
    assert "index content" in context
    assert "[style.css]" in context
    assert "css content" in context


def test_at_file_reference(tmp_path):
    # Setup files inside a deep directory structure
    src_dir = tmp_path / "src" / "pages"
    src_dir.mkdir(parents=True)
    (src_dir / "about.html").write_text("about details", encoding="utf-8")
    (tmp_path / "index.html").write_text("index details", encoding="utf-8")
    
    cs = ContextService(str(tmp_path))
    
    # 1. Test direct name resolving (recursively found)
    context1 = cs.build_context("hãy đọc file @about.html đi bạn")
    assert "[src/pages/about.html]" in context1 or "[src\\pages\\about.html]" in context1
    assert "about details" in context1
    
    # 2. Test direct relative path resolving
    context2 = cs.build_context("sửa file @index.html")
    assert "[index.html]" in context2
    assert "index details" in context2
