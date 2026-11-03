# Claybank UI-UX map — pages · components · API · JSON bodies

One page of truth for what each screen **is**, what sits **on** it, and what it **sends and receives** over the contract.

- **Look-and-feel truth** is `PrototypingFiles/Claybank_ Interactive Workflow v2.html`; this doc is the **wiring** truth. If they disagree on look, the prototype wins.
- Component names are **Flet control names** (`ft.` prefix denotes the framework control family).
- Tokens, chip typing, and UX rules live in `Docs/Design.md` — not repeated here.

## Envelope recap (every call)

- Success: `{ "data": <response body> }` · Error: `{ "error": { "code", "message", "detail" } }`
- List pages inside `data`: `{ items | results, cursor }` (+ filters as noted)
- IDs are UUIDv7; timestamps ISO-8601 UTC `Z`; writes carry `Idempotency-Key`

## Page ↔ endpoint matrix

| # | Page | Endpoints called (request → response bodies) |
|---|---|---|
| 1 | Splash | — (none) |
| 2 | Onboarding | — (none) |
| 3 | Inbox | `GET /saves` (`q`-less list → `save-page`) · `GET /suggestions` (→ `suggestion`) · processing card reads `job` via `GET /saves/{save_id}` (→ `{save, note, job}`) |
| 4 | Add-a-link sheet | `POST /saves` (`save-capture` → `save`) |
| 5 | Notification capture | `POST /saves` (`save-capture` → `save`) · progress reads `job.state` |
| 6 | Item note | `GET /saves/{save_id}` (→ `{save, note, job}`) · `PUT /saves/{id}/note` (`note-put` → `note`) · `PATCH /saves/{id}` (`save-patch` → `save`) · `PUT /saves/{id}/tags` (`tags-put` → `tag[]`) · `POST /saves/{id}/reprocess` (→ `job`) · `DELETE /saves/{id}` (→ `204`) |
| 7 | Folders | `GET /folders` (→ `folder-page`) · `POST /folders` (`folder-write` → `folder`) · `DELETE /folders/{folder_id}` (→ `204`; members return to Inbox) |
| 8 | Folder view | `GET /saves?folder_id=` (→ `save-page`) · `PATCH /folders/{folder_id}` (`folder-write` → `folder`) |
| 9 | Search | `GET /search` (`search-request` as query parameters → `search-page` of `search-result`) |
| 10 | Ask | `POST /ask` (`ask-request` → `ask-answer`) |
| 11 | Settings | — (device-local; see §11) |
| 12 | Processing state | not a page — `job` shape streamed across Inbox card, notification, note header (§12) |

---

## 1 · Splash — tour step 1

**Purpose:** brand moment while the local replica/tokens warm up. Never blocks on the network.

**Components:** `ft.Stack` gradient background, app mark (`ft.Icon` folder in a rounded box), wordmark (`ft.Text` display), determinate `ft.ProgressBar` (local warm-up only).

**API:** none. A cold start may already have kicked `GET /sync/pull` async, but the splash never waits on it.

## 2 · Onboarding — tour step 2

**Purpose:** teach one habit: tap Share → Claybank. Three steps, Skip always visible.

**Components:** top row (`ft.TextButton` back/skip), `ft.ProgressBar` step state, stacked demo `ft.Card`s (animated reveal), `ft.FilledButton` Next.

**API:** none.

## 3 · Inbox — tour step 3 (tab 1, home)

**Purpose:** the unfiled state. What's untouched, what's processing, what needs a check.

**Components:**
- Header: `ft.Row` — `ft.Text` "Inbox" + `ft.Chip` (ok-toned) "N processing"
- `ft.SearchBar`-style button → Search (navigates; **no query is run here**)
- **Quick-check banner** — `ft.Container`, `ft.Text` copy, `ft.TextButton` "Review" (toggle)
- **Review rows** — per item: `ft.Row` thumbnail, title, one-tap folder chip (`✱ Cooking / Pasta · 0.92`), `ft.TextButton` "Ignore"; every action → `ft.SnackBar` with Undo
- **Recently added** — horizontal `ft.ListView` of `ft.Card` tiles (thumbnail, title, meta line incl. folder path)
- **Processing card** — "New: <title>" + stage label + `ft.ProgressBar` (fed by `job`, see §12)
- `ft.FloatingActionButton` "+" → Add-a-link sheet
- `ft.NavigationBar` (4 tabs, shared component on tabs 1–4)

