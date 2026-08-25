"""SQLite-backed durable state: job queue, results ledger, and event log.

This is the "pull-based" job store that lets workers hand off work observably.
The interface is intentionally narrow so it can be swapped for Postgres later
(M5) without touching the agent loop.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    role TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued|running|done|error|blocked
    provider TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    role TEXT NOT NULL,
    output TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    type TEXT NOT NULL,   -- info|tool_call|approval|error
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,                 -- e.g. 'diary/2026-08-21', 'ambition/<slug>'
    content TEXT,
    source TEXT,                     -- 'diary' | 'ambition' | 'decision' | ...
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.name != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- jobs ----------------------------------------------------------------
    def enqueue(self, org: str, role: str, task: str, provider: Optional[str] = None) -> int:
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO jobs (org, role, task, provider) VALUES (?,?,?,?)",
                (org, role, task, provider),
            )
            return int(cur.lastrowid)

    def pull_next(self) -> Optional[sqlite3.Row]:
        """Claim the oldest 'queued' job (mark it running). Returns the row or None."""
        with self._tx() as c:
            row = c.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            c.execute(
                "UPDATE jobs SET status='running', updated_at=datetime('now') WHERE id=?",
                (row["id"],),
            )
            return row

    def complete(self, job_id: int, result: str) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE jobs SET status='done', result=?, updated_at=datetime('now') WHERE id=?",
                (result, job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE jobs SET status='error', error=?, updated_at=datetime('now') WHERE id=?",
                (error, job_id),
            )

    def block(self, job_id: int, reason: str) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE jobs SET status='blocked', error=?, updated_at=datetime('now') WHERE id=?",
                (reason, job_id),
            )

    def get(self, job_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> list[sqlite3.Row]:
        if status:
            return self._conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    # -- results / events ----------------------------------------------------
    def add_result(self, job_id: int, role: str, output: str) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO results (job_id, role, output) VALUES (?,?,?)",
                (job_id, role, output),
            )

    def results_for(self, job_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM results WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()

    def add_event(self, job_id: int, type_: str, detail: str) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO events (job_id, type, detail) VALUES (?,?,?)",
                (job_id, type_, detail),
            )

    def events_for(self, job_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM events WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()
    # -- context ---------------------------------------------------------------
    def upsert_context(self, key: str, content: str, source: str = "") -> None:
        """Insert or update a context entry by key (diary flow / ambition notes)."""
        with self._tx() as c:
            c.execute(
                """
                INSERT INTO context (key, content, source, updated_at)
                VALUES (?,?,?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    content=excluded.content,
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                (key, content, source),
            )

    def get_context(self, key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM context WHERE key=?", (key,)).fetchone()

    def list_context(self, limit: int = 100) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT key, source, content, updated_at FROM context ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def search_context(self, term: str, limit: int = 50) -> list[sqlite3.Row]:
        like = f"%{term}%"
        return self._conn.execute(
            "SELECT * FROM context WHERE content LIKE ? OR key LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, limit),
        ).fetchall()

    def context_blob(self, limit: int = 200) -> str:
        """Flatten recent context into a text block for prompt injection."""
        entries = self._conn.execute(
            "SELECT key, source, content FROM context ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not entries:
            return ""
        blocks = []
        for e in reversed(entries):
            head = f"[{e['key']}]" + (f" ({e['source']})" if e["source"] else "")
            blocks.append(f"{head}\n{e['content']}")
        return "\n\n".join(blocks)

