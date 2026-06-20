"""KnowledgeFreshness — phát hiện và tự động refresh cached knowledge.

Vấn đề:
  DependencyGraph, SymbolDepGraph, ApiRegistry được build một lần
  ở iteration đầu. Sau 100+ iterations, codebase thay đổi nhiều
  nhưng các graph này vẫn dùng dữ liệu cũ → tín hiệu đúng nhưng hết hạn.

Giải pháp:
  - Track mtime của mọi file đã scan
  - Khi modified_files có file cũ, tự động refresh (incremental nếu được)
  - Format context injection: cho biết trạng thái freshness
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("orca.freshness")


@dataclass
class FreshnessStatus:
    """Trạng thái freshness của một knowledge source."""
    name: str                  # "dependency_graph", "symbol_dep_graph", "api_registry"
    total_files: int = 0       # Số files đã scan
    stale_files: int = 0       # Số files cần refresh
    last_build_iteration: int = 0
    is_fresh: bool = True


class KnowledgeFreshness:
    """Quản lý freshness của cached knowledge.

    Usage:
        kf = KnowledgeFreshness(project_root, dep_graph, symdep, api)
        kf.record_build(iteration)
        # Sau mỗi iteration:
        status = kf.verify(iteration, modified_files)
        if not status.is_fresh:
            context = kf.format_context()
    """

    def __init__(
        self,
        project_root: Path,
        dep_graph: object,
        symbol_dep_graph: object,
        api_registry: object,
    ):
        self._root = project_root
        self._dep_graph = dep_graph
        self._symdep = symbol_dep_graph
        self._api = api_registry

        # Track file mtimes at build time
        self._file_mtimes: dict[str, float] = {}          # rel_path → mtime
        self._dep_graph_files: set[str] = set()            # files known to dep_graph
        self._symdep_files: set[str] = set()               # files known to symdep
        self._api_files: set[str] = set()                  # files known to api

        self._last_build_iteration: int = 0
        self._last_verify_iteration: int = 0
        self._total_files_scanned: int = 0

        # Track per-source freshness
        self._dep_fresh = True
        self._symdep_fresh = True
        self._api_fresh = True

    # ── Build lifecycle ──────────────────────────────────────────────

    def record_build(self, iteration: int) -> None:
        """Ghi lại trạng thái sau khi build graph."""
        self._last_build_iteration = iteration
        self._file_mtimes.clear()
        self._dep_graph_files.clear()
        self._symdep_files.clear()
        self._api_files.clear()

        # Collect files từ mỗi source
        try:
            if hasattr(self._dep_graph, '_nodes'):
                self._dep_graph_files = set(self._dep_graph._nodes.keys())
                for f in self._dep_graph_files:
                    self._record_mtime(f)
        except Exception:
            pass
        try:
            if hasattr(self._symdep, '_callers_of'):
                # Collect all files from callers
                for callers in self._symdep._callers_of.values():
                    for c in callers:
                        f = c.caller_file
                        self._symdep_files.add(f)
                        self._record_mtime(f)
        except Exception:
            pass
        try:
            if hasattr(self._api, 'exported'):
                self._api_files = set(self._api.exported.keys())
                for f in self._api_files:
                    self._record_mtime(f)
        except Exception:
            pass

        self._total_files_scanned = len(self._file_mtimes)
        logger.debug("Freshness: recorded build at iter %d (%d files)",
                     iteration, self._total_files_scanned)

    def _record_mtime(self, rel_path: str) -> None:
        """Ghi mtime của một file (nếu chưa có)."""
        if rel_path in self._file_mtimes:
            return
        try:
            full = self._root / rel_path
            if full.exists():
                self._file_mtimes[rel_path] = full.stat().st_mtime
        except Exception:
            pass

    # ── Verify freshness ─────────────────────────────────────────────

    def verify(self, iteration: int, modified_files: set[str]) -> FreshnessStatus:
        """Kiểm tra freshness. Tự động refresh nếu stale.

        Returns:
            FreshnessStatus với is_fresh flag.
        """
        if not self._file_mtimes:
            return FreshnessStatus("all")

        self._last_verify_iteration = iteration
        stale_dep: set[str] = set()
        stale_symdep: set[str] = set()
        stale_api: set[str] = set()

        # Compare mtimes của files đã scan với modified_files
        for f in modified_files:
            norm_f = f.replace("\\", "/")
            old_mtime = self._file_mtimes.get(norm_f)
            if old_mtime is None:
                continue  # File not in any graph — ignore
            try:
                current_mtime = (self._root / norm_f).stat().st_mtime
            except Exception:
                continue
            if current_mtime > old_mtime:
                # Stale! Track which graphs are affected
                if norm_f in self._dep_graph_files:
                    stale_dep.add(norm_f)
                if norm_f in self._symdep_files:
                    stale_symdep.add(norm_f)
                if norm_f in self._api_files:
                    stale_api.add(norm_f)
                # Update mtime
                self._file_mtimes[norm_f] = current_mtime

        # Mark stale → refresh
        total_stale = len(stale_dep) + len(stale_symdep) + len(stale_api)

        if stale_dep:
            self._dep_fresh = False
            self._refresh_dep(stale_dep)
        if stale_symdep:
            self._symdep_fresh = False
            self._refresh_symdep()
        if stale_api:
            self._api_fresh = False
            self._refresh_api(stale_api)

        is_fresh = (not stale_dep and not stale_symdep and not stale_api)
        return FreshnessStatus(
            name="all",
            total_files=self._total_files_scanned,
            stale_files=total_stale,
            last_build_iteration=self._last_build_iteration,
            is_fresh=is_fresh,
        )

    # ── Refresh logic ────────────────────────────────────────────────

    def _refresh_dep(self, stale_files: set[str]) -> None:
        """Incremental refresh cho dependency graph."""
        count = 0
        for f in stale_files:
            try:
                self._dep_graph.refresh_file(f)
                count += 1
            except Exception as exc:
                logger.debug("Freshness: dep_graph refresh %s failed: %s", f, exc)
        if count:
            self._dep_fresh = True
            logger.debug("Freshness: dep_graph refreshed %d files", count)

    def _refresh_symdep(self) -> None:
        """SymbolDepGraph không support incremental → full rebuild."""
        try:
            count = self._symdep.build(self._root)
            self._symdep_fresh = True
            # Re-collect file list
            self._symdep_files.clear()
            for callers in self._symdep._callers_of.values():
                for c in callers:
                    self._symdep_files.add(c.caller_file)
            logger.debug("Freshness: symdep rebuilt (%d files)", count)
        except Exception as exc:
            logger.debug("Freshness: symdep rebuild failed: %s", exc)

    def _refresh_api(self, stale_files: set[str]) -> None:
        """Incremental refresh cho API registry via update()."""
        count = 0
        for f in stale_files:
            try:
                content = (self._root / f).read_text(encoding="utf-8", errors="replace")
                # Extract symbols using semantic_detector
                from core.services.semantic_detector import SemanticDetector
                sd = SemanticDetector()
                fs = sd.extract_symbols(f, content)
                if fs:
                    self._api.update(f, fs.symbols)
                    count += 1
            except Exception as exc:
                logger.debug("Freshness: api refresh %s failed: %s", f, exc)
        if count:
            self._api_fresh = True
            logger.debug("Freshness: api refreshed %d files", count)

    # ── Context ──────────────────────────────────────────────────────

    def format_context(self) -> str:
        """Format freshness status for context injection.

        Returns empty string if everything is fresh.
        """
        if (self._dep_fresh and self._symdep_fresh and self._api_fresh
                and self._total_files_scanned > 0):
            return ""

        parts = ["## Knowledge Freshness:"]
        if not self._dep_fresh and self._dep_graph_files:
            parts.append(f"  [WARN] Dependency graph stale ({len(self._dep_graph_files)} files)")
        if not self._symdep_fresh and self._symdep_files:
            parts.append(f"  [WARN] Symbol dependency graph stale ({len(self._symdep_files)} files)")
        if not self._api_fresh and self._api_files:
            parts.append(f"  [WARN] API registry stale ({len(self._api_files)} files)")

        if self._total_files_scanned > 0:
            parts.append(f"  Last build: iter {self._last_build_iteration}, "
                         f"{self._total_files_scanned} files tracked")

        return "\n".join(parts) if len(parts) > 1 else ""
