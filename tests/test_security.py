"""Unit tests for SecurityService - command classification, blocking, approval."""
from core.services.security_service import SecurityService


def test_init():
    ss = SecurityService()
    assert not ss._auto_approve
    assert not ss.session_approved_build


def test_blocked_commands():
    ss = SecurityService()
    for cmd in ["rm -rf /", "del /f test", "shutdown -s", "format c:"]:
        blocked, _ = ss.is_command_blocked(cmd)
        assert blocked, f"Should block: {cmd}"


def test_safe_commands_not_blocked():
    ss = SecurityService()
    for cmd in ["python test.py", "rg --files", "ls -la", "npm install"]:
        blocked, _ = ss.is_command_blocked(cmd)
        assert not blocked, f"Should not block: {cmd}"


def test_readonly_detection():
    ss = SecurityService()
    assert ss.is_readonly("rg --files")
    assert ss.is_readonly("ls -la")
    assert ss.is_readonly("cat file.txt")
    assert ss.is_readonly("git status")
    assert ss.is_readonly("dir .")
    assert not ss.is_readonly("rm -rf /")
    assert not ss.is_readonly("python test.py")


def test_build_detection():
    ss = SecurityService()
    assert ss.is_build("npm install")
    assert ss.is_build("pip install rich")
    assert ss.is_build("python test.py")
    assert ss.is_build("cargo build")
    assert ss.is_build("make all")
    assert not ss.is_build("rg --files")
    assert not ss.is_build("ls -la")


def test_classify_blocked():
    ss = SecurityService()
    req = ss.classify_command("rm -rf /")
    assert req.risk_level == "high"
    assert req.requires_approval


def test_classify_readonly():
    ss = SecurityService()
    req = ss.classify_command("rg --files")
    assert req.risk_level == "low"
    assert not req.requires_approval


def test_classify_build_first_time():
    ss = SecurityService()
    req = ss.classify_command("npm install")
    assert req.risk_level == "medium"
    assert req.requires_approval


def test_classify_build_approved():
    ss = SecurityService()
    ss.session_approved_build = True
    req = ss.classify_command("npm install")
    assert not req.requires_approval


def test_auto_approve_mode():
    ss = SecurityService()
    ss._auto_approve = True
    assert ss.approve_write_file("test.txt", "content", None)


def test_approve_write_file_no_old():
    ss = SecurityService()
    ss._auto_approve = True
    approved = ss.approve_write_file("test.txt", "content", None)
    assert approved


def test_approve_run_command_blocked():
    ss = SecurityService()
    approved = ss.approve_run_command("rm -rf /")
    assert not approved


def test_approve_run_command_readonly():
    ss = SecurityService()
    approved = ss.approve_run_command("rg --files")
    assert approved


def test_verify_workspace_trust_already_trusted():
    from core.services.security_service import verify_workspace_trust
    from unittest.mock import patch
    import json
    import os
    
    cwd_str = str(os.getcwd())
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "trusted_workspaces": [cwd_str]
        })
        assert verify_workspace_trust() is True


def test_sync_approval_callback():
    called = []
    def sync_cb(title, detail):
        called.append((title, detail))
        return True

    ss = SecurityService(approval_callback=sync_cb)
    approved = ss.ask_approval("Test Title", "Test Detail")
    assert approved is True
    assert len(called) == 1
    assert called[0] == ("Test Title", "Test Detail")

