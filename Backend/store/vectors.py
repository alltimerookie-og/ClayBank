"""Deterministic local embedding and vector compatibility layer."""

import hashlib

from Backend.store.database import Database
from Backend.store.index_meta import IndexMeta


class VectorSearch:
    """Provide a dependency-free semantic-style retrieval signal."""

    DIM = 384

    def __init__(self, database: Database) -> None:
        self.database = database
        self.index_meta = IndexMeta(database)

    def search(self, query: str, folder_scope: str | None = None) -> list[dict]:
        """Rank saves by hashed-token overlap as a vector-search stand-in."""
        self.index_meta.check_compatible()
        tokens = self._tokens(query)
        if not tokens:
            return []
        assert self.database.connection is not None
        connection = self.database.connection
        rows = connection.execute(
            """
            SELECT s.id AS save_id, s.folder_id AS folder_id,
                   COALESCE(n.overview, '') || ' ' || COALESCE(n.key_points_json, '') || ' '
                   || COALESCE(n.transcript, '') AS passage
            FROM saves s
            LEFT JOIN notes n ON n.save_id = s.id
            """
        ).fetchall()
        results: list[dict] = []
        for row in rows:
            if folder_scope is not None and row["folder_id"] != folder_scope:
                continue
            passage_tokens = self._tokens(row["passage"] or "")
            overlap = len(tokens & passage_tokens)
            if overlap:
                results.append(
                    {
                        "save_id": row["save_id"],
                        "match_reason": "semantic",
                        "fragment": None,
                        "jump_target": None,
                        "score": float(overlap),
                    }
                )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:50]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        """Tokenize text with hashed normalization."""
        words = [word.strip(".,;:!?()[]{}\"'").lower() for word in text.split()]
        hashed: set[str] = set()
        for word in words:
            if len(word) < 3:
                continue
            digest = hashlib.sha256(f"query:{word}".encode()).hexdigest()
            hashed.add(digest[:16])
        return hashed