**API:**
- `GET /saves?inbox=true&needs_review=<bool>&kind=<opt>` → `save-page` (`items` of `save`, `cursor`)
- `GET /suggestions` → `suggestion` (`type: single|cluster`, `path`, `confidence`, `dismissed_at`) — shown as the review row's folder chip seed
- Processing card: `GET /saves/{save_id}` → `{save, note, job}` (`job.state`, `job.skipped`/`failed`, `job.error`)

**Undo mapping:** filing = `PATCH /saves/{id}` (`save-patch`), ignore = dismiss suggestion, both restorable. Undo for delete lives on the Item page (§6).

## 4 · Add-a-link sheet (capture) — tour step 4

**Purpose:** the guaranteed capture path. Clipboard read happens *here*, in the foreground.

**Components:** `ft.BottomSheet` (slide-up): drag handle, `ft.Text` title, `ft.TextField` (URL, readonly-filled by paste), "Use it" banner (`ft.Container` + `ft.TextButton`) when the clipboard holds a URL, one-tap folder row (`ft.Chip` outlined), tags row (`ft.Chip` `#name`), optional `note` `ft.TextField`, `ft.FilledButton` Save, `ft.OutlinedButton` Cancel.

**API:** `POST /saves` with `Idempotency-Key`
- Request: `save-capture` — `url` (only required field), `source_app`, `user_context`, `suggested_folder_id`, `force`
- Response: `201` → `save` (`kind` starts `unknown`) → navigate to Inbox processing card
- `409` → `error` `already_saved` with existing id in `detail` → banner with **Open existing** / **Save again** (`force=true` resend under the same key)

**Rules:** the body never awaits the pipeline. `platform` is server-derived — never a field of the request.

## 5 · Notification capture — tour step 5 (spike-gated)

**Purpose:** capture without opening the app. The shade is OS UI, not `ft.` composition; the in-app half is the same sheet as §4.

**Components (OS):** persistent *"Save a link"* notification with `Paste and save` action (via `flet-android-notifications`; behavior contract in `Memory.md`). Progress notification "Saving: <title> · Step k of N" mirrors `job.state` while the pipeline runs.

**Components (in-app):** on action tap → app foregrounds → the §4 sheet opens **pre-filled**. Clipboard read happens after the sheet is visible, not on the first frame; if empty, the `ft.TextField` keeps focus for keyboard paste.

**API:** same as §4. `POST_NOTIFICATIONS` is requested after the **first successful save**, never earlier.

## 6 · Item note — tour step 8 (from Inbox/Folders/Search/Ask citations)

**Purpose:** one save, one note, Markdown as source of truth. No video is stored.

**Components:**
- Header: `ft.Row` — back, breadcrumb (`Folders / Cooking / Pasta`), `↩ move` affordance, `ft.TextButton` Edit, `ft.PopupMenuButton` `⋯` (Move / Edit tags / Reprocess / Delete…)
- Delete confirm — inline `ft.Container` "Delete this note and its save?" + Delete/Cancel
- **Properties grid** (rendered frontmatter, not code): `source`, `channel`, `video_url` (link), `duration`, `published`, `saved` as `ft.Text`; **`folder` and `tags` are live controls** — tapping opens the filing sheet / tag editor, no Edit mode needed
- Note body: `ft.Markdown` — Overview, Key points, Steps, Links mentioned, Transcript as timestamped `>` blockquotes. `extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED`, `selectable=True`, `on_tap_link` handler, `md_style_sheet` mapped to Design tokens. **Flet constraints baked into the design:** GFM checkboxes render but are static (toggling lives in Edit mode); frontmatter is never fed to the renderer (parsed YAML → the Properties grid above); scroll-to-`jump_target` uses a block-split render (body split at headings into per-block `ft.Markdown(shrink_wrap=True)` items in an `ft.ListView`, `scroll_to` the `0:42` blockquote/heading, flash the matched fragment) — used only when a search/Ask jump arrives, plain single-control render otherwise; note bodies stay pure Markdown (HTML tags are flattened by the renderer).
- Edit mode: `ft.TextField` multiline ui-monospace with an insert toolbar row (H / **B** / List / Task / Link) + `ft.FilledButton` becomes "Save note"
- Filing sheet: searchable folder picker (searchable, per Design §filing) + Done; every action → `ft.SnackBar` with **Undo**

