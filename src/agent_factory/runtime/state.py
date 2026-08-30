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

VALID_INSIGHT_LEVELS = {"low", "info", "warning", "critical"}
VALID_INSIGHT_KINDS = {"friction", "access_gap", "contradiction", "blocker", "opportunity"}
VALID_INSIGHT_STATUSES = {"open", "accepted", "dismissed"}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
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
CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    role TEXT NOT NULL,              -- role id that surfaced the insight
    level TEXT NOT NULL DEFAULT 'info' CHECK (level IN ('low','info','warning','critical')),
    kind TEXT NOT NULL DEFAULT 'friction' CHECK (kind IN ('friction','access_gap','contradiction','blocker','opportunity')),
    title TEXT NOT NULL,
    detail TEXT,
    suggestion TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','accepted','dismissed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,           -- shared Slack-style channel id, e.g. 'general'
    author_role TEXT NOT NULL,       -- 'human' for people, or the role id that answered
    author TEXT NOT NULL,            -- display name of the author
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done
    requested_role TEXT,             -- optional role a human wants to answer
    reply_to INTEGER,                -- message id this one is answering
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
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_status_id ON jobs(status, id);
            CREATE INDEX IF NOT EXISTS idx_results_job_id ON results(job_id, id);
            CREATE INDEX IF NOT EXISTS idx_events_job_id ON events(job_id, id);
            CREATE INDEX IF NOT EXISTS idx_context_updated_id ON context(updated_at, id);
            CREATE INDEX IF NOT EXISTS idx_insights_status ON insights(status, id);
            CREATE INDEX IF NOT EXISTS idx_messages_channel_status ON messages(channel, status, id);
            """
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

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
                """
                UPDATE jobs
                SET status='running', updated_at=datetime('now')
                WHERE id = (
                    SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1
                ) AND status='queued'
                RETURNING *
                """
            ).fetchone()
            return row

    def start(self, job_id: int) -> bool:
        """Atomically transition one queued job to running."""
        with self._tx() as c:
            cur = c.execute(
                "UPDATE jobs SET status='running', updated_at=datetime('now') "
                "WHERE id=? AND status='queued'",
                (job_id,),
            )
            return cur.rowcount == 1

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

    def get_last_error(self, job_id: int) -> str:
        row = self._conn.execute("SELECT error FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row["error"] if row and row["error"] else ""

    def schema_version(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            return 0
        return int(row["value"])

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

    def recent_events(self, limit: int = 60) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
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

    # -- insights --------------------------------------------------------------
    def add_insight(
        self,
        org: str,
        role: str,
        *,
        level: str = "info",
        kind: str = "friction",
        title: str,
        detail: str = "",
        suggestion: str = "",
    ) -> int:
        """Record an observer insight. Returns the new insight id."""
        normalized_level = (level or "info").strip().lower()
        normalized_kind = (kind or "friction").strip().lower()
        if normalized_level not in VALID_INSIGHT_LEVELS:
            raise ValueError(f"invalid insight level: {level!r}")
        if normalized_kind not in VALID_INSIGHT_KINDS:
            raise ValueError(f"invalid insight kind: {kind!r}")
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO insights (org, role, level, kind, title, detail, suggestion) VALUES (?,?,?,?,?,?,?)",
                (org, role, normalized_level, normalized_kind, title, detail, suggestion),
            )
            return int(cur.lastrowid)

    def update_insight_status(self, insight_id: int, status: str) -> None:
        normalized = (status or "").strip().lower()
        if normalized not in VALID_INSIGHT_STATUSES:
            raise ValueError(f"invalid insight status: {status!r}")
        with self._tx() as c:
            c.execute(
                "UPDATE insights SET status=?, updated_at=datetime('now') WHERE id=?",
                (normalized, insight_id),
            )

    def list_insights(
        self,
        *,
        status: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list[sqlite3.Row]:
        q = "SELECT * FROM insights WHERE 1=1"
        params: list = []
        if status:
            q += " AND status=?"
            params.append(status)
        if level:
            q += " AND level=?"
            params.append(level)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._conn.execute(q, params).fetchall()

    # -- shared channel (M6: human<->agent "Loop Alley" queue) ------------------
    def post_message(
        self,
        channel: str,
        author_role: str,
        author: str,
        content: str,
        *,
        requested_role: Optional[str] = None,
        reply_to: Optional[int] = None,
        status: str = "pending",
    ) -> int:
        """Post a message into a shared channel. Returns the new message id.

        Human posts land as ``pending`` (the worker answers them). Agent replies
        are posted ``done`` so a channel worker never re-answers its own output.
        """
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO messages (channel, author_role, author, content, requested_role, reply_to, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (channel, author_role, author, content, requested_role, reply_to, status),
            )
            return int(cur.lastrowid)

    def claim_next_in_channel(self, channel: str) -> Optional[sqlite3.Row]:
        """Atomically claim the oldest pending message in a channel (pending -> running)."""
        with self._tx() as c:
            row = c.execute(
                """
                UPDATE messages
                SET status='running', updated_at=datetime('now')
                WHERE id = (
                    SELECT id FROM messages
                    WHERE channel=? AND status='pending' ORDER BY id LIMIT 1
                ) AND status='pending'
                RETURNING *
                """,
                (channel,),
            ).fetchone()
            return row

    def claim_message(self, message_id: int) -> bool:
        """Atomically transition one pending message to running. True if claimed."""
        with self._tx() as c:
            cur = c.execute(
                "UPDATE messages SET status='running', updated_at=datetime('now') "
                "WHERE id=? AND status='pending'",
                (message_id,),
            )
            return cur.rowcount == 1

    def complete_message(self, message_id: int, status: str = "done") -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE messages SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, message_id),
            )

    def list_messages(
        self, channel: Optional[str] = None, limit: int = 100
    ) -> list[sqlite3.Row]:
        """Newest-first listing; pass ``channel`` to see one conversation thread."""
        if channel is not None:
            return self._conn.execute(
                "SELECT * FROM messages WHERE channel=? ORDER BY id DESC LIMIT ?",
                (channel, limit),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def pending_messages(
        self, channel: Optional[str] = None, limit: int = 100
    ) -> list[sqlite3.Row]:
        """Oldest-first list of messages still waiting for an agent reply."""
        if channel is not None:
            return self._conn.execute(
                "SELECT * FROM messages WHERE channel=? AND status='pending' ORDER BY id ASC LIMIT ?",
                (channel, limit),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM messages WHERE status='pending' ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()

    def channel_blob(self, channel: str = "general", limit: int = 30) -> str:
        """Flatten recent channel traffic into a text block for prompt injection."""
        entries = self._conn.execute(
            "SELECT * FROM messages WHERE channel=? ORDER BY id DESC LIMIT ?",
            (channel, limit),
        ).fetchall()
        if not entries:
            return ""
        blocks = []
        for e in reversed(entries):
            head = f"[{e['author_role']}:{e['author']}]"
            if e["requested_role"]:
                head += f" (-> {e['requested_role']})"
            if e["reply_to"]:
                head += f" (re: #{e['reply_to']})"
            blocks.append(f"{head} {e['content']}")
        return "\n".join(blocks)

    def stats(self) -> dict[str, int]:
        """Small aggregate used by the mission-control report."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
        ).fetchall()
        jobs = {r["status"]: r["n"] for r in rows}
        open_insights = self._conn.execute(
            "SELECT COUNT(*) AS n FROM insights WHERE status='open'"
        ).fetchone()["n"]
        pending_messages = self._conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE status='pending'"
        ).fetchone()["n"]
        total_jobs = self._conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
        return {
            "jobs": total_jobs,
            "queued": jobs.get("queued", 0),
            "running": jobs.get("running", 0),
            "done": jobs.get("done", 0),
            "error": jobs.get("error", 0),
            "blocked": jobs.get("blocked", 0),
            "open_insights": open_insights,
            "pending_messages": pending_messages,
        }

