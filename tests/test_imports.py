import sys, os
sys.path.insert(0, os.getcwd())

from config.settings import AppConfig, load_config, get_api_base_url
cfg = load_config()
assert cfg.model.provider == "deepseek"
print("OK: config.settings")

from utils.normalize import normalize_line, normalize_text
assert normalize_line("  Foo  ") == "foo"
print("OK: utils.normalize")

from utils.diff import create_diff, format_diff_simple
diff = create_diff("a\nb\n", "a\nc\n")
assert "-b" in diff and "+c" in diff
print("OK: utils.diff")

from utils.tokenizer import tokenize_lines, count_lines
assert tokenize_lines("a\nb") == ["a", "b"]
print("OK: utils.tokenizer")

from core.models import SearchResult, PatchOperation, PatchResult, DiffLine, SessionState
s = SearchResult("x", 1, 10, "")
assert s.file_path == "x"
print("OK: core.models")

from core.services.context_service import ContextService
cs = ContextService(".")
assert cs.max_files == 5
print("OK: core.services.context_service")

from core.services.patch_service import PatchService
ps = PatchService(".")
calls = ps.parse_tool_calls('<WRITE_FILE path="x">\ntest\n</WRITE_FILE>')
assert calls[0]["type"] == "write_file"
calls2 = ps.parse_tool_calls('<PATCH_FILE path="x">\n------- SEARCH\nold\n=======\nnew\n+++++++ REPLACE\n</PATCH_FILE>')
assert calls2[0]["type"] == "patch_file"
calls3 = ps.parse_tool_calls('<RUN_COMMAND>\nls\n</RUN_COMMAND>')
assert calls3[0]["type"] == "run_command"
print("OK: core.services.patch_service")

from core.services.security_service import SecurityService
ss = SecurityService()
blocked, _ = ss.is_command_blocked("rm -rf /")
assert blocked
assert ss.is_readonly("rg --files")
assert not ss.is_readonly("rm -rf /")
print("OK: core.services.security_service")

from core.viewmodels.session_vm import SessionViewModel
from core.viewmodels.patch_vm import PatchViewModel
svm = SessionViewModel(SessionState())
assert svm.summary()
pvm = PatchViewModel()
assert not pvm.has_changes()
print("OK: core.viewmodels")

from core.ui import StatusBar, show_diff_summary, show_tool_call, show_result, show_error, show_warning
from core.ui import show_config
print("OK: core.ui")

from core.git_repo import GitRepo
from core.summarizer import ChatSummarizer
summ = ChatSummarizer()
big = [{"role": "user", "content": "x" * 10000}] * 50
result = summ.summarize(big)
assert len(result) < len(big)
print("OK: core.git_repo + core.summarizer")

print("\nALL IMPORTS OK")