**API (all under `Idempotency-Key`):**
| Action | Call | Request → Response |
|---|---|---|
| Open | `GET /saves/{save_id}` | → `{save, note, job}` |
| Edit note | `PUT /saves/{id}/note` | `note-put` (`markdown`, `updated_at`) → `note` |
| Move folder | `PATCH /saves/{id}` | `save-patch` (`folder_id`, `tag_ids`, `user_context`, `updated_at`) → `save` |
| Edit tags | `PUT /saves/{id}/tags` | `tags-put` (`tag_ids`, `updated_at`) → `tag[]` |
| Reprocess | `POST /saves/{id}/reprocess` | → `job` (metadata & transcript only; body untouched) |
| Delete | `DELETE /saves/{id}` | → `204` |
| Undo delete | `POST /saves` | **same `save-capture` payload + same `Idempotency-Key`** → replay restores the original save |

`updated_at` on the two PUT/PATCH bodies is the stale-write guard → `409` `conflict` → banner, no silent overwrite.

**Auto-save is local-first and automatic.** The user never presses Save to persist:
1. **every edit is written to the device SQLite replica immediately** (debounced ~1 s after typing pauses, and on page close) — new `markdown` + a fresh `updated_at` on the local row; the visible state is a quiet `Saved on device ✓`;
2. the same write **enqueues a `note_put` op in `device_queue`** (payload = the `note-put` shape, own `Idempotency-Key`);
3. the outbox replays via `POST /sync/push` when the device next syncs — the edit survives an app kill, crash, and network loss;
4. a stale push (`409` `conflict`) keeps both versions (banner + recovery), per Rules §5.
The per-item endpoints (`PUT /saves/{id}/note` etc.) remain the API shape — direct wire calls won't race the local write; the queue is the only writer from the app.

## 7 · Folders — tour step 9 (tab 2)

**Purpose:** the only container. Project grids, sort chips, no "Unsorted" card (Inbox is that state).

**Components:** header `ft.Row` ("Folders" + "+ New" `ft.Chip`), sort row (`ft.Chip`: Recent / A–Z / Most saved), `ft.GridView` of folder cards (4-tile color mosaic, name, `save_count` + recency line — zero counts hidden), explainer `ft.Text`, `ft.NavigationBar`.

**API:**
- `GET /folders` → `folder-page` (`items` of `folder`, `cursor`)
- `POST /folders` → `folder-write` (`name`, `parent_id`, `archived_at`) → `folder` (`id: null` in create requests)
- Long-press menu: rename = `PATCH /folders/{folder_id}` (`folder-write` → `folder`, rename is a bulk frontmatter rewrite); archive uses `archived_at`; delete = `DELETE /folders/{folder_id}` → `204` (member saves return to Inbox; `ft.SnackBar` Undo is local-state-first)

## 8 · Folder view — tour step 10

**Purpose:** drill and filter. Two separate chip rows with different verbs.

**Components:** breadcrumb back row, `ft.Text` title + count, **FOLDERS row**: child chips `Pasta 6 ›` (`ft.Chip` outlined — *navigate*), **TAGS row**: `#recipe` chips (`ft.Chip` filled — *filter in place*), save cards (thumbnail, title, one-liner, platform chip `├ Instagram`, tag chips), `ft.NavigationBar`.

**API:**
- `GET /saves?folder_id=<uuid>` → `save-page`
- Tag filter resolves client-side against loaded items (taxonomic, not a new result set)
- Header `⋯`: rename/move = `PATCH /folders/{folder_id}` (`folder-write` → `folder`); depth error `422` (`folder_depth_exceeded`) → inline sheet message

## 9 · Search — tour step 11 (tab 3)

**Purpose:** keyword + meaning in one result list. Every result explains itself.

**Components:** "Ask your library" banner row (`ft.Container` + `ft.Icon` chat → Ask, scoped or everything), `ft.SearchBar` (typed query state), Recent chips (`ft.Chip` neutral), filter chips (`All / YouTube / Instagram / This month`), result cards: thumbnail, title, **match line as text** (`Match in transcript · "add cream"` italic fragment) + jump chip (`ft.Chip` "▶ 0:42") + destination chip (folder/tag) + muted score, `ft.NavigationBar`.

