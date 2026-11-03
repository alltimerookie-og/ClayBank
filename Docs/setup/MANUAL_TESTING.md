# Claybank — Manual Testing Guide

This guide is for the main developer manually inspecting the frontend on `aqib`. All steps run against the Flet Python UI with fixture-backed callbacks when no backend is attached. No server or device runtime is required.

See also: `Docs/SETUP.md` for install/run, `Docs/LIMITATIONS.md` for claims matrix, `Docs/TEST_REPORT.md` for automated evidence.

## A. Getting started

1. **Clone `aqib`:** `git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git && cd ClayBank`
2. **Create / Activate venv:** `python -m venv .venv && .\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (macOS/Linux). (Reuse existing `.venv` if already created).
3. **Install:** `python -m pip install --upgrade pip && python -m pip install -e . && python -m pip install "jsonschema>=4.21" referencing pytest`
4. **Start desktop preview:** `flet run main.py` — desktop window or browser tab opens. Close it or `Ctrl+C` to stop.
5. **Start Android live preview:** `flet run --android main.py` — starts development server and outputs a terminal QR code for the mobile Flet app.
6. **Navigate four tabs:** Bottom `SharedNavigationBar` (`app/shell/nav.py: TAB_COUNT = 4`): **Inbox (0) → Folders (1) → Search (2) → Settings (3)**. **Ask is not a tab** — opened from Search ("Ask your library") or a folder `...` menu (`app/app.py:on_ask_query`).

## B. Android live testing with Flet

You can run and test ClayBank live on your physical Android smartphone using the official Flet app:

1. **Prerequisites:**
   - Android smartphone with the official **Flet** app installed from Google Play Store.
   - Development PC and Android phone connected to the exact same local Wi-Fi network.
2. **Launch live server:**
   On your PC terminal, execute:

   ```powershell
   flet run --android main.py
   ```

   *(Note: On Windows PowerShell, if ASCII QR rendering fails with a charmap encoding error, run `$env:PYTHONIOENCODING="utf-8"` before launching).*
3. **QR Code Scanning:**
   - Look at the terminal output on your development PC: Flet renders an ASCII QR code and displays a local network URL (e.g., `http://192.168.1.X:8550`).
   - Open the **Flet** app on your Android device.
   - Tap the camera/scanner icon and point the camera at your PC screen to scan the QR code (or manually input the URL if preferred).
4. **Live interaction verification:**
   - Verify that ClayBank boots immediately and transitions to the application shell (`AppShellLayout`).
   - Test bottom navigation switching between the four tabs: Inbox, Folders, Search, and Settings.
   - Tap the `+` action button in the Inbox header to verify that the `AddLinkPasteSheet` modal bottom sheet slides up smoothly.
   - Verify mobile touch responsiveness, scrolling performance, and button tap feedback.
5. **What to test on mobile hardware:**
   - **Touch targets & sheets:** Check tap target sizes, sheet dismiss gestures, and modal scrolling behavior.
   - **Navigation bar scaling:** Verify that `SharedNavigationBar` icons and labels fit mobile viewports across portrait orientations.
   - **Settings toggles:** Toggle switches (auto-sort, Wi-Fi processing) and select chat models (Cloud / Local dropdown).
   - **Manual paste & note reading:** Paste a sample link or view fixture-backed notes and verify typography scaling and readability.
6. **Limitations on Flet Android runner:**
   - The Flet app runner executes frontend Python UI within its cross-platform client runtime container.
   - It does **not** test standalone compiled APK installation.
   - Native device capabilities such as OS-level background service execution, `POST_NOTIFICATIONS` permission dialogs, system tray notification delivery, background clipboard sniffing, and on-device GGUF inference runtimes require dedicated Android build pipelines and are unverified on device.

## C. Application navigation

| Tab | Class | Notes |
| --- | --- | --- |
| **Inbox** | `app/views/inbox_view.py` | Default after onboarding. Capture sheet, processing card, quick-check/suggestions, recent carousel, job stages. |
| **Folders** | `app/views/folders/folders_grid_view.py` + `folder_detail_view.py` | Grid → detail (breadcrumb, child chips, tags row, search filter). |
| **Search** | `app/views/search/search_view.py` | Query field, platform/time chips, result cards with match reason + fragment + jump target. |
| **Settings** | `app/views/settings/settings_view.py` | Profile + sync chip, chat model card, storage, toggles, privacy banner. |

