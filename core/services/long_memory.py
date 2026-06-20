"""Long-term Memory System — Event Log + Task Memory + Knowledge Base + FTS5 Search.

Architecture:
    Raw Events  → SQLite (with FTS5 full-text search)
    Task Summaries → Markdown files
    Knowledge Base  → Markdown files
    Embeddings     → SQLite (vector index, future)

Search flow:
    Query → FTS5 Search → Top 100
        ↓
    Keyword Search → Top 20
        ↓
    Score Rerank → Top 5

Usage:
    mem = LongMemory(project_root=".")
    mem.log_event("edit_file", file="Login.vue", summary="Added token refresh")
    mem.log_event("run_command", command="npm test", summary="Tests passed")
    mem.complete_task("Fix Login", files=["Login.vue", "auth.js"],
                      result="success", lessons="Token refresh required")
    results = mem.search("authentication login token", limit=5)
"""
import sqlite3
import json
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from rich.console import Console

console = Console()

# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    action TEXT NOT NULL,
    file TEXT DEFAULT '',
    command TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    details TEXT DEFAULT '',
    task_id INTEGER,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    time_start TEXT NOT NULL,
    time_end TEXT DEFAULT '',
    files TEXT DEFAULT '[]',
    result TEXT DEFAULT 'pending',
    lessons TEXT DEFAULT '',
    summary_md TEXT DEFAULT '',
    event_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name TEXT NOT NULL,
    pattern_text TEXT NOT NULL,
    source_tasks TEXT DEFAULT '[]',
    occurrence_count INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    action, file, summary, details
);

CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    name, files, lessons, summary_md
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    pattern_name, pattern_text
);
"""

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, action, file, summary, details)
    VALUES (new.id, new.action, new.file, new.summary, new.details);
END;

CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, name, files, lessons, summary_md)
    VALUES (new.id, new.name, new.files, new.lessons, new.summary_md);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, pattern_name, pattern_text)
    VALUES (new.id, new.pattern_name, new.pattern_text);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
    DELETE FROM knowledge_fts WHERE rowid = old.id;
    INSERT INTO knowledge_fts(rowid, pattern_name, pattern_text)
    VALUES (new.id, new.pattern_name, new.pattern_text);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
    DELETE FROM knowledge_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
    DELETE FROM events_fts WHERE rowid = old.id;
    INSERT INTO events_fts(rowid, action, file, summary, details)
    VALUES (new.id, new.action, new.file, new.summary, new.details);
END;

CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
    DELETE FROM events_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
    DELETE FROM tasks_fts WHERE rowid = old.id;
    INSERT INTO tasks_fts(rowid, name, files, lessons, summary_md)
    VALUES (new.id, new.name, new.files, new.lessons, new.summary_md);
END;

CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
    DELETE FROM tasks_fts WHERE rowid = old.id;
END;
"""


@dataclass
class Event:
    id: int = 0
    time: str = ""
    action: str = ""
    file: str = ""
    command: str = ""
    summary: str = ""
    details: str = ""
    task_id: int = 0


@dataclass
class Task:
    id: int = 0
    name: str = ""
    time_start: str = ""
    time_end: str = ""
    files: list[str] = field(default_factory=list)
    result: str = "pending"
    lessons: str = ""
    summary_md: str = ""
    event_count: int = 0


@dataclass
class Knowledge:
    id: int = 0
    pattern_name: str = ""
    pattern_text: str = ""
    source_tasks: list[int] = field(default_factory=list)
    occurrence_count: int = 1
    created: str = ""
    updated: str = ""