**API:** `GET /search`
- Request: `search-request` as query parameters — `q` (required), `folder_scope` (folder uuid or null = everything), `cursor`
- Response: `search-page` — `results` of `search-result`: `save`, `match_reason` (`title|transcript|body|tag|folder|semantic`), `fragment`, `jump_target` (`0:42` timestamp or heading anchor), `score`
- Tap jump chip → opens the note **at the anchor** (§6), not at the top

## 10 · Ask — tour step 12 (opened from Search / folder `⋯`)

**Purpose:** folder-scoped answers that cite the saves they used. Not a tab.

**Components:** breadcrumb header + "Scope: Cooking" `ft.Chip`, user bubble (`ft.Container` right-aligned), typing dots, answer card: `ft.Text` answer + "Based on N saves" line + **citation chips** (`ft.Chip` tag-toned, each opens the note; answers without citations are a bug), "Try asking" chips, input bar (`ft.TextField` + Send).

**API:** `POST /ask`
- Request: `ask-request` — `question` (required), `save_scope`, `engine` (chat model choice from Settings: cloud or local)
- Response: `ask-answer` — `answer`, `citations` (**mandatory** — contract-tested), `scope`, `engine`

## 11 · Settings — tour step 13 (tab 4)

**Purpose:** account/sync summary, AI split, storage, capture toggles.

**Components:** profile card (avatar `ft.CircleAvatar`, name, "Last backup", Synced `ft.Chip`), **Chat model card** ("Cloud | Local" + explainer "Notes are always generated in the cloud"), local model picker row (`ft.Chip`: MiniCPM5-2B · Qwen3-1.7B + first-use download state), split storage row (Library · Local model), `ft.Switch` rows (auto-sort, weekly digest, Wi-Fi-only processing, quick-save notification), privacy banner, `ft.NavigationBar`.

**API:** **none in the hackathon**. This screen reads/writes the device `settings` table (`chat_model ∈ cloud|local`, `cluster_min_size ≥ 3`, sync state, storage counters — `Docs/db/0003_device.sql`). No endpoint serves settings; changes take effect on the next call (e.g. `POST /ask` carries `engine`).

## 12 · Processing state — cross-cutting, not a page

`job` (`save_id`, `state`, `tier`, `skipped[]`, `failed[]`, `error`) streams through three surfaces:

| Surface | What shows | Where the data comes from |
|---|---|---|
| Inbox card | "New: <title>" + stage + bar | `GET /saves/{save_id}` polled while `state ≠ ready` |
| OS progress notification | "Saving: <title> · Step k of N" | same values via the notification extension |
| Item note header | stage strip chips (Fetched · Transcribing · Sorting) | `job.skipped`/`failed` render as their own states; `error` is user-facing text |

`state` enum is linear for display only: `queued → extracting → transcribing → analyzing → sorting → ready`. Stages skip or fail **independently** — a failed stage shows `error`, others still proceed.

## Cross-cutting rules

- **Undo everywhere:** file/move/tags/delete all end in `ft.SnackBar` + Undo; delete undo is a same-`Idempotency-Key` replay (§6). Undo that can't replay server-side restores local state first and never lies about being saved.
- **Error → UI mapping:** `already_saved` → open-or-force banner · `conflict` → stale-write banner (keep-both recovery) · `folder_depth_exceeded` / `reserved_folder_name` → inline sheet errors · `llm_unavailable` / `asr_unavailable` / `extraction_failed` / `transcription_failed` → job failed-stage text · `contract_version_mismatch` → "update the app" screen (not a toast) · `unauthorized` → session setup retry.
- **Chip typing is schema-typed:** folder chip shows `save.folder_path`/suggestion `path`; platform chip = `save.platform`; tag chip = tags from `save`/`tag[]`; citation chip = `ask-answer.citations` member. Same visual family, same JSON origin.
- **Every list ends in a cursor:** Inbox, folders, search results, sync pulls. Cursor surfaces in the UI as infinite scroll — never as a page number.
- **Degraded, never dead:** a save with `kind: unknown` renders a lean card (thumbnail-less) and *stays* in the pipeline (§12). The UI never drops data silently.
