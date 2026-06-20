"""CodeGraph Service — Python wrapper for codegraph CLI integration.

Runs codegraph CLI commands via subprocess, parses JSON output,
and provides a high-level API for code intelligence queries.

Usage:
    cg = CodeGraphService(project_root=".")
    if cg.available:
        cg.init_project()        # codegraph init + index
        symbols = cg.search("UserService")
        callers = cg.get_callers("UserService.create")
        context = cg.explore("how does auth work")
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.codegraph")


@dataclass
class CodeGraphSymbol:
    name: str
    kind: str = ""
    file_path: str = ""
    line: int = 0
    column: int = 0
    signature: str = ""
    body: str = ""
    doc: str = ""
    language: str = ""


@dataclass
class CodeGraphEdge:
    source: str = ""
    target: str = ""
    kind: str = ""
    file_path: str = ""
    line: int = 0


@dataclass
class CodeGraphNodeInfo:
    id: str = ""
    name: str = ""
    kind: str = ""
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    body: str = ""
    language: str = ""
    callers: list[CodeGraphSymbol] = field(default_factory=list)
    callees: list[CodeGraphSymbol] = field(default_factory=list)


@dataclass
class CodeGraphExploreResult:
    query: str = ""
    symbols: list[CodeGraphSymbol] = field(default_factory=list)
    flow: Optional[str] = None
    blast_radius: list[CodeGraphSymbol] = field(default_factory=list)
    raw: str = ""


@dataclass
class CodeGraphStatus:
    initialized: bool = False
    indexed: bool = False
    total_files: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    languages: list[str] = field(default_factory=list)
    db_size: str = ""
    version: str = ""


class CodeGraphService:
    """Python wrapper for codegraph CLI with graceful fallback."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self._codegraph_path: Optional[str] = None
        self._available: Optional[bool] = None
        self._node_available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = self._detect_codegraph()
        return self._available

    @property
    def node_available(self) -> bool:
        if self._node_available is None:
            self._node_available = shutil.which("node") is not None
        return self._node_available

    def _detect_codegraph(self) -> bool:
        # 1. Bundled with OrcaCode (dist đã build sẵn)
        local_source = Path(__file__).resolve().parent.parent.parent / "codegraph-main"
        dist_bin = local_source / "dist" / "bin" / "codegraph.js"
        if dist_bin.exists():
            try:
                result = subprocess.run(
                    ["node", str(dist_bin), "version"],
                    capture_output=True, encoding="utf-8", errors="replace",
                    timeout=10, cwd=str(dist_bin.parent),
                )
                if result.returncode == 0:
                    self._codegraph_path = str(dist_bin)
                    logger.info(f"CodeGraph detected (bundled): {dist_bin}")
                    return True
            except Exception:
                pass

        # 2. Global install
        global_cg = shutil.which("codegraph")
        if global_cg:
            try:
                result = subprocess.run(
                    [global_cg, "version"],
                    capture_output=True, encoding="utf-8", errors="replace",
                    timeout=10, cwd=self.project_root,
                )
                if result.returncode == 0:
                    self._codegraph_path = global_cg
                    logger.info(f"CodeGraph detected (global): {global_cg}")
                    return True
            except Exception:
                pass

        # 3. npx fallback
        try:
            result = subprocess.run(
                ["npx", "@colbymchenry/codegraph", "version"],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=15, cwd=self.project_root,
            )
            if result.returncode == 0:
                self._codegraph_path = "npx"
                return True
        except Exception:
            pass

        return False

    def _build_cmd(self, *args: str) -> list[str]:
        if self._codegraph_path is None:
            if not self._detect_codegraph():
                raise RuntimeError("CodeGraph CLI not found")

        cg = self._codegraph_path

        if cg == "npx":
            return ["npx", "@colbymchenry/codegraph", *args]

        if cg.endswith(".js"):
            return ["node", cg, *args]

        return [cg, *args]

    def _run(self, *args: str, timeout: int = 60, cwd: str = None) -> subprocess.CompletedProcess:
        cmd = self._build_cmd(*args)
        work_dir = cwd or str(self.project_root)
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=work_dir,
        )

    def _run_json(self, *args: str, timeout: int = 60, cwd: str = None) -> Optional[dict]:
        result = self._run(*args, timeout=timeout, cwd=cwd)
        if result.returncode != 0:
            logger.warning(f"CodeGraph command failed: {result.stderr.strip()}")
            return None
        stdout = result.stdout.strip()
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning(f"CodeGraph returned non-JSON output")
            return {"_raw": stdout}

    def init_project(self, force: bool = False) -> bool:
        if not self.available:
            return False
        args = ["init", str(self.project_root)]
        if force:
            args.insert(1, "--force")
        result = self._run(*args, timeout=120)
        if result.returncode == 0:
            return True
        logger.warning(f"codegraph init failed: {result.stderr.strip()}")
        return False

    def index_project(self, force: bool = False, quiet: bool = True) -> bool:
        if not self.available:
            return False
        args = ["index", str(self.project_root)]
        if force:
            args.insert(1, "--force")
        if quiet:
            args.insert(1, "--quiet")
        result = self._run(*args, timeout=300)
        if result.returncode == 0:
            return True
        logger.warning(f"codegraph index failed: {result.stderr.strip()}")
        return False

    def get_status(self) -> CodeGraphStatus:
        status = CodeGraphStatus()
        if not self.available:
            return status

        data = self._run_json("status", str(self.project_root), "--json", timeout=10)
        if not data:
            return status

        status.initialized = data.get("initialized", False)
        status.indexed = data.get("indexed", False)
        status.total_files = data.get("totalFiles", data.get("files", 0))
        status.total_nodes = data.get("totalNodes", data.get("nodes", 0))
        status.total_edges = data.get("totalEdges", data.get("edges", 0))
        status.languages = data.get("languages", [])
        status.db_size = data.get("dbSize", data.get("db_size", ""))
        status.version = data.get("version", "")
        return status

    def search(self, query: str, kind: str = None, limit: int = 20) -> list[CodeGraphSymbol]:
        if not self.available:
            return []

        args = ["query", query, "--json", "--limit", str(limit)]
        if kind:
            args.extend(["--kind", kind])

        data = self._run_json(*args, timeout=30)
        if not data:
            return []

        results = data if isinstance(data, list) else data.get("results", [])
        symbols = []
        for item in results:
            symbols.append(CodeGraphSymbol(
                name=item.get("name", ""),
                kind=item.get("kind", ""),
                file_path=item.get("file", item.get("filePath", "")),
                line=item.get("line", 0),
                column=item.get("column", 0),
                signature=item.get("signature", ""),
                language=item.get("language", ""),
            ))
        return symbols

    def explore(self, query: str) -> CodeGraphExploreResult:
        result = CodeGraphExploreResult(query=query)
        if not self.available:
            return result

        data = self._run_json("explore", query, "--json", timeout=60)
        if not data:
            return result

        result.raw = data.get("_raw", "")

        for sym_data in data.get("symbols", []):
            result.symbols.append(CodeGraphSymbol(
                name=sym_data.get("name", ""),
                kind=sym_data.get("kind", ""),
                file_path=sym_data.get("file", sym_data.get("filePath", "")),
                line=sym_data.get("line", 0),
                column=sym_data.get("column", 0),
                signature=sym_data.get("signature", ""),
                body=sym_data.get("body", sym_data.get("source", "")),
                doc=sym_data.get("doc", ""),
                language=sym_data.get("language", ""),
            ))

        result.flow = data.get("flow", data.get("flowSection", None))

        for sym_data in data.get("blastRadius", data.get("blast_radius", [])):
            result.blast_radius.append(CodeGraphSymbol(
                name=sym_data.get("name", ""),
                kind=sym_data.get("kind", ""),
                file_path=sym_data.get("file", ""),
            ))

        return result

    def get_callers(self, symbol: str, limit: int = 30) -> list[CodeGraphSymbol]:
        if not self.available:
            return []
        data = self._run_json("callers", symbol, "--json", "--limit", str(limit), timeout=30)
        if not data:
            return []
        results = data if isinstance(data, list) else data.get("callers", [])
        return [CodeGraphSymbol(
            name=r.get("name", r.get("caller", "")),
            kind=r.get("kind", ""),
            file_path=r.get("file", r.get("filePath", "")),
            line=r.get("line", 0),
            signature=r.get("signature", ""),
        ) for r in results]

    def get_callees(self, symbol: str, limit: int = 30) -> list[CodeGraphSymbol]:
        if not self.available:
            return []
        data = self._run_json("callees", symbol, "--json", "--limit", str(limit), timeout=30)
        if not data:
            return []
        results = data if isinstance(data, list) else data.get("callees", [])
        return [CodeGraphSymbol(
            name=r.get("name", r.get("callee", "")),
            kind=r.get("kind", ""),
            file_path=r.get("file", r.get("filePath", "")),
            line=r.get("line", 0),
        ) for r in results]

    def get_impact(self, symbol: str, depth: int = 3) -> list[CodeGraphSymbol]:
        if not self.available:
            return []
        data = self._run_json("impact", symbol, "--json", "--depth", str(depth), timeout=30)
        if not data:
            return []
        results = data if isinstance(data, list) else data.get("impacted", data.get("results", []))
        return [CodeGraphSymbol(
            name=r.get("name", ""),
            kind=r.get("kind", ""),
            file_path=r.get("file", r.get("filePath", "")),
            line=r.get("line", 0),
        ) for r in results]

    def get_node(self, symbol_or_file: str) -> Optional[CodeGraphNodeInfo]:
        if not self.available:
            return None
        data = self._run_json("node", symbol_or_file, "--json", timeout=30)
        if not data:
            return None

        node = CodeGraphNodeInfo(
            id=data.get("id", ""),
            name=data.get("name", ""),
            kind=data.get("kind", ""),
            file_path=data.get("file", data.get("filePath", "")),
            line_start=data.get("lineStart", data.get("line_start", 0)),
            line_end=data.get("lineEnd", data.get("line_end", 0)),
            body=data.get("body", data.get("source", "")),
            language=data.get("language", ""),
        )

        for c in data.get("callers", []):
            node.callers.append(CodeGraphSymbol(
                name=c.get("name", ""), kind=c.get("kind", ""),
                file_path=c.get("file", ""), line=c.get("line", 0),
            ))

        for c in data.get("callees", []):
            node.callees.append(CodeGraphSymbol(
                name=c.get("name", ""), kind=c.get("kind", ""),
                file_path=c.get("file", ""), line=c.get("line", 0),
            ))

        return node

    def get_files(self, path: str = None, max_depth: int = None,
                  filter_pattern: str = None) -> list[str]:
        if not self.available:
            return []
        args = ["files", str(path or self.project_root), "--json"]
        if max_depth is not None:
            args.extend(["--max-depth", str(max_depth)])
        if filter_pattern:
            args.extend(["--filter", filter_pattern])
        data = self._run_json(*args, timeout=30)
        if not data:
            return []
        if isinstance(data, list):
            return data
        return data.get("files", [])

    def get_affected_tests(self, files: list[str], depth: int = 5,
                           filter_pattern: str = None) -> list[str]:
        if not self.available or not files:
            return []
        args = ["affected", *files, "--json", "--depth", str(depth)]
        if filter_pattern:
            args.extend(["--filter", filter_pattern])
        data = self._run_json(*args, timeout=60)
        if not data:
            return []
        if isinstance(data, list):
            return data
        return data.get("affected", data.get("files", []))

    def is_project_initialized(self) -> bool:
        codegraph_dir = self.project_root / ".codegraph"
        return codegraph_dir.exists() and codegraph_dir.is_dir()

    def ensure_initialized(self, force_index: bool = False) -> bool:
        if not self.available:
            return False
        if not self.is_project_initialized():
            if not self.init_project():
                return False
            return self.index_project(force=force_index)
        if force_index:
            return self.index_project(force=True)
        return True

    def build_context_for_ai(self, query: str, max_symbols: int = 15) -> str:
        if not self.available or not self.is_project_initialized():
            return ""

        explore_result = self.explore(query)
        if not explore_result.symbols:
            return ""

        lines = ["## CodeGraph Intelligence", ""]

        if explore_result.flow:
            lines.append(f"### Flow: {explore_result.flow}")
            lines.append("")

        lines.append("### Relevant Symbols")
        lines.append("")
        for sym in explore_result.symbols[:max_symbols]:
            location = f"{sym.file_path}:{sym.line}" if sym.file_path else "unknown"
            kind_info = f" ({sym.kind})" if sym.kind else ""
            lines.append(f"- **`{sym.name}`**{kind_info} — {location}")
            if sym.signature:
                lines.append(f"  ```\n  {sym.signature}\n  ```")
            if sym.body:
                body_preview = sym.body[:500]
                if len(sym.body) > 500:
                    body_preview += "\n  ..."
                lines.append(f"  ```{sym.language or ''}\n{body_preview}\n  ```")
            lines.append("")

        if explore_result.blast_radius:
            lines.append("### Blast Radius (potentially affected)")
            for sym in explore_result.blast_radius[:10]:
                location = f"{sym.file_path}" if sym.file_path else "unknown"
                lines.append(f"- `{sym.name}` ({sym.kind}) — {location}")

        return "\n".join(lines)
