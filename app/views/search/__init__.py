"""Search and Ask views package for ClayBank (Phase 6)."""

from app.views.search.search_result_card import (
    MATCH_REASON_LABELS,
    SearchResultCard,
    format_match_reason,
)

__all__ = [
    "SearchResultCard",
    "format_match_reason",
    "MATCH_REASON_LABELS",
]
