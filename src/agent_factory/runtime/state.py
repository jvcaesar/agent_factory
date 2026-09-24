"""SQLite-backed durable state: job queue, results ledger, and event log.

This is the "pull-based" job store that lets workers hand off work observably.
The interface is intentionally narrow so it can be swapped for Postgres later
(M5) without touching the agent loop.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

VALID_INSIGHT_LEVELS = {"low", "info", "warning", "critical"}
VALID_INSIGHT_KINDS = {"friction", "access_gap", "contradiction", "blocker", "opportunity"}
VALID_INSIGHT_STATUSES = {"open", "accepted", "dismissed"}
CURRENT_SCHEMA_VERSION = 3
VALID_OPERATION_STATUSES = {
    "queued",
    "running",
    "done",
    "error",
    "blocked",
    "cancelled",
}
VALID_APPROVAL_RISKS = {"low", "medium", "high"}
VALID_APPROVAL_STATUSES = {"pending", "approved", "denied", "expired", "cancelled"}
TERMINAL_OPERATION_STATUSES = {"done", "error", "blocked", "cancelled"}
OPERATION_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": TERMINAL_OPERATION_STATUSES,
}
OPERATION_DEFAULTS = {
    "run": {"provider": None, "model": None, "approval_mode": "deny"},
    "ambition": {
        "max_actions": 3,
        "max_risk": "medium",
        "approval_mode": "deny",
        "provider": None,
        "model": None,
    },
    "observe": {"role": None, "provider": None, "model": None},
    "brief": {"role": None, "provider": None, "model": None},
    "channel_worker": {
        "role": None,
        "max_messages": 10,
        "approval_mode": "deny",
        "provider": None,
        "model": None,
    },
}
OPERATION_REQUIRED = {
    "run": {"role", "task"},
    "ambition": {"role"},
    "observe": set(),
    "brief": set(),
    "channel_worker": {"channel"},
}


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

_OPERATIONS_SCHEMA = """
CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    kind TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    result TEXT,
    error TEXT,
    job_id INTEGER REFERENCES jobs(id),
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_APPROVALS_SCHEMA = """
CREATE TABLE approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    job_id INTEGER REFERENCES jobs(id),
    operation_id INTEGER REFERENCES operations(id),
    role TEXT NOT NULL,
    tool TEXT NOT NULL,
    action_args TEXT NOT NULL DEFAULT '{}',
    risk TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'pending',
    decided_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT
)
"""


