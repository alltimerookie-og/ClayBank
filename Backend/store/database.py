"""SQLite database lifecycle and transaction boundary."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILES = (
    ROOT / "Docs" / "db" / "0001_core.sql",
    ROOT / "Docs" / "db" / "0002_server.sql",
)
REQUIRED_TABLES = frozenset({"saves", "users", "idempotency_keys", "changes"})


class Database:
    """Manage one SQLite connection for the FastAPI application."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else ROOT / "data" / "claybank.sqlite3"
        self.connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create the database and apply the shared/server schemas."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        existing_tables = {
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if existing_tables and not REQUIRED_TABLES.issubset(existing_tables):
            self.close()
            raise RuntimeError(
                f"Database at {self.path} has an incomplete Claybank schema"
            )
        if not REQUIRED_TABLES.issubset(existing_tables):
            for schema_file in SCHEMA_FILES:
                self.connection.executescript(schema_file.read_text(encoding="utf-8"))
        self.connection.execute(
            """
            INSERT OR IGNORE INTO users (id, name, created_at)
            VALUES ('dev-user', 'Development User', '1970-01-01T00:00:00Z')
            """
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO index_meta (id, model_id, dim, version, created_at)
            VALUES (1, 'intfloat/multilingual-e5-small', 384, 1, ?)
            """,
            (datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),),
        )
        self.connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit a successful transaction and roll back failures."""
        if self.connection is None:
            raise RuntimeError("Database is not initialized")
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None