class LongMemory:
    """SQLite + FTS5 based long-term memory system.

    Stores events, tasks, and knowledge base with full-text search.
    Supports searching across millions of records efficiently.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.db_dir = self.project_root / ".orca" / "memory"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "long_memory.db"
        self._local = threading.local()
        self._all_connections: list[sqlite3.Connection] = []
        self._conn_lock = threading.Lock()
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        """Thread-safe SQLite connection — creates a new one per thread using thread local storage."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
            with self._conn_lock:
                self._all_connections.append(conn)
        return self._local.conn

    def _ensure_schema(self):
        """Create tables and FTS indexes if they don't exist.
        Must be called once per thread before using conn.
        """
        conn_local = self.conn  # Gets thread-safe connection
        conn_local.executescript(SCHEMA_SQL)
        try:
            conn_local.executescript(TRIGGERS_SQL)
        except sqlite3.OperationalError:
            pass
        conn_local.commit()

    def close(self):
        with self._conn_lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None

    # ─── Event Log ────────────────────────────────────────────────────────────

    def log_event(self, action: str, file: str = "", command: str = "",
                  summary: str = "", details: str = "", task_id: int = 0) -> int:
        """Log a single event. Returns the event ID.

        Actions: edit_file, create_file, delete_file, run_command,
                 search, read_file, error, fix_error, etc.
        """
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO events (time, action, file, command, summary, details, task_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, action, file, command, summary, details, task_id or None)
        )
        self.conn.commit()
        return cur.lastrowid

    def log_file_event(self, action: str, file_path: str, summary: str = "",
                       task_id: int = 0) -> int:
        """Convenience: log a file-related event."""
        return self.log_event(action=action, file=file_path, summary=summary, task_id=task_id)

    def log_command_event(self, command: str, summary: str = "",
                          task_id: int = 0) -> int:
        """Convenience: log a command execution event."""
        return self.log_event(action="run_command", command=command, summary=summary, task_id=task_id)

    def get_events(self, limit: int = 100, action: str = "",
                   file: str = "", task_id: int = 0) -> list[Event]:
        """Get events with optional filters."""
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        if action:
            query += " AND action = ?"
            params.append(action)
        if file:
            query += " AND file = ?"
            params.append(file)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count_events(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    # ─── Task Memory ──────────────────────────────────────────────────────────

    def start_task(self, name: str, files: list[str] = None) -> int:
        """Start a new task. Returns the task ID."""
        now = datetime.now().isoformat()
        files_json = json.dumps(files or [])
        cur = self.conn.execute(
            "INSERT INTO tasks (name, time_start, files, result) VALUES (?, ?, ?, 'pending')",
            (name, now, files_json)
        )
        self.conn.commit()
        return cur.lastrowid

    def complete_task(self, name: str, files: list[str] = None,
                      result: str = "success", lessons: str = "",
                      summary_md: str = "") -> int:
        """Complete a task in one call (creates + completes).

        This is the primary API for task completion.
        Returns the task ID.
        """
        now = datetime.now().isoformat()
        files_json = json.dumps(files or [])

        # Check if task already exists (by name, recently started)
        existing = self.conn.execute(
            "SELECT id FROM tasks WHERE name = ? AND result = 'pending' "
            "ORDER BY id DESC LIMIT 1", (name,)
        ).fetchone()

        if existing:
            task_id = existing["id"]
            self.conn.execute(
                "UPDATE tasks SET time_end=?, files=?, result=?, lessons=?, "
                "summary_md=? WHERE id=?",
                (now, files_json, result, lessons, summary_md, task_id)
            )
        else:
            cur = self.conn.execute(
                "INSERT INTO tasks (name, time_start, time_end, files, result, lessons, summary_md) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, now, now, files_json, result, lessons, summary_md)
            )
            task_id = cur.lastrowid

        # Update event count for this task
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE task_id=?", (task_id,)
        ).fetchone()[0]
        self.conn.execute(
            "UPDATE tasks SET event_count=? WHERE id=?", (count, task_id)
        )
        self.conn.commit()
        return task_id

    def get_tasks(self, limit: int = 50, result: str = "") -> list[Task]:
        """Get tasks with optional result filter."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if result:
            query += " AND result = ?"
            params.append(result)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def count_tasks(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    # ─── Knowledge Base ───────────────────────────────────────────────────────

    def add_knowledge(self, pattern_name: str, pattern_text: str,
                      source_task_id: int = 0) -> int:
        """Add or update a knowledge pattern.

        If a similar pattern already exists, increment its occurrence count.
        """
        now = datetime.now().isoformat()

        # Check for existing similar pattern (by name)
        existing = self.conn.execute(
            "SELECT id, source_tasks, occurrence_count FROM knowledge "
            "WHERE pattern_name = ?", (pattern_name,)
        ).fetchone()

        if existing:
            tasks = json.loads(existing["source_tasks"])
            if source_task_id and source_task_id not in tasks:
                tasks.append(source_task_id)
            self.conn.execute(
                "UPDATE knowledge SET pattern_text=?, source_tasks=?, "
                "occurrence_count=?, updated=? WHERE id=?",
                (pattern_text, json.dumps(tasks),
                 existing["occurrence_count"] + 1, now, existing["id"])
            )
            self.conn.commit()
            return existing["id"]
        else:
            tasks = [source_task_id] if source_task_id else []
            cur = self.conn.execute(
                "INSERT INTO knowledge (pattern_name, pattern_text, source_tasks, "
                "occurrence_count, created, updated) VALUES (?, ?, ?, 1, ?, ?)",
                (pattern_name, pattern_text, json.dumps(tasks), now, now)
            )
            self.conn.commit()
            return cur.lastrowid

    def get_knowledge(self, limit: int = 50) -> list[Knowledge]:
        rows = self.conn.execute(
            "SELECT * FROM knowledge ORDER BY occurrence_count DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._row_to_knowledge(r) for r in rows]

    def count_knowledge(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]

    # ─── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search across events, tasks, and knowledge using FTS5.

        Returns a unified list of results sorted by relevance.
        Each result has: type, id, name/summary, score, details.
        """
        results = []
        query_clean = self._clean_fts_query(query)

        if not query_clean:
            return results

        # Search events via FTS5
        try:
            event_rows = self.conn.execute(
                "SELECT e.id, e.action, e.file, e.summary, e.details, "
                "f.rank FROM events_fts f "
                "JOIN events e ON e.id = f.rowid "
                "WHERE events_fts MATCH ? ORDER BY f.rank LIMIT ?",
                (query_clean, min(limit * 2, 200))
            ).fetchall()
            for r in event_rows:
                results.append({
                    "type": "event",
                    "id": r["id"],
                    "name": f"{r['action']}: {r['summary'] or r['file']}",
                    "file": r["file"],
                    "details": r["details"],
                    "score": abs(r["rank"]),
                })
        except sqlite3.OperationalError:
            pass

        # Search tasks via FTS5
        try:
            task_rows = self.conn.execute(
                "SELECT t.id, t.name, t.files, t.lessons, t.summary_md, "
                "f.rank FROM tasks_fts f "
                "JOIN tasks t ON t.id = f.rowid "
                "WHERE tasks_fts MATCH ? ORDER BY f.rank LIMIT ?",
                (query_clean, min(limit * 2, 100))
            ).fetchall()
            for r in task_rows:
                results.append({
                    "type": "task",
                    "id": r["id"],
                    "name": r["name"],
                    "files": r["files"],
                    "lessons": r["lessons"],
                    "score": abs(r["rank"]),
                })
        except sqlite3.OperationalError:
            pass

        # Search knowledge via FTS5
        try:
            knowledge_rows = self.conn.execute(
                "SELECT k.id, k.pattern_name, k.pattern_text, "
                "k.occurrence_count, f.rank FROM knowledge_fts f "
                "JOIN knowledge k ON k.id = f.rowid "
                "WHERE knowledge_fts MATCH ? ORDER BY f.rank LIMIT ?",
                (query_clean, min(limit * 2, 50))
            ).fetchall()
            for r in knowledge_rows:
                results.append({
                    "type": "knowledge",
                    "id": r["id"],
                    "name": r["pattern_name"],
                    "text": r["pattern_text"],
                    "occurrences": r["occurrence_count"],
                    "score": abs(r["rank"]),
                })
        except sqlite3.OperationalError:
            pass

        # Fallback: keyword search if FTS5 returns nothing
        if not results:
            results = self._keyword_search(query, limit)

        # Sort by score (lower rank = better in FTS5, but we converted)
        # Boost knowledge (learned patterns are most valuable)
        for r in results:
            if r["type"] == "knowledge":
                r["score"] *= 0.5  # Boost knowledge
            elif r["type"] == "task":
                r["score"] *= 0.7  # Boost tasks
            else:
                r["score"] *= 1.0  # Events are baseline

        results.sort(key=lambda x: x["score"])
        return results[:limit]

    def _keyword_search(self, query: str, limit: int) -> list[dict]:
        """Fallback keyword search using LIKE queries."""
        results = []
        keywords = query.lower().split()
        if not keywords:
            return results

        # Build LIKE conditions
        like_conditions = " OR ".join(
            ["(LOWER(summary) LIKE ? OR LOWER(file) LIKE ? OR LOWER(details) LIKE ?)"]
            * len(keywords)
        )
        params = []
        for kw in keywords:
            pat = f"%{kw}%"
            params.extend([pat, pat, pat])

        try:
            rows = self.conn.execute(
                f"SELECT id, action, file, summary, details FROM events "
                f"WHERE {like_conditions} ORDER BY id DESC LIMIT ?",
                params + [limit * 2]
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "event",
                    "id": r["id"],
                    "name": f"{r['action']}: {r['summary'] or r['file']}",
                    "file": r["file"],
                    "score": 2.0,
                })
        except Exception:
            pass

        return results

    def _clean_fts_query(self, query: str) -> str:
        """Clean query for FTS5 — remove special characters, use OR for broader matching."""
        # Remove FTS5 special chars
        cleaned = query.replace('"', '').replace("'", "").replace('*', '')
        # Split into words, filter short ones, join with OR for broader matching
        words = [w for w in cleaned.split() if len(w) > 1]
        if not words:
            return ""
        return " OR ".join(words)

    # ─── Context Building for AI ──────────────────────────────────────────────

    def build_context_for_query(self, query: str, max_tokens: int = 2000) -> str:
        """Build a focused context string for AI based on a search query.

        This is the key filtering: millions of records → ~100 lines of relevant context.
        """
        results = self.search(query, limit=10)
        if not results:
            return ""

        lines = [f"## Long-term Memory (query: {query})", ""]

        # Group by type
        knowledge_results = [r for r in results if r["type"] == "knowledge"]
        task_results = [r for r in results if r["type"] == "task"]
        event_results = [r for r in results if r["type"] == "event"]

        # Knowledge first (most valuable)
        if knowledge_results:
            lines.append("### Knowledge Patterns:")
            for k in knowledge_results[:5]:
                lines.append(f"- **{k['name']}** (used {k.get('occurrences', 1)} times)")
                if k.get("text"):
                    lines.append(f"  {k['text'][:200]}")

        # Then tasks
        if task_results:
            lines.append("\n### Related Tasks:")
            for t in task_results[:5]:
                result_icon = "+" if t.get("lessons") else "?"
                lines.append(f"- [{result_icon}] {t['name']}")
                if t.get("lessons"):
                    lines.append(f"  Lessons: {t['lessons'][:150]}")

        # Then recent events
        if event_results:
            lines.append("\n### Recent Events:")
            for e in event_results[:5]:
                lines.append(f"- {e['name']}")

        context = "\n".join(lines)
        # Truncate if too long
        if len(context) > max_tokens * 4:  # ~4 chars per token
            context = context[:max_tokens * 4] + "\n... (truncated)"

        return context

    # ─── Export / Stats ───────────────────────────────────────────────────────

    def export_task_markdown(self, task_id: int) -> str:
        """Export a task as Markdown."""
        task = self.get_task(task_id)
        if not task:
            return ""

        lines = [
            f"# Task: {task.name}",
            f"Started: {task.time_start}",
            f"Ended: {task.time_end}",
            f"Result: {task.result}",
            "",
        ]
        if task.files:
            lines.append("## Files")
            for f in task.files:
                lines.append(f"- {f}")
            lines.append("")

        if task.lessons:
            lines.append("## Lessons")
            lines.append(task.lessons)
            lines.append("")

        # Get events for this task
        events = self.get_events(task_id=task_id, limit=100)
        if events:
            lines.append("## Events")
            for e in events:
                lines.append(f"- [{e.time}] {e.action}: {e.summary or e.file}")
            lines.append("")

        return "\n".join(lines)

    def export_knowledge_markdown(self) -> str:
        """Export all knowledge as a Markdown document."""
        knowledge = self.get_knowledge(limit=100)
        if not knowledge:
            return "# Knowledge Base\n\nNo patterns learned yet."

        lines = ["# Knowledge Base", f"Patterns: {len(knowledge)}", ""]

        # Group by occurrence count
        high = [k for k in knowledge if k.occurrence_count >= 5]
        medium = [k for k in knowledge if 2 <= k.occurrence_count < 5]
        low = [k for k in knowledge if k.occurrence_count < 2]

        if high:
            lines.append("## Frequently Used Patterns")
            for k in high:
                lines.append(f"### {k.pattern_name} ({k.occurrence_count}x)")
                lines.append(k.pattern_text)
                lines.append("")

        if medium:
            lines.append("## Known Patterns")
            for k in medium:
                lines.append(f"- **{k.pattern_name}** ({k.occurrence_count}x): {k.pattern_text[:100]}")
            lines.append("")

        if low:
            lines.append("## Observed Patterns")
            for k in low:
                lines.append(f"- {k.pattern_name}: {k.pattern_text[:80]}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "events": self.count_events(),
            "tasks": self.count_tasks(),
            "knowledge": self.count_knowledge(),
            "db_size_kb": round(self.db_path.stat().st_size / 1024, 1) if self.db_path.exists() else 0,
        }

    # ─── Row Converters ───────────────────────────────────────────────────────

    def _row_to_event(self, row) -> Event:
        return Event(
            id=row["id"], time=row["time"], action=row["action"],
            file=row["file"], command=row["command"], summary=row["summary"],
            details=row["details"], task_id=row["task_id"] or 0,
        )

    def _row_to_task(self, row) -> Task:
        return Task(
            id=row["id"], name=row["name"],
            time_start=row["time_start"], time_end=row["time_end"],
            files=json.loads(row["files"]) if row["files"] else [],
            result=row["result"], lessons=row["lessons"],
            summary_md=row["summary_md"], event_count=row["event_count"],
        )

    def _row_to_knowledge(self, row) -> Knowledge:
        return Knowledge(
            id=row["id"], pattern_name=row["pattern_name"],
            pattern_text=row["pattern_text"],
            source_tasks=json.loads(row["source_tasks"]) if row["source_tasks"] else [],
            occurrence_count=row["occurrence_count"],
            created=row["created"], updated=row["updated"],
        )