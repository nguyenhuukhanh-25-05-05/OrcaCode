"""Tests for core.services.file_backup.FileBackup."""

import time
from pathlib import Path

import pytest

from core.services.file_backup import FileBackup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileBackup:

    def test_backup_creates_file(self, tmp_path: Path):
        """backup() phải tạo file .bak trong thư mục backups."""
        _write_text(tmp_path / "hello.py", "print('v1')")
        svc = FileBackup(str(tmp_path))

        result = svc.backup(str(tmp_path / "hello.py"))

        assert result is not None
        bak = Path(result)
        assert bak.exists()
        assert bak.suffix == ".bak"
        assert bak.read_bytes() == b"print('v1')"

    def test_restore_latest(self, tmp_path: Path):
        """restore() mặc định phục hồi bản mới nhất (version=-1)."""
        target = tmp_path / "src" / "app.py"
        _write_text(target, "v1")
        svc = FileBackup(str(tmp_path))

        svc.backup(str(target))
        _write_text(target, "v2")
        svc.backup(str(target))

        # Ghi đè nội dung hiện tại
        _write_text(target, "v3-dirty")

        assert svc.restore(str(target)) is True
        assert _read_text(target) == "v2"

    def test_restore_specific_version(self, tmp_path: Path):
        """restore(version=0) phục hồi bản cũ nhất."""
        target = tmp_path / "data.txt"
        svc = FileBackup(str(tmp_path))

        _write_text(target, "first")
        svc.backup(str(target))
        time.sleep(0.05)  # đảm bảo timestamp khác nhau

        _write_text(target, "second")
        svc.backup(str(target))

        _write_text(target, "current")

        assert svc.restore(str(target), version=0) is True
        assert _read_text(target) == "first"

    def test_prune_old_versions(self, tmp_path: Path):
        """Chỉ giữ lại max_versions bản backup."""
        target = tmp_path / "prune_me.txt"
        svc = FileBackup(str(tmp_path), max_versions=3)

        for i in range(6):
            _write_text(target, f"v{i}")
            svc.backup(str(target))
            time.sleep(0.05)

        versions = svc.list_versions(str(target))
        assert len(versions) == 3

        # Bản còn lại phải là 3 bản mới nhất
        contents = [Path(v["path"]).read_text(encoding="utf-8") for v in versions]
        assert contents == ["v3", "v4", "v5"]

    def test_backup_nonexistent_file(self, tmp_path: Path):
        """backup() trả về None nếu file không tồn tại."""
        svc = FileBackup(str(tmp_path))
        result = svc.backup(str(tmp_path / "does_not_exist.py"))
        assert result is None

    def test_list_versions(self, tmp_path: Path):
        """list_versions() trả về danh sách dict đúng format."""
        target = tmp_path / "versions.txt"
        svc = FileBackup(str(tmp_path))

        # Chưa có backup → danh sách rỗng
        assert svc.list_versions(str(target)) == []

        _write_text(target, "alpha")
        svc.backup(str(target))
        time.sleep(0.05)

        _write_text(target, "beta")
        svc.backup(str(target))

        versions = svc.list_versions(str(target))
        assert len(versions) == 2

        for v in versions:
            assert "path" in v
            assert "timestamp" in v
            assert "size" in v
            assert isinstance(v["size"], int)
            assert v["size"] > 0

    def test_binary_file_backup(self, tmp_path: Path):
        """Backup và restore file nhị phân không bị hỏng dữ liệu."""
        target = tmp_path / "image.bin"
        binary_data = bytes(range(256)) * 4  # 1024 bytes dữ liệu nhị phân
        target.write_bytes(binary_data)

        svc = FileBackup(str(tmp_path))
        bak_path = svc.backup(str(target))
        assert bak_path is not None

        # Ghi đè file gốc
        target.write_bytes(b"\x00" * 10)

        assert svc.restore(str(target)) is True
        assert target.read_bytes() == binary_data

    def test_restore_nonexistent_backup(self, tmp_path: Path):
        """restore() trả về False khi không có bản backup nào."""
        svc = FileBackup(str(tmp_path))
        assert svc.restore(str(tmp_path / "ghost.py")) is False

    def test_restore_invalid_version_index(self, tmp_path: Path):
        """restore() trả về False khi version index ngoài phạm vi."""
        target = tmp_path / "idx.txt"
        _write_text(target, "only one")
        svc = FileBackup(str(tmp_path))
        svc.backup(str(target))

        assert svc.restore(str(target), version=99) is False
