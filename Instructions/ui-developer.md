# UI developer instructions

You build the Flet client (`app/` in `Docs/Architecture.md` §5). Your product is **the prototype, real** — screens, flows, and copy are already designed and browser-verified; your job is fidelity plus honest states.

**Hard rule this file exists to serve:** degraded saves render **normally** with a "transcript unavailable" chip — never an error page — *Rules.md §2*. The UI's job is to make degradations look like the product working.

## Before the first screen

1. Open `PrototypingFiles/Claybank_ Interactive Workflow v2.html` in a browser and walk the 13-step tour. This is UI truth: layout, copy, states, and interaction (including undo) are settled. `PrototypingFiles/Claybank App Wireframes.html` carries the Flet widget intent per screen.
2. Read `Docs/UIUX.md` — the page ↔ endpoint matrix and, for each screen you build, its section (components, exact request/response JSON bodies, error-code → UI mapping).
3. Read `Docs/Design.md` (color/spacing/type tokens, typed chips, organization UX) and wire tokens into the theme in `shell/` before any screen work.
4. Read `Docs/Rules.md` §2 (hard yes) and §3 (hard no, especially the *AI honesty* block).

## Step sequence (phases from `Docs/Phases.md`)

1. **Phase 2 — app shell + capture:** 4-tab NavigationBar (Inbox · Folders · Search · Settings — no tab may be added without a grilled need). Paste sheet with clipboard detection (read after the sheet is visible, not on first frame; empty read → keep the TextField focused). Inbox renders streamed stages over SSE/polling.
   *Done when:* laptop flow — paste a link → save card in Inbox with live stage pills, matching tour step 3/4.
2. **Phase 4 — note editor:** frontmatter rendered as live controls (folder → filing sheet, tags → chips), body via `ft.Markdown` — the Flet constraints in `Docs/UIUX.md` §6 are design decisions, not options (static GFM checkboxes, frontmatter never fed to the renderer, block-split render only when a search/Ask jump arrives). Edits auto-save to the device SQLite (~1 s debounce / page close) and enqueue `note_put`; no save button; show "Saved on device" state.
   *Done when:* the prototype's item note is real for a freshly saved link.
3. **Phase 5 — organization:** Folders tab with breadcrumbs, child-folder chips, separate Tags row, single suggestion with confidence, auto-file above threshold with undo visible, review queue as a filter.
   *Done when:* save → suggestion → accept in one tap → filed, with undo visible — tour step 9/10.
4. **Phase 6 — search + Ask:** every result carries match reason + matched fragment + jump target (timestamp or heading anchor; jump = scroll + fragment flash via the block-split render); *"Ask your library"* entry at the top of Search — Ask is not a tab; citations displayed as mandatory chips.
   *Done when:* searching a spoken phrase produces a transcript hit with a timestamp jump — tour step 11/12.
5. **Phase 7 — settings + offline:** `Chat model: Cloud | Local` + local model picker, split storage row (`Library … · Local model …`), one honest offline line under the toggle; offline queue/sync states visible (writes queue, sync on reconnect, conflict → banner + keep-both recovery).
   *Done when:* airplane-mode demo matches tour expectations; `POST_NOTIFICATIONS` is requested only after the first successful save.
6. **Phase 8 — spike-gated capture:** notification capture only through the spike outcome (`Docs/Phases.md` phase 8). Paste sheet is the guaranteed demo path and stays unaffected either way.

## Boundaries (short list — full set in `Docs/Rules.md` §3)

- UI code never imports pipeline internals — it calls the client use-case layer that owns the calls.
- Batch `ft` updates (no `page.update()` per cell in loops); heavy work off the UI path with staged states shown.
- Handlers replaying real user intent (file/ignore/move/undo) are idempotent-in-UI and re-dispatchable.
- Honest labels: "Chat model", never "AI model"; offline means read/search/local-chat only; local-model download is a visible state, never silent.

## Standing checks

- Each finished screen is compared side-by-side with its prototype tour step — copy included.
- Error-code → UI mapping lives in the screen's section of `Docs/UIUX.md`; wire it, never improvise a fallback.
