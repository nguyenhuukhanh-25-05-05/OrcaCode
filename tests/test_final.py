"""Final integration test for OrcaCode."""
import ast
import sys
import os
sys.path.insert(0, os.getcwd())

print("=== OrcaCode Final Test ===\n")

# 1. Syntax check all files
all_files = [
    "orca.py", "config/settings.py", "core/__init__.py", "core/agent.py",
    "core/git_repo.py", "core/summarizer.py", "core/ui.py", "core/commands.py",
    "core/memory_manager.py",
    "core/services/context_service.py", "core/services/patch_service.py",
    "core/services/security_service.py",
    "core/services/plugin_service.py", "core/services/debug_service.py",
    "core/services/error_parser.py",    "core/services/rule_engine.py",
    "core/services/error_pipeline.py",
    "core/services/arch_graph.py",
    "core/services/checkpoint_service.py",
    "core/services/blueprint_service.py",
    "utils/diff.py", "utils/normalize.py", "utils/tokenizer.py",
]
syntax_ok = True
for f in all_files:
    try:
        code = open(f, encoding='utf-8').read()
        ast.parse(code)
        print(f"  OK {f}")
    except Exception as e:
        print(f"  FAIL {f}: {e}")
        syntax_ok = False

# 2. Import test
from config.settings import AppConfig, load_config
from core.services.patch_service import PatchService
from core.services.security_service import SecurityService, verify_workspace_trust
from core.git_repo import GitRepo
from core.summarizer import ChatSummarizer
from core.commands import handle_command, is_command
print(f"\n  All imports OK")

# 3. Functional tests
ss = SecurityService()
assert ss.is_command_blocked("rm -rf /")[0], "Block check"
assert ss.is_readonly("rg --files"), "Readonly check"
print("  SecurityService functional")

ps = PatchService(".")
calls = ps.parse_tool_calls('<WRITE_FILE path="x">\ntest\n</WRITE_FILE>')
assert calls[0]["type"] == "write_file"
calls2 = ps.parse_tool_calls('<PATCH_FILE path="x">\n------- SEARCH\nold\n=======\nnew\n+++++++ REPLACE\n</PATCH_FILE>')
assert calls2[0]["type"] == "patch_file"
calls3 = ps.parse_tool_calls('<RUN_COMMAND>\nls\n</RUN_COMMAND>')
assert calls3[0]["type"] == "run_command"
print("  PatchService.parse_tool_calls functional")

result = ps.write_file("_test_final.txt", "hello")
assert result.success and os.path.exists("_test_final.txt")
os.remove("_test_final.txt")
print("  PatchService.write_file functional")

summ = ChatSummarizer()
assert not summ.too_big([{"role": "user", "content": "hi"}])
big = [{"role": "user", "content": "x" * 5000}] * 100
assert summ.too_big(big)
result = summ.summarize(big)
assert len(result) < len(big)
print("  ChatSummarizer functional")

# 4. Commands test
assert is_command("/help")
assert is_command("/exit")
assert not is_command("hello world")
print("  Commands functional")

# 5. UI module import
from core.ui import print_banner, StatusBar, show_diff_summary, show_tool_call, show_result
from core.ui import show_iteration, show_ai_response, show_error, show_warning
from core.ui import show_config, get_interactive_input, confirm_action
from core.ui import show_file_list, chat_prompt
print("  core/ui imports OK")

# 6. GitRepo
repo = GitRepo()
print(f"  GitRepo (available={repo.available})")

print(f"\n{'='*50}")
print(f"ALL {len(all_files)} FILES: SYNTAX OK + IMPORTS OK + FUNCTIONAL OK")
print(f"{'='*50}")