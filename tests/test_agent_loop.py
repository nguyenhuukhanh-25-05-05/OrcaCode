"""Tests for the core agent execution loop (_execute_loop)."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.agent import AgentController
from core.agent_utils import AppCallbacks
from config.settings import load_config


@pytest.fixture
def mock_controller():
    config = load_config()
    callbacks = AppCallbacks()
    ctrl = AgentController(cfg=config, callbacks=callbacks)
    ctrl.client = MagicMock()
    ctrl.patch_svc = MagicMock()
    ctrl.patch_svc.parse_tool_calls.return_value = []
    ctrl._execute_tool = MagicMock(return_value={"summary": "ok", "success": True})
    ctrl._check_syntax = MagicMock(return_value="")
    ctrl._diagnose_file = MagicMock(return_value="")
    ctrl._verify_with_evidence = AsyncMock(return_value=MagicMock(all_pass=MagicMock(return_value=True)))
    ctrl._has_leaked_code = MagicMock(return_value=False)
    ctrl._is_awaiting_user_input = MagicMock(return_value=False)
    ctrl._is_conversational_response = MagicMock(return_value=False)
    ctrl._is_interrupted = MagicMock(return_value=False)
    ctrl._extract_plan_steps = MagicMock(return_value=[])
    ctrl._validate_plan_review = MagicMock(return_value=(True, ""))
    ctrl._validate_task_review = MagicMock(return_value=(True, ""))
    ctrl.session_vm = MagicMock()
    ctrl.memory = MagicMock()
    ctrl.memory.load_instructions.return_value = ""
    ctrl.conversation_cache = MagicMock()
    return ctrl


@pytest.mark.asyncio
async def test_normal_done_flow(mock_controller):
    """AI sends tool call then DONE — loop should exit cleanly."""
    responses = [
        '<WRITE_FILE path="test.txt">hello</WRITE_FILE>\n\n<DONE/>',
    ]
    mock_controller.patch_svc.parse_tool_calls.side_effect = [
        [{"type": "write_file", "path": "test.txt", "content": "hello"}],
        [],
    ]

    call_count = 0

    async def mock_call_ai(client, cfg, messages, **kw):
        nonlocal call_count
        resp = responses[call_count] if call_count < len(responses) else "<DONE/>"
        call_count += 1
        return resp, 10, 5, {"finish_reason": "stop", "truncated": False}

    import core.agent
    import core.agent_utils
    core.agent._call_ai = mock_call_ai
    core.agent_utils._call_ai = mock_call_ai

    messages = [{"role": "system", "content": "test"}, {"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=10)
    assert call_count <= 2, f"Expected ≤2 calls, got {call_count}"


@pytest.mark.asyncio
async def test_truncation_does_not_break(mock_controller):
    """Truncation triggers summarization, does not break loop on its own."""
    call_count = 0

    async def mock_call_ai(client, cfg, messages, **kw):
        nonlocal call_count
        call_count += 1
        return "", 10, 5, {"finish_reason": "length", "truncated": True}

    import core.agent
    core.agent._call_ai = mock_call_ai

    messages = [{"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=10)
    # Only "no tools used" guard stops it (MAX_CONSECUTIVE_FAILURES=5) => 6 calls
    assert call_count == 6, f"Expected 6 calls (1 + 5 no-tool failures), got {call_count}"


@pytest.mark.asyncio
async def test_compliance_code_leak(mock_controller):
    """Code leak violation should trigger correction and retry."""
    mock_controller._has_leaked_code.return_value = True
    call_count = 0

    async def mock_call_ai(client, cfg, messages, **kw):
        nonlocal call_count
        call_count += 1
        return "```python\nprint('leaked')\n```", 10, 5, {"finish_reason": "stop", "truncated": False}

    import core.agent
    core.agent._call_ai = mock_call_ai

    messages = [{"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=3)
    assert call_count >= 2, "Should have retried after leak"


@pytest.mark.asyncio
async def test_no_token_budget_limit(mock_controller):
    """Loop does NOT break on token usage (budget guard removed)."""
    call_count = 0

    async def mock_call_ai(client, cfg, messages, **kw):
        nonlocal call_count
        call_count += 1
        return '<WRITE_FILE path="t.txt">x</WRITE_FILE>', 300_000, 200_000, {"finish_reason": "stop", "truncated": False}

    import core.agent
    core.agent._call_ai = mock_call_ai

    def tool_side_effect(*a):
        # First two calls return write_file, rest return empty
        if not hasattr(tool_side_effect, 'call_idx'):
            tool_side_effect.call_idx = 0
        tool_side_effect.call_idx += 1
        if tool_side_effect.call_idx <= 2:
            return [{"type": "write_file", "path": "t.txt", "content": "x"}]
        return []
    mock_controller.patch_svc.parse_tool_calls.side_effect = tool_side_effect

    messages = [{"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=10)
    # Token budget was removed - loop continues past old 500K limit
    assert call_count > 3, f"Should exceed old budget limit, got {call_count}"


@pytest.mark.asyncio
async def test_stall_detection(mock_controller):
    """No new files after 3 iterations should trigger stall break."""
    call_count = 0

    async def mock_call_ai(client, cfg, messages, **kw):
        nonlocal call_count
        call_count += 1
        return '<WRITE_FILE path="t.txt">x</WRITE_FILE>', 10, 5, {"finish_reason": "stop", "truncated": False}

    import core.agent
    core.agent._call_ai = mock_call_ai

    mock_controller.patch_svc.parse_tool_calls.side_effect = [
        [{"type": "write_file", "path": "t.txt", "content": "x"}],
        [{"type": "write_file", "path": "t.txt", "content": "x"}],
        [{"type": "write_file", "path": "t.txt", "content": "x"}],
        [{"type": "write_file", "path": "t.txt", "content": "x"}],
    ]

    messages = [{"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=10)
    assert call_count <= 5, f"Stall should break after ~4 iterations, got {call_count}"


@pytest.mark.asyncio
async def test_user_interrupt(mock_controller):
    """User interrupt should stop immediately."""
    mock_controller._is_interrupted.return_value = True

    async def mock_call_ai(client, cfg, messages, **kw):
        return "doing stuff", 10, 5, {"finish_reason": "stop", "truncated": False}

    import core.agent
    core.agent._call_ai = mock_call_ai

    messages = [{"role": "user", "content": "do it"}]
    await mock_controller._execute_loop(messages, max_iter=10)
    # Loop should exit at first interrupt check before calling AI
