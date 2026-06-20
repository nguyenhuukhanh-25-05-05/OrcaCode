"""Workspace Checkpoint Service for Time-Travel workspace states."""

import logging
import os
import json
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class CheckpointService:
    """Manages workspace checkpoints including code, chat history, and database states."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.orca_dir = self.project_root / ".orca"
        self.checkpoints_dir = self.orca_dir / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.orca_dir / "memory" / "long_memory.db"
        self.history_path = self.orca_dir / "memory" / "chat_history.json"
        self._walk_cache: list[Path] | None = None
        self._walk_cache_time: float = 0
        self._walk_cache_ttl: float = 2.0
        
    def list_checkpoints(self) -> List[Dict]:
        """Returns list of all checkpoints sorted by timestamp."""
        index_file = self.checkpoints_dir / "checkpoints.json"
        if not index_file.exists():
            return []
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                checkpoints = json.load(f)
            return sorted(checkpoints, key=self._checkpoint_sort_key)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _checkpoint_sort_key(self, checkpoint: Dict) -> tuple:
        timestamp = checkpoint.get("timestamp", "")
        try:
            parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return (parsed, checkpoint.get("id", ""))
        except (ValueError, TypeError):
            return (datetime.min, checkpoint.get("id", ""))

    def _save_index(self, checkpoints: List[Dict]):
        index_file = self.checkpoints_dir / "checkpoints.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(sorted(checkpoints, key=self._checkpoint_sort_key), f, ensure_ascii=False, indent=2)

    def prune_after(self, checkpoint_id: str) -> int:
        """Delete checkpoints that are newer than the selected checkpoint."""
        checkpoints = self.list_checkpoints()
        keep_index = next((i for i, cp in enumerate(checkpoints) if cp.get("id") == checkpoint_id), None)
        if keep_index is None:
            return 0

        keep = checkpoints[:keep_index + 1]
        drop = checkpoints[keep_index + 1:]
        for cp in drop:
            cp_id = cp.get("id")
            if not cp_id:
                continue
            for path in (
                self.checkpoints_dir / f"{cp_id}.zip",
                self.checkpoints_dir / f"{cp_id}_temp.db",
            ):
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    pass

        self._save_index(keep)
        return len(drop)

    def _collect_workspace_files(self) -> list[Path]:
        """Walk project tree and collect files, with TTL cache."""
        now = time.monotonic()
        if self._walk_cache and (now - self._walk_cache_time) < self._walk_cache_ttl:
            return self._walk_cache

        files: list[Path] = []
        for root, dirs, dir_files in os.walk(self.project_root):
            for d in [d for d in dirs if d in {".git", ".orca", "node_modules", "venv", ".venv", "env"}]:
                dirs.remove(d)
            for file in dir_files:
                file_path = Path(root) / file
                if not self._should_exclude(file_path):
                    files.append(file_path)

        self._walk_cache = files
        self._walk_cache_time = now
        return files

    def _invalidate_walk_cache(self):
        self._walk_cache = None
        self._walk_cache_time = 0

    def _should_exclude(self, path: Path) -> bool:
        try:
            rel_path = path.relative_to(self.project_root)
        except ValueError:
            return True

        parts = rel_path.parts
        ignored_names = {
            ".git", ".orca", "node_modules", "venv", ".venv", "env",
            "__pycache__", ".pytest_cache", ".codewhale", "orcacode.egg-info",
            "rg.exe"
        }
        ignored_exts = {".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".zip", ".tar.gz", ".tgz"}

        for part in parts:
            if part in ignored_names:
                return True
            if part.startswith(".") and part not in (".env", ".env.example", ".gitignore"):
                return True

        if path.suffix.lower() in ignored_exts:
            return True

        return False

    def create_checkpoint(self, description: str, action_type: str = "AI") -> Optional[str]:
        """Creates a new workspace checkpoint (files, history, database).

        Returns:
            checkpoint_id (str) or None if error.
        """
        if self._is_testing_bypass():
            now = datetime.now()
            return f"CP_MOCK_{now.strftime('%Y%m%d_%H%M%S')}"

        now = datetime.now()
        cp_id = f"CP_{now.strftime('%Y%m%d_%H%M%S')}"
        cp_zip_path = self.checkpoints_dir / f"{cp_id}.zip"

        # Collect workspace files (with cache)
        files_to_backup = self._collect_workspace_files()
        self._invalidate_walk_cache()  # next walk will be fresh

        try:
            # Ensure parent directories exist for memory files
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            # Create zip file
            with zipfile.ZipFile(cp_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                # Add workspace files
                workspace_files_rel = []
                for file_path in files_to_backup:
                    rel_path = file_path.relative_to(self.project_root)
                    z.write(file_path, arcname=f"workspace/{rel_path.as_posix()}")
                    workspace_files_rel.append(rel_path.as_posix())

                # Add chat history if exists
                if self.history_path.exists():
                    z.write(self.history_path, arcname="chat_history.json")

                # Add database snapshot if exists
                if self.db_path.exists():
                    temp_db = self.checkpoints_dir / f"{cp_id}_temp.db"
                    try:
                        src = sqlite3.connect(str(self.db_path))
                        dst = sqlite3.connect(str(temp_db))
                        src.backup(dst)
                        dst.close()
                        src.close()
                        z.write(temp_db, arcname="long_memory.db")
                    except (sqlite3.Error, OSError):
                        shutil.copy2(self.db_path, temp_db)
                        z.write(temp_db, arcname="long_memory.db")
                    finally:
                        if temp_db.exists():
                            try:
                                temp_db.unlink()
                            except OSError:
                                pass

            # Save checkpoint metadata
            new_cp = {
                "id": cp_id,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "time_display": now.strftime("%H:%M"),
                "description": description,
                "action_type": action_type,
                "workspace_files": workspace_files_rel
            }

            checkpoints = self.list_checkpoints()
            checkpoints.append(new_cp)
            self._save_index(checkpoints)
            return cp_id
        except (OSError, zipfile.BadZipFile) as e:
            if cp_zip_path.exists():
                try:
                    cp_zip_path.unlink()
                except OSError:
                    pass
            raise e

    def rollback_to(self, checkpoint_id: str, on_db_close_callback=None) -> bool:
        """Rollback workspace state to specified checkpoint."""
        if self._is_testing_bypass():
            return True

        cp_zip_path = self.checkpoints_dir / f"{checkpoint_id}.zip"
        if not cp_zip_path.exists():
            return False

        checkpoints = self.list_checkpoints()
        meta = next((cp for cp in checkpoints if cp["id"] == checkpoint_id), None)
        if not meta:
            return False

        try:
            # 1. Close long memory database
            if on_db_close_callback:
                on_db_close_callback()

            # 2. Collect current workspace files (with cache)
            current_files = self._collect_workspace_files()

            # 3. Read checkpoint and restore files
            with zipfile.ZipFile(cp_zip_path, "r") as z:
                zip_names = z.namelist()
                workspace_files_in_zip = [name for name in zip_names if name.startswith("workspace/")]
                checkpoint_files_rel = {name.replace("workspace/", "") for name in workspace_files_in_zip}

                # Delete current files that are not in the checkpoint
                for cur_file in current_files:
                    rel = cur_file.relative_to(self.project_root).as_posix()
                    if rel not in checkpoint_files_rel:
                        try:
                            cur_file.unlink()
                        except OSError:
                            pass

                # Extract and overwrite files
                for member in workspace_files_in_zip:
                    rel_target = member.replace("workspace/", "")
                    target_path = self.project_root / rel_target
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                # Restore chat history
                if "chat_history.json" in zip_names:
                    self.history_path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open("chat_history.json") as source, open(self.history_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                elif self.history_path.exists():
                    try:
                        self.history_path.unlink()
                    except OSError:
                        pass

                # Restore DB
                if "long_memory.db" in zip_names:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open("long_memory.db") as source, open(self.db_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                elif self.db_path.exists():
                    try:
                        self.db_path.unlink()
                    except OSError:
                        pass

            # Purge all checkpoints after this one (they reference a now-reverted state)
            pruned = self.prune_after(checkpoint_id)
            if pruned:
                logger.info("rollback: pruned %d future checkpoint(s) after %s", pruned, checkpoint_id)

            return True
        except (OSError, zipfile.BadZipFile, KeyError) as e:
            raise e

    def _is_testing_bypass(self) -> bool:
        if "PYTEST_CURRENT_TEST" in os.environ:
            import tempfile
            temp_dir = Path(tempfile.gettempdir()).resolve()
            proj_dir = Path(self.project_root).resolve()
            try:
                proj_dir.relative_to(temp_dir)
                return False
            except ValueError:
                return True
        return False
