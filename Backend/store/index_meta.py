"""Embedding index metadata and compatibility checks."""

import sqlite3

from Backend.errors import DomainError
from Backend.store.database import Database


EXPECTED_MODEL_ID = "intfloat/multilingual-e5-small"
EXPECTED_DIM = 384
EXPECTED_VERSION = 1


class IndexMeta:
    """Pin and validate the active embedding model."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure(self) -> dict:
        """Create the pinned index metadata when missing."""
        assert self.database.connection is not None
        connection = self.database.connection
        row = connection.execute("SELECT * FROM index_meta WHERE id = 1").fetchone()
        if row is None:
            try:
                connection.execute(
                    "INSERT INTO index_meta (id, model_id, dim, version, created_at) VALUES (1, ?, ?, ?, ?)",
                    (EXPECTED_MODEL_ID, EXPECTED_DIM, EXPECTED_VERSION, "1970-01-01T00:00:00Z"),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                connection.rollback()
            row = connection.execute("SELECT * FROM index_meta WHERE id = 1").fetchone()
        assert row is not None
        return {
            "model_id": row["model_id"],
            "dim": row["dim"],
            "version": row["version"],
        }

    def check_compatible(self) -> None:
        """Refuse search when the stored embedding model mismatches."""
        meta = self.ensure()
        if (
            meta["model_id"] != EXPECTED_MODEL_ID
            or meta["dim"] != EXPECTED_DIM
            or meta["version"] != EXPECTED_VERSION
        ):
            raise DomainError("index_mismatch", "Search index does not match the pinned embedding model")
