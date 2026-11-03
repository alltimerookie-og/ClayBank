"""SQLite-backed full-text retrieval."""

import sqlite3

from Backend.errors import DomainError
from Backend.store.database import Database
from Backend.store.index_meta import IndexMeta


class FtsSearch:
    """Query the trigger-maintained FTS5 note index."""

    COLUMNS = ("title", "transcript", "body", "tag", "folder", "semantic")

    def __init__(self, database: Database) -> None:
        self.database = database
        self.index_meta = IndexMeta(database)

    def search(self, query: str, folder_scope: str | None = None) -> list[dict]:
        """Return BM25-ranked matches with match reason metadata."""
        if not query.strip():
            raise DomainError("validation", "Search query is required")
        self.index_meta.check_compatible()
        assert self.database.connection is not None
        connection = self.database.connection
        try:
            rows = connection.execute(
                """
                SELECT save_id, title, overview, key_points, body, transcript, tags, folder, bm25(notes_fts) AS rank
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT 50
                """,
                (query,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise DomainError("validation", "Invalid search query") from exc
        results: list[dict] = []
        lowered = query.lower()
        for row in rows:
            save_id = row["save_id"]
            save = connection.execute("SELECT * FROM saves WHERE id = ?", (save_id,)).fetchone()
            if save is None:
                continue
            if folder_scope is not None and save["folder_id"] != folder_scope:
                continue
            reason, fragment = self._match_reason(row, lowered)
            score = max(0.0, 10.0 - float(row["rank"]))
            results.append(
                {
                    "save_id": save_id,
                    "match_reason": reason,
                    "fragment": fragment,
                    "jump_target": self._jump_target(row, reason),
                    "score": score,
                }
            )
        return results

    def _match_reason(self, row, lowered: str) -> tuple[str, str | None]:
        """Select the first matching indexed column deterministically."""
        title = row["title"] or ""
        transcript = row["transcript"] or ""
        body = f"{row['overview'] or ''}\n{row['key_points'] or ''}\n{row['body'] or ''}"
        tags = row["tags"] or ""
        folder = row["folder"] or ""
        if lowered in title.lower():
            return "title", self._snippet(title, lowered)
        if lowered in transcript.lower():
            return "transcript", self._snippet(transcript, lowered)
        if lowered in body.lower():
            return "body", self._snippet(body, lowered)
        if lowered in tags.lower():
            return "tag", self._snippet(tags, lowered)
        if lowered in folder.lower():
            return "folder", self._snippet(folder, lowered)
        return "semantic", None

    @staticmethod
    def _snippet(value: str, lowered: str) -> str | None:
        """Return surrounding text for a matched value."""
        index = value.lower().find(lowered)
        if index == -1:
            return None
        start = max(0, index - 20)
        return value[start : index + len(lowered) + 20].strip()

    @staticmethod
    def _jump_target(row, reason: str) -> str | None:
        """Return a timestamp or heading anchor when available."""
        if reason != "transcript" or not row["transcript"]:
            return None
        for line in str(row["transcript"]).splitlines():
            if "—" in line:
                return line.split("—", 1)[0].strip()
        return None
