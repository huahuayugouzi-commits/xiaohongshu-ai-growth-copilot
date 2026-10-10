"""Explicit initialization, per-operation connections and transactional migrations."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .migrations import MIGRATIONS

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_path() -> Path:
    configured = os.environ.get("GROWTH_DB_PATH")
    return Path(configured).expanduser().resolve() if configured else PROJECT_ROOT / "data" / "growth.sqlite3"


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).resolve() if path is not None else default_path()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # No executescript here: it implicitly commits a pending transaction.
        with self.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            applied = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            known = [v for v, _ in MIGRATIONS]
            if applied != known[:len(applied)]:
                raise RuntimeError("Unsupported Growth database migration history")
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                statement = ""
                for line in script.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        conn.execute(statement)
                        statement = ""
                if statement.strip():
                    raise RuntimeError("Incomplete migration SQL")
                conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
