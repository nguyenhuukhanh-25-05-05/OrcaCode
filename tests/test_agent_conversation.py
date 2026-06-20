import pytest
from unittest.mock import AsyncMock
from core.agent import AgentController, AppCallbacks
from core.models import ExecutionMode
from config.settings import load_config

@pytest.mark.asyncio
async def test_app_mode_routing():
    config = load_config()
    controller = AgentController(cfg=config)
    controller.client = type("MockClient", (), {})()
    
    # Mock routing endpoints as async
    called = []
    controller._handle_simple_conversation = AsyncMock(side_effect=lambda *args: called.append(("chat", args[0])))
    controller._run_auto = AsyncMock(side_effect=lambda *args: called.append(("auto", args[0])))
    controller._run_review = AsyncMock(side_effect=lambda *args: called.append(("plan", args[0])))
    
    # Chat mode
    controller.mode = ExecutionMode.CHAT
    await controller.run("hello")
    assert called == [("chat", "hello")]
    called.clear()
    
    # Auto mode
    controller.mode = ExecutionMode.AUTO
    await controller.run("hãy tạo file index.html mới với nội dung hello world")
    assert called == [("auto", "hãy tạo file index.html mới với nội dung hello world")]
    called.clear()
    
    # Plan mode
    controller.mode = ExecutionMode.PLAN
    await controller.run("hãy tạo file index.html mới với nội dung hello world")
    assert called == [("plan", "hãy tạo file index.html mới với nội dung hello world")]

@pytest.mark.asyncio
async def test_handle_simple_conversation(monkeypatch):
    config = load_config()
    called = []

    callbacks = AppCallbacks(
        on_status=lambda text: called.append(("status", text)),
        on_tokens_used=lambda p, c: called.append(("tokens", p, c)),
        on_chat=lambda text: called.append(("chat", text)),
        on_done=lambda *args: called.append("done")
    )

    controller = AgentController(cfg=config, callbacks=callbacks)

    async def mock_call_ai_stream(client, cfg, messages, **kw):
        return "Chào bạn! Tôi có thể giúp gì cho bạn?", 10, 5, {"truncated": False}

    import core.agent
    monkeypatch.setattr(core.agent, "_call_ai_stream", mock_call_ai_stream)

    await controller._handle_simple_conversation("chào bạn")

    # Assert correct callbacks were invoked
    assert any(x[0] == "chat" and "Chào bạn!" in x[1] for x in called)
    assert "done" in called
