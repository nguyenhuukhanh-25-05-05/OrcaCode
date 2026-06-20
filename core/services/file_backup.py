"""Per-file Backup Service – lưu và phục hồi từng file trước khi chỉnh sửa."""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class FileBackup:
    """Quản lý backup từng file trong workspace.

    Mỗi file được lưu theo cấu trúc:
        {project_root}/.orca/backups/{sanitized_relative_path}/{timestamp}.bak

    Attributes:
        project_root: Đường dẫn gốc của project.
        max_versions: Số lượng bản backup tối đa giữ lại cho mỗi file.
    """

    def __init__(self, project_root: str, max_versions: int = 5):
        self.project_root = Path(project_root).resolve()
        self.max_versions = max_versions
        self.backup_root = self.project_root / ".orca" / "backups"
        self.backup_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backup(self, file_path: str) -> Optional[str]:
        """Tạo bản backup cho *file_path* trước khi chỉnh sửa.

        Args:
            file_path: Đường dẫn tuyệt đối hoặc tương đối (so với project_root)
                       tới file cần backup.

        Returns:
            Đường dẫn tới file backup vừa tạo, hoặc ``None`` nếu file nguồn
            không tồn tại.
        """
        src = self._resolve(file_path)
        if not src.is_file():
            return None

        backup_dir = self._get_backup_dir(file_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = backup_dir / f"{timestamp}.bak"

        # Copy nguyên bytes để hỗ trợ cả file nhị phân
        shutil.copy2(str(src), str(dest))

        self._prune_old_versions(file_path)
        return str(dest)

    def restore(self, file_path: str, version: int = -1) -> bool:
        """Phục hồi file từ bản backup.

        Args:
            file_path: Đường dẫn tới file gốc cần phục hồi.
            version: Chỉ số phiên bản (0 = cũ nhất, -1 = mới nhất).

        Returns:
            ``True`` nếu phục hồi thành công, ``False`` nếu không tìm thấy
            bản backup phù hợp.
        """
        versions = self.list_versions(file_path)
        if not versions:
            return False

        try:
            selected = versions[version]
        except IndexError:
            return False

        backup_path = Path(selected["path"])
        if not backup_path.is_file():
            return False

        target = self._resolve(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(backup_path), str(target))
        return True

    def list_versions(self, file_path: str) -> List[Dict]:
        """Liệt kê tất cả các bản backup của một file.

        Returns:
            Danh sách dict sắp xếp theo thời gian (cũ → mới), mỗi phần tử
            chứa ``'path'``, ``'timestamp'``, ``'size'``.
        """
        backup_dir = self._get_backup_dir(file_path)
        if not backup_dir.is_dir():
            return []

        versions: List[Dict] = []
        for bak_file in sorted(backup_dir.glob("*.bak")):
            stat = bak_file.stat()
            versions.append({
                "path": str(bak_file),
                "timestamp": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "size": stat.st_size,
            })
        return versions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_old_versions(self, file_path: str) -> None:
        """Giữ lại tối đa *max_versions* bản backup, xoá các bản cũ nhất."""
        backup_dir = self._get_backup_dir(file_path)
        if not backup_dir.is_dir():
            return

        backups = sorted(backup_dir.glob("*.bak"))
        while len(backups) > self.max_versions:
            oldest = backups.pop(0)
            oldest.unlink()

    def _get_backup_dir(self, file_path: str) -> Path:
        """Trả về thư mục backup cho một file cụ thể.

        Đường dẫn tương đối của file được *sanitize* bằng cách thay các ký tự
        phân cách thành ``/`` rồi dùng làm sub-directory dưới backup_root.
        """
        resolved = self._resolve(file_path)
        try:
            rel = resolved.relative_to(self.project_root)
        except ValueError:
            # File nằm ngoài project – dùng tên file làm fallback
            rel = Path(resolved.name)

        # Sanitize: dùng từng phần của đường dẫn làm sub-folder
        return self.backup_root / rel

    def _resolve(self, file_path: str) -> Path:
        """Chuyển *file_path* thành đường dẫn tuyệt đối."""
        p = Path(file_path)
        if not p.is_absolute():
            p = self.project_root / p
        return p.resolve()
