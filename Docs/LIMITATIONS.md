# Claybank - Limitations and Technical Claims

Disclosure date: 2026-11-03. See `Docs/TEST_REPORT.md` for the exact commit.
This is a frontend-first submission. Limitations below are required reading.

## Mandatory Phase 8 disclosure

- Quick-save notification is a **desktop preview, not native notification delivery** (`app/views/capture/`).
- Native Android notification spike is **INCONCLUSIVE** - no device delivery proof, no `flet-android-notifications` dep, no manifest patch (`Docs/Phases.md:88-96`).
- Guaranteed capture path is the **in-app paste sheet** (`app/views/paste_sheet.py`).
- `POST_NOTIFICATIONS`, OS share-target, background sync, GGUF inference are **device/backend-dependent and unverified on device**.

## Classification key

- Implemented + tested - renders and passes tests.
- Fixture/mock-verified - runs against `Docs/api/fixtures/*.json` or in-memory coordinators; no live backend.
- Desktop-preview - visible in `flet run` on laptop; not proven on Android hardware.
- Backend/device-dependent - needs FastAPI workers or Android OS.
- Planned - post-hackathon (`Docs/Phases.md`).

## Claims matrix

| Feature | Status | Evidence | Limitation |
|---|---|---|---|
| Capture paste sheet, validation, `already_saved` | Implemented + tested | `paste_sheet.py`, phase 2 + 8 tests |  |
| Inbox stages, review queue + Undo | Implemented + tested | `inbox_view`, `processing_card`, `quick_check_card` | Stages simulated; real job worker is backend |
| Cloud note generation | Fixture/mock, Backend-dependent | `note/*`, `app.py:_resolve_default_markdown` | No live LLM call |
| Hybrid search (match reason/jump target) | Fixture/mock, Backend-dependent | `search_view`, `search_result_card` | No live FTS5/faiss ranking |
| Ask with citations | Fixture/mock, Backend-dependent | `ask_view`, `ask_message` | Synthetic citation fallback if no callback |
| Folders/tags (depth <=3, one-per-save, flat tags) | Implemented + tested + schema-verified | `folder_dialogs:MAX_FOLDER_DEPTH`, `0001_core.sql`, `test_schema.py` |  |
| Sync 409 keep-both | Fixture/mock, Backend-dependent | `sync_coordinator`, `conflict_banner` | `agent_trace` stripped; cursor server not live |
| Offline queue | Desktop-preview, Backend-dependent | `SyncCoordinator` + Idempotency-Key contract | No Android offline proof |
| Settings + persistence | Implemented + tested | `settings_view`, `chat_model_card`, `storage_card` | `0003_device.sql` is definition, not a live DB log |
| Local model selection / GGUF inference | Desktop-preview / Planned | `chat_model_card`, `Architecture.md:43`, ADR 0008 | Budgets 6-10 tok/s are not measurements |
| Notification / share target / clipboard | Desktop-preview, INCONCLUSIVE | `notification_coordinator`, `paste_sheet` foreground-timed reads | Background reads impossible on Android 10+ |
| Security/privacy boundaries | Documented, unverified at runtime | `Rules.md`, ADR 0004 | `text only / transcript-only cloud` is a boundary, not an audit verdict |
| Performance budgets (30 s / 2 min) | Budgets, not measurements | `Docs/PRD.md:97-99` | Do not present as measured latency |

See `Docs/SUBMISSION.md` for the package checklist and `Docs/TEST_REPORT.md` for test evidence.
