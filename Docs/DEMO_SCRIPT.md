# Claybank - Demo Script (Remote Submission Recording)

Official flow: `Docs/Phases.md:102-105`. Decision-by-decision bullets, not prose. Laptop `flet run` is the safest capture path; phone is optional. Offline shown with network visibly off.

## Before you record

- Fixtures stand in for a live backend - note generation, search ranking, and sync cursors are fixture-backed.
- Guaranteed path is the **in-app paste sheet** - native notification is desktop-preview only (see shot 13).
- Recording host is up to you; drop the link into `Docs/SUBMISSION.md` placeholder after.

## Shot list

| # | Screen/Action | Must be visible | Narration bullets | Expected result | Setup | Backend/device? |
|---|---|---|---|---|---|---|
| 1 | Inbox landing | Header, processing pill, Recently Added carousel, search entry | Inbox is the unfiled state | List of saves | Seeded saves/fixtures | Frontend only |
| 2 | Capture - paste sheet open | Sheet slides up, URL field focused | One paste is enough to capture | Empty sheet ready | Tap Add Link |  |
| 3 | Capture - clipboard prefill | Clipboard link auto-filled (foreground-timed read) | Foreground read, not background | `inbox_paste` source | Link copied beforehand | Foreground clipboard |
| 4 | Capture - submit | User_context field, quick-tag chips, Save | One tap creates the save | Save appears in Inbox | Enter URL + optional note | Backend would canonicalize/dedupe |
| 5 | Processing | Inbox card with `queued -> ready` stages + progress | Durable capture, streamed enrichment | Stage bar updates | Same save | Real job worker is backend |
| 6 | Note open + edit | Properties grid, frontmatter as controls, Markdown editor | One note per save, Markdown truth | Note readable | Tap the new save | Fixture fallback for markdown |
| 7 | Note filing + tags | Filing sheet (depth<=3), tag chips, undo snackbar | Reversible organization | Folder + tags set | Move via sheet |  |
| 8 | Folders | Grid, breadcrumb, child-folder chips navigate / tag row filters | Folders are intent, not topics | Folder view with saves | With folders |  |
| 9 | Review with Undo | One-tap `suggested_folder` chip + Ignore + Undo bar | AI suggests, user disposes | Save filed or ignored, undo offered | Suggestion with confidence | Threshold is config |
| 10 | Search | Query + `match_reason + fragment + jump_target + score` | Every hit explains itself | Filtered results | Type phrase from transcript | Real ranking is backend (FTS5+faiss) |
| 11 | Search jump | Fragment highlighted; tap jump_target | Actionable match | Opens note at anchor | Tap jump chip/timestamp |  |
| 12 | Ask with citations | Folder-scoped Q + answer + citation chips | Cited answers, citations mandatory | At least one chip opens note | Ask in folder scope | Backend LLM + retrieval |
| 13 | Notification preview | Persistent `Save a link` + `Paste and save` / `Open app` | **Preview only - native delivery INCONCLUSIVE** | Foreground sheets pre-filled | `NotificationCoordinator` preview | Native delivery is device-runtime |
| 14 | Settings | Chat model Cloud|Local + picker (MiniCPM5-2B/Qwen3-1.7B), split storage, toggles, privacy banner | Settings are device-local | Open Settings | Local inference not running |
| 15 | Offline queue/sync | Network indicator visibly OFF, queued write, then Syncing/Synced + conflict banner path | Writes queue idempotently | Queued op replays on reconnect | `SyncCoordinator` simulation + toggle wifi/airplane | Live cursor server is backend |
| 16 | Edge cases (Rules.md 5) | Degraded save (no transcript), 409 conflict `keep-both`, AI-sort off -> Inbox with suggestion | Degraded, not dead | Each edge renders, not an error page | Seeded degraded + conflict saves |  |

## Notes

- Keep each decision isolated in one continuous take; speak bullets, not a script of prose (`Docs/Phases.md:102`).
- Mark shot 13 and 16 as conditional - if the runtime cannot show them, keep the paste sheet and Inbox as the honest proof and disclose in `Docs/LIMITATIONS.md`.
- No dummy video or screenshots will be committed until the user supplies the actual recording.
