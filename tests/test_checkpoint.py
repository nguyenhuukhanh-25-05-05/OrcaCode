import asyncio
import json
import sqlite3
import gc
import shutil
import tempfile
from pathlib import Path
import pytest

from core.models import ExecutionMode
from core.services.checkpoint_service import CheckpointService

@pytest.fixture
def temp_project():
    """Fixture to set up a dummy project directory."""
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir)
    
    # Create some dummy files
    (project_path / "src").mkdir()
    (project_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (project_path / "src" / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
    
    # Create .orca directory structure
    (project_path / ".orca" / "memory").mkdir(parents=True)
    
    # Create dummy chat history
    history_file = project_path / ".orca" / "memory" / "chat_history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump([{"role": "user", "content": "hello"}], f)
        
    # Create dummy DB
    db_file = project_path / ".orca" / "memory" / "long_memory.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test (val) VALUES ('old_data')")
    conn.commit()
    conn.close()
    
    yield project_path
    
    # Retry cleanup with delay on Windows to release SQLite file locks
    import time
    for _ in range(3):
        try:
            shutil.rmtree(temp_dir)
            break
        except PermissionError:
            time.sleep(0.5)
            gc.collect()
    else:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_lifecycle(temp_project):
    svc = CheckpointService(str(temp_project))
    
    # 1. Create a checkpoint
    cp_id = svc.create_checkpoint("Initial state", "USER")
    assert cp_id is not None
    assert cp_id.startswith("CP_")
    
    # Verify zip and index exist
    zip_path = svc.checkpoints_dir / f"{cp_id}.zip"
    assert zip_path.exists()
    
    checkpoints = svc.list_checkpoints()
    assert len(checkpoints) == 1
    assert checkpoints[0]["id"] == cp_id
    assert checkpoints[0]["description"] == "Initial state"
    assert checkpoints[0]["action_type"] == "USER"
    
    # 2. Modify files, create new file, change DB, change chat history
    main_file = temp_project / "src" / "main.py"
    main_file.write_text("print('hello modified')", encoding="utf-8")
    
    new_file = temp_project / "src" / "new_module.py"
    new_file.write_text("# new module", encoding="utf-8")
    
    # Modify DB
    db_file = temp_project / ".orca" / "memory" / "long_memory.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT INTO test (val) VALUES ('new_data')")
    conn.commit()
    conn.close()
    
    # Modify chat history
    history_file = temp_project / ".orca" / "memory" / "chat_history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump([{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}], f)
        
    # Verify changes are present
    assert main_file.read_text(encoding="utf-8") == "print('hello modified')"
    assert new_file.exists()
    
    conn = sqlite3.connect(str(db_file))
    rows = conn.execute("SELECT val FROM test").fetchall()
    assert len(rows) == 2
    conn.close()
    
    # 3. Rollback to checkpoint
    def close_db_dummy():
        pass
        
    success = svc.rollback_to(cp_id, close_db_dummy)
    assert success is True
    
    # 4. Verify rollback result
    assert main_file.read_text(encoding="utf-8") == "print('hello')"
    assert not new_file.exists() # Should be deleted as it wasn't in checkpoint
    
    # Verify chat history restored
    with open(history_file, "r", encoding="utf-8") as f:
        hist = json.load(f)
        assert len(hist) == 1
        assert hist[0]["content"] == "hello"
        
    # Verify DB restored
    conn = sqlite3.connect(str(db_file))
    rows = conn.execute("SELECT val FROM test").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "old_data"
    conn.close()


@pytest.mark.asyncio
async def test_agent_checkpoint_integration(temp_project, monkeypatch):
    from core.agent import AgentController, AppCallbacks
    from config.settings import AppConfig

    # Configure mock config
    cfg = AppConfig()
    cfg.project_root = str(temp_project)
    cfg.model.api_key = "mock-key"

    # Create controller
    controller = AgentController(cfg=cfg)
    controller.client = type("MockClient", (), {})()

    # Track checkpoint calls
    checkpoint_calls = []
    original_create_checkpoint = controller.checkpoint_svc.create_checkpoint
    def track_checkpoint(desc, action_type="AI"):
        checkpoint_calls.append((desc, action_type))
        return original_create_checkpoint(desc, action_type)
    controller.checkpoint_svc.create_checkpoint = track_checkpoint

    # Mock intent router to always return "execute" intent
    from core.services.intent_router import IntentResult
    controller.intent_router.classify = lambda prompt: IntentResult(
        intent="execute", confidence=0.9, reason="test mock", suggested_action="", danger_reason=""
    )

    # We mock _call_ai to return simple plan/execute answers
    def mock_call_ai(client, config, messages, **kw):
        for msg in messages:
            if msg["role"] == "system" and "PLAN" in msg["content"]:
                return "Plan: 1. Create a file <PLAN_DONE/>", 10, 5, {}
        return "Explanation <DONE/>", 10, 5, {}

    import core.agent
    monkeypatch.setattr(core.agent, "_call_ai", mock_call_ai)

    # We also mock _run_post_execution_pipeline to avoid actually running builds/tests
    async def mock_post_pipeline(prompt):
        pass
    controller._run_post_execution_pipeline = mock_post_pipeline

    # Let's run the agent in Plan (review) mode
    controller.mode = ExecutionMode.PLAN

    # Mock plan approval callback to automatically approve
    callbacks = AppCallbacks(
        request_plan_approval=lambda plan: "approve_auto" # autopilot
    )
    controller.callbacks = callbacks

    # Execute prompt
    await controller.run("Create a new feature")

    # Check that create_checkpoint was called
    assert len(checkpoint_calls) >= 1
    assert any("Trước khi chạy prompt" in desc for desc, _ in checkpoint_calls)

    # Let's check checkpoints that were created!
    checkpoints = controller.checkpoint_svc.list_checkpoints()
    
    # At minimum the pre-prompt checkpoint should exist
    assert len(checkpoints) >= 1
    descriptions = [cp["description"] for cp in checkpoints]
    assert any("Trước khi chạy prompt" in desc for desc in descriptions)

    # Clean up connections to release file locks (critical on Windows)
    controller.shutdown()

