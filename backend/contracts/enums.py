"""Shared vocabularies — single definitions derived from Docs/api/schemas (Rules.md).

Enum members mirror the contract exactly; never compare raw strings at use sites.
"""
from __future__ import annotations

from enum import StrEnum


class Kind(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    UNKNOWN = "unknown"


class JobState(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    SORTING = "sorting"
    READY = "ready"


class JobStage(StrEnum):
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    SORTING = "sorting"


class MatchReason(StrEnum):
    TITLE = "title"
    TRANSCRIPT = "transcript"
    BODY = "body"
    TAG = "tag"
    FOLDER = "folder"
    SEMANTIC = "semantic"


class Engine(StrEnum):
    CLOUD = "cloud"
    LOCAL = "local"


class ErrorCode(StrEnum):
    ALREADY_SAVED = "already_saved"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    CONTRACT_VERSION_MISMATCH = "contract_version_mismatch"
    FOLDER_DEPTH_EXCEEDED = "folder_depth_exceeded"
    RESERVED_FOLDER_NAME = "reserved_folder_name"
    EXTRACTION_FAILED = "extraction_failed"
    TRANSCRIPTION_FAILED = "transcription_failed"
    ASR_UNAVAILABLE = "asr_unavailable"
    LLM_UNAVAILABLE = "llm_unavailable"
    INDEX_MISMATCH = "index_mismatch"
    UNAUTHORIZED = "unauthorized"


class SyncOp(StrEnum):
    SAVE_CREATE = "save_create"
    SAVE_PATCH = "save_patch"
    NOTE_PUT = "note_put"
    FOLDER_CREATE = "folder_create"
    FOLDER_PATCH = "folder_patch"
    TAGS_PUT = "tags_put"
    SUGGESTION_ACCEPT = "suggestion_accept"


RESERVED_FOLDER_NAMES = frozenset({"other", "misc", "unsorted", "inbox"})
CONTRACT_VERSION = 0