Boot order in `app/app.py: ClayBankApp` is Splash → Onboarding (if `has_seen_onboarding==false`) → `AppShellLayout`. In `main.py`, `has_seen_onboarding=True` and `app.transition_to_shell()` bypass the splash/onboarding screen for direct developer inspection.

## D. Manual workflow checklist

### Inbox and capture

Lives in `app/views/paste_sheet.py: AddLinkPasteSheet` + `app/views/inbox_view.py` + `app/app.py: handle_save_capture`.

1. Open **Inbox**. Confirm header, processing pill, and Inbox content.
2. Tap **Add Link** (header add button or shell `on_add_link`). Verify `AddLinkPasteSheet` slides up with: title "Add Link", URL field, `Detected link in clipboard` banner (if clipboard holds a URL), quick-tag chips (`ai · reading · recipe · dev · video`), user-context field, Save/Cancel.
3. Enter a **valid URL** (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`). Check `source_app`: `notification`/`share_target` if routed, `inbox_paste` if clipboard banner visible, otherwise `manual` (`paste_sheet.py: resolved_source_app`).
4. Check **URL validation**: try `not-a-url` or empty → `url_field.error` shows `"URL is required"` or `"Please enter a valid HTTP or HTTPS URL"`; no submit.
5. Toggle quick-tag chips (tap → selected uses `accent_bg` + `accent` border; tap again → deselected).
6. Fill **user context** (optional) and tap **Save** → payload `{url, source_app, user_context, suggested_folder_id: None, force: false}`. On `already_saved` error, `feedback_text` shows `"Already saved in library"`. On success, `on_success` fires and Inbox shows the new save card.
7. Clipboard flow: with `clipboard_reader` wired, sheet auto-prefills when visible. Clear with X → `clear_url` resets `source_app` to `manual` and hides banner.
8. Notification/share intents: `app/app.py: handle_external_capture` forwards `ACTION_PASTE_AND_SAVE` / `ACTION_SHARE_TARGET` / `ACTION_OPEN_APP` via `NotificationCoordinator`. When routed, `open_paste_sheet(initial_url, source_app=...)` pre-fills the sheet — verify URL field and that submit uses that `source_app`.

**Expected:** No network is hit in the default manual run. Saves appear via the callback return or fixture path (see §F).

### Notes

`app/views/note/note_view.py` + `note_engine.py`, `note_editor.py`, `properties_grid.py`, `note_renderer.py`.

1. Open a saved note by tapping an Inbox or folder save card → `ClayBankApp.open_note_view(save_id)` loads data + resolves markdown via `_resolve_default_markdown` (fixture `note.fixtures.json` if present, else frontmatter fallback).
2. Inspect **generated-note presentation**: Overview + Key points + Links sections from fixture markdown. Edit mode shows the Markdown editor with toolbar (`editor_toolbar.py`).
3. **Edit**: toggle edit mode; change Markdown. **Auto-save** is local-first — `handle_save_note` writes to `self.notes[save_id]` immediately and only calls `on_save_note` if wired. Confirm "Saved on device" or equivalent; no server round-trip required.
4. **Properties grid** (`properties_grid.py`): folder chip → filing sheet, tag chips → tag sheet. Change folder → `handle_move_folder(save_id, folder_path)` updates `inbox_view._saves` locally. Confirm undo/snackbar if available.
5. **Undo / conflict**: delete → `handle_delete_note`; a `UndoSnackBar` (5000 ms) may appear. `handle_restore_note` replays capture under same Idempotency-Key (fixture-backed here). For conflict, see `app/views/sync/conflict_banner.py`.

### Folders and organization

`app/views/folders/` — `folders_grid_view.py`, `folder_detail_view.py`, `folder_dialogs.py`, `cluster_card.py`.

1. Open **Folders**. Verify grid of `FolderCard`s with collage gradients.
2. **Create folder:** tap add/create → `CreateFolderSheet`. Enter a name; depth is enforced (`MAX_FOLDER_DEPTH = 3`); reserved names `Other`/`Misc`/`Unsorted`/`Inbox` are rejected (mirrors `Docs/db/0001_core.sql`). On create, a folder card appears; without a backend, the change stays local.
3. **Rename:** open folder context menu (`FolderContextMenu`) → `RenameFolderSheet` → confirm → card name updates.
4. **Delete:** context menu → `DeleteFolderConfirmDialog` → confirm. Member saves return to **Inbox** (Inbox-as-state; `Inbox` is not a folder).
5. **Folder details:** tap a folder card → `FolderDetailView` with breadcrumb, child-folder chips (navigate) vs tag row (filter in place), and search filtering within the folder.
6. **Tags and filters:** tag row chips filter saves in place.
7. **Suggestions + review:** cluster proposals (`ClusterCard`) show a suggested folder path + confidence. Accept/dismiss via the card → filed save or dismissed suggestion. Review queue (`quick_check_card.py`) is a derived filter `needs_review=true`.

### Search

`app/views/search/search_view.py` + `search_result_card.py`.

1. Open **Search**. Confirm the query field and "Ask your library" entry.
2. Enter a **search query** (e.g. a phrase you know appears in a fixture note's transcript/title/body/tag). Results load via `on_search_query(query, scope)`.
3. Inspect each **search result card**: it must show **match reason** (`title | transcript | body | tag | folder | semantic`), **matched fragment**, **jump target** (`0:42` or heading anchor), and **score**.
4. Tap a **jump target** chip → `note_view` opens at the anchor, not at the top.
5. Negative/empty query → no results or helper empty state; no crash.

Without a live backend, `app/app.py:handle_search_query` returns fixture-derived results.

### Ask

`app/views/search/ask_view.py` + `ask_message.py`.

1. Open **Ask** contextually: from Search header ("Ask your library") or a folder `...` menu (pre-scoped). Verify **Ask is never a tab** — `nav.py` enforces 4 tabs only.
2. Submit a **question** (e.g. "What did I save about pasta?"). `AskView` sends `{question, save_scope, engine}` via `on_ask_query` (`ask-request.json`: `question` required, `engine` = `cloud|local`).
3. Inspect the **answer card**: text answer + `Based on N saves` + **citation chips** (each chip opens the cited note at its anchor). **Answers without citations are a contract bug** (`ask-answer.json: citations mandatory`).
4. Tap a **citation chip** → the cited note opens at the citation's offset.
5. **Fixture vs live:** without a backend, `app/app.py:handle_ask_query` synthesizes a scoped answer from fixture saves with `citations: [{save_id, offset}]`. Do not confuse this with live LLM execution.

### Settings

`app/views/settings/settings_view.py` + `chat_model_card.py`, `storage_card.py`, `profile_card.py`, `switch_card.py`, `privacy_banner.py`.

1. Open **Settings**. Inspect: **profile card** (avatar, name, "Last backup", Synced `ft.Chip`), **Chat model card** ("Cloud | Local"), **local model picker** row (`MiniCPM5-2B · Qwen3-1.7B` + download state), **split storage row** (Library · Local model), `ft.Switch` rows (auto-sort, weekly digest, Wi-Fi-only processing, quick-save notification), **privacy banner**.
2. This screen reads/writes the `settings` table (`chat_model in cloud|local`, `cluster_min_size >= 3` — `Docs/db/0003_device.sql`). No endpoint serves settings; changes take effect on next call (e.g. `POST /ask` carries `engine`).
3. Toggle `Chat model: Cloud | Local` and the model picker. Toggle the preference switches. Confirm UI reflects the new selection.
4. Trigger a **conflict** path (`app/views/sync/conflict_banner.py`): simulate a `409 conflict` (e.g. two rapid edits). Verify the stale-write banner appears with Keep Both / Overwrite / Discard and that Undo via `UndoSnackBar` is offered.
5. Check **sync state** (`SyncCoordinator`): `Synced` / `Offline` / `Syncing...` + `last_backup` timestamp. Pull/push cursors are local-only without a backend.

### Capture notification preview

`app/views/capture/notification_card.py` + `notification_coordinator.py` (spike-gated).

1. Locate the **notification preview** (In-app card or dev preview surface). Verify the **Preview** label is visible — not a real Android notification.
2. **Paste and save** → foregrounds the app into the pre-filled capture sheet (clipboard is read only after the sheet is visible — Android 10+ forbids background reads per `Docs/Architecture.md`). Verify the sheet's link field is pre-filled and keyboard-focusable; if empty, the TextField stays focused.
3. **Open app** → opens the app without a pre-fill.
4. Do not treat this as a real `flet-android-notifications` delivery. Native permission, foreground service, and intent routing are unverified on device (see `Docs/LIMITATIONS.md`).

## E. Offline and error-state testing

| State | How to trigger/inspect | Expected frontend behavior |
| --- | --- | --- |
| **Degraded save** (transcript unavailable) | Open a save whose fixture has `transcript == null` | Renders as a smaller note, not an error page |
| **Processing states** | Observe Inbox card while `job.state` cycles `queued → extracting → transcribing → analyzing → sorting → ready` | Progress indicator + stage label updates |
| **Capture validation error** | Submit empty/invalid URL in paste sheet | Inline error under the URL field |
| **Duplicate capture** | Submit the same URL twice (without `force`) | `"Already saved in library"` feedback |
| **`already_saved` 409** | Same as above | `409 already_saved` per `POST /saves` contract |
| **`409 conflict` (stale write)** | Rapid edit + second edit with stale `updated_at` | Stale-write banner: Keep Both / Overwrite / Discard |
| **Sync offline** | Simulate offline (no `on_sync_pull`/`on_sync_push`) | `SyncCoordinator` → `Offline` chip |
| **Empty Inbox** | Start with no saves/suggestions | Empty-state copy + Add Link CTA |
| **Missing/invalid data** | Supply a save missing `title`/`url` or with unknown `kind` | Degraded but rendered note |

All of the above are frontend-rendered states — no live server required.

## F. Test data and fixture behavior

| Topic | Location / Behavior |
| --- | --- |
| **Fixtures** | `Docs/api/fixtures/*.fixtures.json` — 23 generated files. Single authored source: `Docs/api/generate_fixtures.py`. Never hand-edit fixtures. |
| **Schemas** | `Docs/api/schemas/*.json` — 22 draft 2020-12 schemas; `openapi.yaml` `$ref`s them. |
| **Screens loading fixtures** | `_resolve_default_markdown` (`app/app.py:931-965`) loads `note.fixtures.json` for note markdown when `notes[save_id]` is absent. `handle_search_query` / `handle_ask_query` / sync handlers use fixture-derived responses when callbacks are not wired. |
| **No backend connected** | Saves, notes, search hits, Ask answers, sync cursors are **locally simulated** via fixtures and in-memory coordinators. |
| **Locally simulated interactions** | All `handle_*` methods in `app/app.py` mutate local state and return `{status, ...}` when no callback is provided. |
| **Requires API responses** | Persistence beyond the process, canonicalization, real duplicate check, real hybrid results, real LLM answer generation, real cursor pull/push — all need the FastAPI backend from `Docs/api/openapi.yaml`. |
| **Seed accounts** | None. Hackathon shape uses `DEV_TOKEN` + `X-Device-Id` middleware (`Docs/adr/0006`). Placeholders are in `.env.example`. |

## G. Backend integration boundary

Inspect `Docs/api/openapi.yaml` (13 paths) and `app/app.py` callback seams (`on_*`). Frontend validates shapes against `Docs/api/schemas/*.json`.

| Area | Frontend component | Documented API / callback | Current fallback | Missing integration | Verify once wired |
| --- | --- | --- | --- | --- | --- |
| **Capture persistence** | `AddLinkPasteSheet` → `handle_save_capture` | `POST /saves` (`save-capture.json` → `save.json`; `409 already_saved`; `Idempotency-Key`) | Local payload + synthesized duplicate check | FastAPI capture persistence, canonicalization | Wire `on_save_capture` — duplicate without `force=true` → `409 already_saved` |
| **Extraction & processing** | `InboxView` + job stage UI | `GET /saves/{id}` → `{save, note, job}` (`job.json: state queued→ready`) | Simulated polling; fixture job states | Worker pipeline (yt-dlp/trafilatura, Muse Voice / faster-whisper) | Capture a public link → stage label steps |
| **Cloud note generation** | `app/views/note/` + `_resolve_default_markdown` | `PUT /saves/{id}/note` (`note-put.json` → `note.json`) | Fixture `note.fixtures.json` or frontmatter fallback | Meta Model API | Wire `on_save_note`; edit → `PUT` payload is full markdown |
| **Search indexing** | `search_view.py`, `search_result_card.py` | `POST /search` (`search-request.json` → `search-result.json`) | Synthesizes from fixture saves | FTS5 + faiss flat (384-dim) index | Query a transcript phrase → `match_reason: transcript` |
| **Ask & citations** | `ask_view.py`, `ask_message.py` | `POST /ask` (`ask-request.json` → `ask-answer.json`: citations mandatory) | Synthesizes answer + citations from fixtures | LLM + retrieval pipeline | Ask scoped to a folder → answer + `citations[]` chips |
| **Folders & tags persistence** | `folders/`, `folder_sheet.py`, `tag_sheet.py` | `GET/POST /folders`, `PATCH/DELETE /folders/{id}`, `PUT /saves/{id}/tags` | Mutates local state | Real folder store + depth≤3 enforcement | Create/rename/delete via `folder-write.json`; members return to Inbox on delete |
| **Settings persistence** | `settings_view.py` | **No endpoint** — device-local `settings` table (`Docs/db/0003_device.sql`) | In-memory dict; next `POST /ask` carries `engine` | No server API by design | Change `chat_model` → next `POST /ask` carries chosen `engine` |
| **Sync pull & push** | `sync_coordinator.py` | `GET /sync/pull?since=<cursor>` + `POST /sync/push` (`sync-push.json`: 7 ops) | Empty cursors locally | Authoritative store, `changes` log + idempotent replay | Wire `on_sync_pull`/`on_sync_push`; offline → queue → reconnect → replay |
| **Conflict resolution** | `ConflictBanner`, `UndoSnackBar` | `409 conflict` | Banner for stale `updated_at` | Server authoritative conflict | Cause stale write → banner; Keep Both preserves both versions |
| **Processing progress** | `InboxView`, `QuickSaveNotificationCard` | `GET /saves/{id}` polled while `state != ready` | Simulated via fixture polling | SSE/polling from `job.state` | Capture → Inbox card + notification progress advance together |

Never invent an endpoint or payload. Single source is `Docs/api/schemas/*.json`; every path is in `Docs/api/openapi.yaml`.

## H. Device-runtime boundary

- **Android notification service is not verified.** `NotificationCoordinator` + `QuickSaveNotificationCard` render a desktop preview. The **native Android spike is INCONCLUSIVE** (`Docs/Phases.md §8`).
- **Notification permission (`POST_NOTIFICATIONS`) is not verified** on a real Android device. In this build the coordinator gates on `has_completed_first_save`; on device it would be `POST_NOTIFICATIONS`.
- **OS share-target is not verified** as shipped. `ACTION_SHARE_TARGET` plumbing exists as a pre-filled intent, but no `AndroidManifest.xml` intent-filter delivery has been device-proven.
- **Background clipboard reading is prohibited by Android 10+.** The build avoids it: `AddLinkPasteSheet` performs **foreground-timed reads** — clipboard is read only after the sheet is visible.
- **Local GGUF inference is not verified.** `Chat model: Cloud | Local` and picker exist as device-local settings; the actual `llama_cpp_python` runtime is not device-proven here.
- **Desktop notification preview ≠ native notification delivery.** `notification_card.py` renders a preview payload `{"id": 1001, "header": "Claybank · now", "title": "Save a link", "ongoing": true}` — that is not a native OS notification.

All unverified items are **Device-runtime dependent** in `Docs/LIMITATIONS.md`.

## I. Known limitations

Full matrix: `Docs/LIMITATIONS.md`. Evidence: `Docs/TEST_REPORT.md`.

- **Working frontend:** shell, paste sheet, Inbox/processing, note editor, folders/tags/suggestions/review, Search+Ask UI, Settings, notification preview, conflict banner, sync coordinator — all pass `pytest -q` (374 passed).
- **Fixture/mock-based:** capture validation, note markdown fallback, search hits, Ask synthesized answers, sync cursors, notification coordinator flows.
- **Backend dependencies:** capture persistence, extraction/transcription/note pipeline, real hybrid search, real Ask retrieval, folder/tag persistence, cursor pull/push replay.
- **Device-runtime dependencies:** native notification delivery/permission, OS share-target, background clipboard, local GGUF inference.
- **Planned:** see `Docs/Phases.md` post-hackathon section.

---

*Last validated:* `Docs/TEST_REPORT.md` generation `2026-11-03` (`Python 3.12.10`, `Flet 1.0.5`, `FastAPI 0.162.0` host) — re-run `python Docs/api/test_contract.py && python Docs/db/test_schema.py && python -m pytest -q` to confirm green.
