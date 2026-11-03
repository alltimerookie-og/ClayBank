"""Deterministic local embedding and vector compatibility layer."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import numpy as np

from Backend.store.database import Database
from Backend.store.embeddings import MODEL_ID, is_downloaded, model_directory
from Backend.store.index_meta import IndexMeta


log = logging.getLogger(__name__)


class EmbeddingBackend:
    """ONNX Runtime embeddings for the pinned multilingual model."""

    DIM = 384

    def __init__(self, root: Path | None = None) -> None:
        self.model_dir = model_directory(root)
        self.session = None
        self.tokenizer = None

    def ensure_loaded(self) -> None:
        """Load ONNX and tokenizer artifacts on first use."""
        if self.session is not None and self.tokenizer is not None:
            return
        if not is_downloaded():
            raise RuntimeError("Embedding model is not downloaded")
        log.info("vectors: loading ONNX model from %s", self.model_dir)
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.session = ort.InferenceSession(str(self.model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))

    def embed(self, texts: list[str], *, prefix: str) -> np.ndarray:
        """Embed texts with the required e5 prefix."""
        self.ensure_loaded()
        assert self.session is not None
        assert self.tokenizer is not None
        prefixed = [f"{prefix} {text}".strip() for text in texts]
        encoded = self.tokenizer.encode_batch(prefixed)
        input_ids = np.array([item.ids for item in encoded], dtype=np.int64)
        attention_mask = np.array([item.attention_mask for item in encoded], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)
        outputs = self.session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        vectors = np.asarray(outputs[0], dtype=np.float32)
        mask = attention_mask[:, :, None].astype(np.float32)
        summed = (vectors * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1.0, None)
        averaged = summed / counts
        norms = np.linalg.norm(averaged, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (averaged / norms).astype(np.float32)


class VectorIndex:
    """faiss flat index backed by SQLite recovery storage."""

    DIM = 384

    def __init__(self, database: Database, root: Path | None = None) -> None:
        self.database = database
        if root is None:
            db_path = getattr(database, "path", None)
            root = Path(db_path).parent if db_path else Path(__file__).resolve().parents[1]
        self.root = root
        self.index_path = self.root / "data" / "faiss.index"
        self.embeddings = EmbeddingBackend()
        self.index = None

    def ensure(self):
        """Load or rebuild the faiss flat index."""
        import faiss

        if self.index is not None:
            return self.index
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists() and self._read_ids():
            self.index = faiss.read_index(str(self.index_path))
            return self.index
        self.index = faiss.IndexFlatIP(self.DIM)
        self.rebuild()
        return self.index

    def rebuild(self) -> int:
        """Rebuild faiss from SQLite recovery vectors."""
        assert self.database.connection is not None
        import faiss

        rows = self.database.connection.execute("SELECT save_id, vector, dim FROM save_vectors").fetchall()
        vectors: list[np.ndarray] = []
        ids: list[str] = []
        for row in rows:
            if row["dim"] != self.DIM:
                continue
            vector = np.frombuffer(row["vector"], dtype=np.float32)
            if vector.shape[0] != self.DIM:
                continue
            vectors.append(vector)
            ids.append(row["save_id"])
        self.index = faiss.IndexFlatIP(self.DIM)
        if vectors:
            matrix = np.stack(vectors).astype(np.float32)
            self.index.add(matrix)
            self._write_ids(ids)
            faiss.write_index(self.index, str(self.index_path))
        return len(ids)

    def index_note(self, save_id: str, text: str) -> None:
        """Embed one note and persist both recovery and faiss representations."""
        assert self.database.connection is not None
        vector = self.embeddings.embed([text], prefix="passage:")[0]
        blob = sqlite3.Binary(vector.tobytes())
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO save_vectors (save_id, vector, dim)
                VALUES (?, ?, ?)
                ON CONFLICT(save_id) DO UPDATE SET vector=excluded.vector, dim=excluded.dim
                """,
                (save_id, blob, self.DIM),
            )
        self.rebuild()

    def query(self, text: str, limit: int = 50) -> list[tuple[str, float]]:
        """Return save IDs ordered by cosine similarity."""
        self.ensure()
        assert self.index is not None
        vector = self.embeddings.embed([text], prefix="query:")
        scores, positions = self.index.search(vector.astype(np.float32), limit)
        ids = self._read_ids()
        results: list[tuple[str, float]] = []
        for score, position in zip(scores[0].tolist(), positions[0].tolist()):
            if position < 0 or position >= len(ids):
                continue
            results.append((ids[position], float(score)))
        return results

    def _write_ids(self, ids: list[str]) -> None:
        """Persist faiss row ordering beside the index file."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.with_suffix(".ids").write_text("\n".join(ids), encoding="utf-8")

    def _read_ids(self) -> list[str]:
        """Read faiss row ordering."""
        path = self.index_path.with_suffix(".ids")
        if not path.exists():
            return []
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class VectorSearch:
    """faiss-backed semantic retrieval."""

    DIM = 384

    def __init__(self, database: Database, root: Path | None = None) -> None:
        self.database = database
        self.index_meta = IndexMeta(database)
        self.index = VectorIndex(database, root)

    def search(self, query: str, folder_scope: str | None = None) -> list[dict]:
        """Rank saves with real cosine similarity."""
        self.index_meta.check_compatible()
        if not query.strip():
            return []
        assert self.database.connection is not None
        matches = {save_id: score for save_id, score in self.index.query(query)}
        if not matches:
            return []
        connection = self.database.connection
        rows = connection.execute(
            f"SELECT id, folder_id FROM saves WHERE id IN ({','.join('?' for _ in matches)})",
            list(matches),
        ).fetchall()
        results: list[dict] = []
        for row in rows:
            if folder_scope is not None and row["folder_id"] != folder_scope:
                continue
            results.append(
                {
                    "save_id": row["id"],
                    "match_reason": "semantic",
                    "fragment": None,
                    "jump_target": None,
                    "score": matches[row["id"]],
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:50]

    @staticmethod
    def model_id() -> str:
        """Return the pinned model identifier."""
        return MODEL_ID