def normalize_operation_params(kind: str, params: Mapping[str, object]) -> dict[str, object]:
    """Validate and default one operation payload for durable canonical storage."""
    if kind not in OPERATION_DEFAULTS:
        raise ValueError(f"invalid operation kind: {kind!r}")
    if not isinstance(params, Mapping):
        raise TypeError("operation params must be a mapping")

    allowed = set(OPERATION_DEFAULTS[kind]) | OPERATION_REQUIRED[kind]
    unknown = set(params) - allowed
    if unknown:
        raise ValueError(f"unknown {kind} operation params: {sorted(unknown)!r}")

    normalized = {**OPERATION_DEFAULTS[kind], **dict(params)}
    for field in OPERATION_REQUIRED[kind]:
        value = normalized.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{kind} operation requires non-empty {field!r}")
        normalized[field] = value.strip()

    for field in ("role", "channel", "provider", "model"):
        value = normalized.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"operation param {field!r} must be a non-empty string or null")
        if isinstance(value, str):
            normalized[field] = value.strip()

    if "approval_mode" in normalized and normalized["approval_mode"] not in {
        "allow",
        "deny",
        "ask",
    }:
        raise ValueError("approval_mode must be 'allow', 'deny', or 'ask'")
    if "max_risk" in normalized and normalized["max_risk"] not in {
        "low",
        "medium",
        "high",
    }:
        raise ValueError("max_risk must be 'low', 'medium', or 'high'")
    for field in ("max_actions", "max_messages"):
        value = normalized.get(field)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
            raise ValueError(f"operation param {field!r} must be a positive integer")

    json.dumps(normalized)
    return normalized


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._memory = self.path.name == ":memory:"
        if not self._memory:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._database = (
            f"file:agent_factory_{id(self)}?mode=memory&cache=shared"
            if self._memory
            else str(self.path)
        )
        self._uri = self._memory
        self._local = threading.local()
        self._connections: set[sqlite3.Connection] = set()
        self._connections_lock = threading.Lock()
        self._write_lock = threading.RLock()
        self._closed = False

        connection = self._connection()
        with self._write_lock:
            connection.executescript(_SCHEMA)
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_status_id ON jobs(status, id);
                CREATE INDEX IF NOT EXISTS idx_results_job_id ON results(job_id, id);
                CREATE INDEX IF NOT EXISTS idx_events_job_id ON events(job_id, id);
                CREATE INDEX IF NOT EXISTS idx_context_updated_id ON context(updated_at, id);
                CREATE INDEX IF NOT EXISTS idx_insights_status ON insights(status, id);
                CREATE INDEX IF NOT EXISTS idx_messages_channel_status ON messages(channel, status, id);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
            )
            connection.commit()
        try:
            self._migrate()
        except Exception:
            self.close()
            raise

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database,
            uri=self._uri,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if self._memory:
            connection.execute("PRAGMA read_uncommitted = ON")
        else:
            connection.execute("PRAGMA journal_mode = WAL")
        with self._connections_lock:
            if self._closed:
                connection.close()
                raise RuntimeError("store is closed")
            self._connections.add(connection)
        return connection

    def _connection(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("store is closed")
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._new_connection()
            self._local.connection = connection
        return connection

    def _migrate(self) -> None:
        version = self.schema_version()
        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema {version} is newer than supported "
                f"version {CURRENT_SCHEMA_VERSION}"
            )
        if version < 2:
            with self._tx() as connection:
                connection.execute(_OPERATIONS_SCHEMA)
                connection.execute(
                    "CREATE INDEX idx_operations_status_id "
                    "ON operations(status, id)"
                )
                connection.execute(
                    "CREATE INDEX idx_operations_org_status_id "
                    "ON operations(org, status, id)"
                )
                connection.execute(
                    "UPDATE meta SET value='2' WHERE key='schema_version'"
                )
            version = 2
        if version < 3:
            with self._tx() as connection:
                connection.execute(_APPROVALS_SCHEMA)
                connection.execute(
                    "CREATE INDEX idx_approvals_status_id ON approvals(status, id)"
                )
                connection.execute(
                    "CREATE INDEX idx_approvals_org_status_id "
                    "ON approvals(org, status, id)"
                )
                connection.execute(
                    "UPDATE meta SET value='3' WHERE key='schema_version'"
                )

    @property
    def _conn(self) -> sqlite3.Connection:
        """Return the calling thread's connection for compatibility."""
        return self._connection()

    def close(self) -> None:
        with self._connections_lock:
            if self._closed:
                return
            self._closed = True
            connections = list(self._connections)
            self._connections.clear()
        for connection in connections:
            connection.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._write_lock:
            connection = self._connection()
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    # -- jobs ----------------------------------------------------------------
    def enqueue(self, org: str, role: str, task: str, provider: str | None = None) -> int:
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO jobs (org, role, task, provider) VALUES (?,?,?,?)",
                (org, role, task, provider),
            )
            return int(cur.lastrowid)

    def create_running_job(
        self,
        org: str,
        role: str,
        task: str,
        provider: str | None = None,
    ) -> int:
        """Create a running job already owned by the synchronous caller."""
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO jobs (org, role, task, provider, status) "
                "VALUES (?,?,?,?, 'running')",
                (org, role, task, provider),
            )
            return int(cur.lastrowid)

    def pull_next(self) -> sqlite3.Row | None:
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

    def get(self, job_id: int) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def get_last_error(self, job_id: int) -> str:
        row = self._conn.execute("SELECT error FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row["error"] if row and row["error"] else ""

    def schema_version(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            return 0
        return int(row["value"])

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
        if status:
            return self._conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    # -- operations ----------------------------------------------------------
    def create_operation(self, org: str, kind: str, params: Mapping[str, object]) -> int:
        normalized = normalize_operation_params(kind, params)
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._tx() as connection:
            cursor = connection.execute(
                "INSERT INTO operations (org, kind, params) VALUES (?,?,?)",
                (org, kind, encoded),
            )
            return int(cursor.lastrowid)

    def get_operation(self, operation_id: int) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM operations WHERE id=?", (operation_id,)
        ).fetchone()

    def list_operations(
        self,
        org: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[sqlite3.Row]:
        if status is not None and status not in VALID_OPERATION_STATUSES:
            raise ValueError(f"invalid operation status: {status!r}")
        if limit < 1:
            raise ValueError("limit must be positive")
        query = "SELECT * FROM operations WHERE 1=1"
        values: list[object] = []
        if org is not None:
            query += " AND org=?"
            values.append(org)
        if status is not None:
            query += " AND status=?"
            values.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        values.append(limit)
        return self._conn.execute(query, values).fetchall()

    def transition_operation(
        self,
        operation_id: int,
        from_status: str,
        to_status: str,
        *,
        result: str | None = None,
        error: str | None = None,
        job_id: int | None = None,
    ) -> sqlite3.Row | None:
        if to_status not in OPERATION_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"invalid operation transition: {from_status} -> {to_status}")
        with self._tx() as connection:
            return connection.execute(
                """
                UPDATE operations
                SET status=?, result=?, error=?, job_id=?, updated_at=datetime('now')
                WHERE id=? AND status=?
                RETURNING *
                """,
                (to_status, result, error, job_id, operation_id, from_status),
            ).fetchone()

    def request_operation_cancel(self, operation_id: int) -> sqlite3.Row | None:
        with self._tx() as connection:
            row = connection.execute(
                "SELECT status FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
            if row is None:
                return None
            if row["status"] == "queued":
                return connection.execute(
                    """
                    UPDATE operations
                    SET status='cancelled', cancel_requested=1,
                        updated_at=datetime('now')
                    WHERE id=? AND status='queued'
                    RETURNING *
                    """,
                    (operation_id,),
                ).fetchone()
            if row["status"] == "running":
                return connection.execute(
                    """
                    UPDATE operations
                    SET cancel_requested=1, updated_at=datetime('now')
                    WHERE id=? AND status='running'
                    RETURNING *
                    """,
                    (operation_id,),
                ).fetchone()
            return None

    def operation_cancel_requested(self, operation_id: int) -> bool:
        row = self._conn.execute(
            "SELECT cancel_requested FROM operations WHERE id=?", (operation_id,)
        ).fetchone()
        return bool(row and row["cancel_requested"])

    def claim_next_operation(self) -> sqlite3.Row | None:
        with self._tx() as connection:
            return connection.execute(
                """
                UPDATE operations
                SET status='running', updated_at=datetime('now')
                WHERE id = (
                    SELECT id FROM operations
                    WHERE status='queued' AND cancel_requested=0
                    ORDER BY id LIMIT 1
                ) AND status='queued' AND cancel_requested=0
                RETURNING *
                """
            ).fetchone()

    # -- approvals -----------------------------------------------------------
    def create_approval(
        self,
        org: str,
        role: str,
        tool: str,
        action_args: Mapping[str, object],
        *,
        risk: str,
        job_id: int | None = None,
        operation_id: int | None = None,
    ) -> int:
        if risk not in VALID_APPROVAL_RISKS:
            raise ValueError(f"invalid approval risk: {risk!r}")
        encoded = json.dumps(
            dict(action_args),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._tx() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approvals
                    (org, role, tool, action_args, risk, job_id, operation_id)
                VALUES (?,?,?,?,?,?,?)
                """,
                (org, role, tool, encoded, risk, job_id, operation_id),
            )
            return int(cursor.lastrowid)

    def get_approval(self, approval_id: int) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM approvals WHERE id=?", (approval_id,)
        ).fetchone()

    def list_approvals(
        self,
        *,
        org: str | None = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[sqlite3.Row]:
        if status not in VALID_APPROVAL_STATUSES:
            raise ValueError(f"invalid approval status: {status!r}")
        if limit < 1:
            raise ValueError("limit must be positive")
        query = "SELECT * FROM approvals WHERE status=?"
        values: list[object] = [status]
        if org is not None:
            query += " AND org=?"
            values.append(org)
        query += " ORDER BY id ASC LIMIT ?"
        values.append(limit)
        return self._conn.execute(query, values).fetchall()

    def resolve_approval(
        self,
        approval_id: int,
        decision: str,
        *,
        decided_by: str = "",
    ) -> sqlite3.Row | None:
        if decision not in {"approved", "denied"}:
            raise ValueError("approval decision must be 'approved' or 'denied'")
        with self._tx() as connection:
            return connection.execute(
                """
                UPDATE approvals
                SET status=?, decided_by=?, decided_at=datetime('now')
                WHERE id=? AND status='pending'
                RETURNING *
                """,
                (decision, decided_by, approval_id),
            ).fetchone()

    def _finish_pending_approval(self, approval_id: int, status: str) -> bool:
        with self._tx() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET status=?, decided_at=datetime('now')
                WHERE id=? AND status='pending'
                """,
                (status, approval_id),
            )
            return cursor.rowcount == 1

    def expire_approval(self, approval_id: int) -> bool:
        return self._finish_pending_approval(approval_id, "expired")

    def cancel_approval(self, approval_id: int) -> bool:
        return self._finish_pending_approval(approval_id, "cancelled")

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

    def get_context(self, key: str) -> sqlite3.Row | None:
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
        status: str | None = None,
        level: str | None = None,
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
        requested_role: str | None = None,
        reply_to: int | None = None,
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

    def claim_next_in_channel(self, channel: str) -> sqlite3.Row | None:
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
        self, channel: str | None = None, limit: int = 100
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
        self, channel: str | None = None, limit: int = 100
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

