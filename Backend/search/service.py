"""Hybrid search and cited Ask service."""

from Backend.capture.service import CaptureService
from Backend.config import Settings, load_settings
from Backend.contracts.search import AskRequest, SearchQuery
from Backend.errors import DomainError
from Backend.llm.provider import provider_from_settings
from Backend.store.database import Database
from Backend.store.fts5 import FtsSearch
from Backend.store.index_meta import IndexMeta
from Backend.store.vectors import VectorSearch


class SearchService:
    """Serve keyword plus semantic retrieval and Ask answers."""

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        self.database = database
        self.settings = settings or load_settings()
        self.capture = CaptureService(database)
        self.fts = FtsSearch(database)
        self.vectors = VectorSearch(database)
        self.index_meta = IndexMeta(database)
        self.chat = provider_from_settings(self.settings)

    def search(self, query: SearchQuery) -> dict:
        """Return fused FTS5 and semantic results for one query."""
        if not query.q.strip():
            raise DomainError("validation", "Search query is required")
        self.index_meta.check_compatible()
        folder_scope = str(query.folder_scope) if query.folder_scope else None
        keyword = self.fts.search(query.q, folder_scope)
        semantic = self.vectors.search(query.q, folder_scope)
        fused = self._reciprocal_rank_fusion(keyword, semantic)
        items = []
        for entry in fused[:50]:
            bundle = self.capture.get_save_bundle(entry["save_id"])
            items.append(
                {
                    "save": bundle["save"],
                    "match_reason": entry["match_reason"],
                    "fragment": entry["fragment"],
                    "jump_target": entry["jump_target"],
                    "score": entry["score"],
                }
            )
        return {"results": items, "cursor": None}

    def ask(self, payload: AskRequest) -> dict:
        """Answer from retrieved saves with mandatory citations."""
        if not payload.question.strip():
            raise DomainError("validation", "Ask question is required")
        if payload.engine not in {"cloud", "local"}:
            raise DomainError("validation", "Ask engine must be cloud or local")
        scope = payload.save_scope or "library"
        folder_scope = None if scope == "library" else scope
        self.index_meta.check_compatible()
        keyword = self.fts.search(payload.question, folder_scope)
        semantic = self.vectors.search(payload.question, folder_scope)
        fused = self._reciprocal_rank_fusion(keyword, semantic)
        if not fused:
            raise DomainError("not_found", "No saves matched this question")
        bundles = []
        for entry in fused[:3]:
            bundles.append((entry, self.capture.get_save_bundle(entry["save_id"])))
        citations = []
        titles = []
        for entry, bundle in bundles:
            titles.append(bundle["save"].get("title") or bundle["save"]["id"])
            citations.append(
                {
                    "save_id": entry["save_id"],
                    "anchor": entry["jump_target"],
                    "quote": entry["fragment"],
                }
            )
        answer = self._cloud_answer(payload, bundles) or self._local_answer(citations, titles)
        return {
            "answer": answer,
            "scope": scope,
            "engine": payload.engine,
            "citations": citations,
        }

    def _cloud_answer(self, payload: AskRequest, bundles: list) -> str | None:
        """Generate a cloud answer when requested and configured."""
        if payload.engine != "cloud" or self.chat is None:
            return None
        context = "\n\n".join(
            f"Save {bundle['save']['id']}: {bundle['save'].get('title') or ''}\n"
            f"{(bundle['note'] or {}).get('markdown', '')[:4000]}"
            for _, bundle in bundles
        )
        return self.chat.answer(payload.question, context)

    @staticmethod
    def _local_answer(citations: list[dict], titles: list[str | None]) -> str:
        """Generate a deterministic local fallback answer."""
        named = [title for title in titles if title]
        return f"Based on {len(citations)} save(s): " + "; ".join(named)

    @staticmethod
    def _reciprocal_rank_fusion(keyword: list[dict], semantic: list[dict]) -> list[dict]:
        """Fuse two ranked lists with reciprocal rank fusion."""
        scores: dict[str, float] = {}
        best: dict[str, dict] = {}
        for rank, entry in enumerate(keyword, start=1):
            scores[entry["save_id"]] = scores.get(entry["save_id"], 0.0) + 1.0 / (60 + rank)
            best.setdefault(entry["save_id"], entry)
        for rank, entry in enumerate(semantic, start=1):
            scores[entry["save_id"]] = scores.get(entry["save_id"], 0.0) + 1.0 / (60 + rank)
            current = best.get(entry["save_id"])
            if current is None or current["match_reason"] == "semantic":
                best[entry["save_id"]] = entry
        fused = []
        for save_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            entry = dict(best[save_id])
            entry["score"] = round(score, 6)
            fused.append(entry)
        return fused
