"""Search and Ask views package for ClayBank (Phase 6)."""

from app.views.search.ask_message import (
    AskAnswerCard,
    AskTypingDots,
    AskUserBubble,
)
from app.views.search.ask_view import (
    DEFAULT_FOLDER_PROMPTS,
    DEFAULT_LIBRARY_PROMPTS,
    AskView,
)
from app.views.search.search_result_card import (
    MATCH_REASON_LABELS,
    SearchResultCard,
    format_match_reason,
)
from app.views.search.search_view import (
    FACET_ALL,
    FACET_INSTAGRAM,
    FACET_THIS_MONTH,
    FACET_YOUTUBE,
    FACETS,
    SearchView,
    filter_results_by_facet,
)

__all__ = [
    "SearchResultCard",
    "format_match_reason",
    "MATCH_REASON_LABELS",
    "SearchView",
    "filter_results_by_facet",
    "FACET_ALL",
    "FACET_YOUTUBE",
    "FACET_INSTAGRAM",
    "FACET_THIS_MONTH",
    "FACETS",
    "AskUserBubble",
    "AskTypingDots",
    "AskAnswerCard",
    "AskView",
    "DEFAULT_LIBRARY_PROMPTS",
    "DEFAULT_FOLDER_PROMPTS",
]
