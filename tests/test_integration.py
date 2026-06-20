import sys, os, tempfile
sys.path.insert(0, os.getcwd())

from core.agent import AgentController
from config.settings import load_config

cfg = load_config()
ctrl = AgentController(cfg)
assert ctrl.context_svc is not None
assert ctrl.patch_svc is not None
assert ctrl.security_svc is not None
assert ctrl.session_vm is not None
assert ctrl.patch_vm is not None
print("OK: AgentController init")

# Patch test
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
    f.write("def hello():\n    print(\"old\")\n    return True\n")
    tmp = f.name
try:
    result = ctrl.patch_svc.apply_patch(
        tmp,
        "def hello():\n    print(\"old\")\n    return True",
        "def hello():\n    print(\"new\")\n    return False"
    )
    assert result.success, f"Patch failed: {result.message}"
    content = open(tmp, encoding='utf-8').read()
    assert "new" in content
    print("OK: fuzzy patch")
finally:
    try: os.unlink(tmp)
    except: pass

# Write + read
tmp2 = tempfile.mktemp(suffix='.txt')
try:
    result = ctrl.patch_svc.write_file(tmp2, "hello world")
    assert result.success
    content = ctrl.patch_svc.read_file(tmp2)
    assert content == "hello world"
    print("OK: write/read")
finally:
    try: os.unlink(tmp2)
    except: pass

# Parse tool calls
ps = ctrl.patch_svc
calls = ps.parse_tool_calls('<WRITE_FILE path="x">\ntest\n</WRITE_FILE>')
assert calls[0]["type"] == "write_file"
calls2 = ps.parse_tool_calls('<PATCH_FILE path="x">\n------- SEARCH\nold\n=======\nnew\n+++++++ REPLACE\n</PATCH_FILE>')
assert calls2[0]["type"] == "patch_file"
calls3 = ps.parse_tool_calls('<RUN_COMMAND>\nls\n</RUN_COMMAND>')
assert calls3[0]["type"] == "run_command"
print("OK: parse tool calls")

# Security
ss = ctrl.security_svc
blocked, _ = ss.is_command_blocked("rm -rf /")
assert blocked
assert ss.is_readonly("rg --files")
assert ss.is_build("npm install")
assert not ss.is_build("rg --files")
print("OK: security service")

# ViewModels
ctrl.session_vm.add_message("user", "hello")
assert ctrl.session_vm.last_message() == "hello"
assert ctrl.session_vm.estimate_tokens() > 0
summary = ctrl.session_vm.summary()
assert "msgs" in summary

ctrl.patch_vm.set_operation(result)
assert ctrl.patch_vm.has_changes()
ctrl.patch_vm.reset()
assert not ctrl.patch_vm.has_changes()
print("OK: viewmodels")

print("\nALL INTEGRATION TESTS PASSED")
