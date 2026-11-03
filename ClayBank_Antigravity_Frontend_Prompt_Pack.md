# ClayBank Frontend Development: Antigravity Prompt Pack

This prompt pack is for completing only the ClayBank Flet frontend and UI. It follows the repository documentation and the required component-by-component workflow.

## How to use this pack

1. Open the actual ClayBank repository in Antigravity IDE.
2. Start a fresh Antigravity conversation and paste the **Project Guardrails Prompt** once.
3. For each phase, paste its **Step 1: Analyze** prompt. The agent must inspect the repository and produce a plan without editing files.
4. After reviewing the plan, paste **Step 2: Implement** for the first component only.
5. Paste **Step 3: Review, Test, Commit and Push** for that same component.
6. Repeat Step 2 and Step 3 for each remaining component in the phase. Do not combine components into one commit.
7. Move to the next phase only when every component in the current phase is reviewed and pushed, or explicitly recorded as blocked/deferred.

Important: A phase can contain many components. Step 2 and Step 3 must be repeated separately for every component. Never implement or commit an entire page as one unit. Do not commit or push this file "C:\Users\Elightbook 840\Desktop\Shefayat Vai\ClayBank\ClayBank_Antigravity_Frontend_Prompt_Pack.md"

---

# A. Project Guardrails Prompt

Paste this once at the beginning of your Antigravity project conversation.

```text
You are the frontend and UI implementation assistant for the ClayBank project. I am responsible only for the frontend and UI as a collaborator. The main developer owns backend, database, extraction, ASR, LLM, search engine, sync engine, and other backend infrastructure.

Your job is to help me implement the Flet frontend in Python, strictly following the existing repository instructions. Do not assume this is a React, Next.js, Flutter, or web application. The accepted UI stack is Flet with Python.

SOURCE-OF-TRUTH ORDER
1. Read Docs/Memory.md first. It is the project session ground truth and records the latest decisions.
2. Read Docs/Rules.md. These are hard constraints. Do not violate them for convenience.
3. Read Docs/Phases.md for the official project build order and scope.
4. Read Docs/UIUX.md for page components, Flet controls, endpoint mapping, request bodies, and response bodies.
5. Read Docs/Design.md for colors, typography, component language, typed chips, accessibility, and interaction rules.
6. Read Docs/Architecture.md, Docs/DataModel.md, Docs/GLOSSARY.md, and relevant ADRs when needed.
7. Use PrototypingFiles/Claybank_ Interactive Workflow v2.html as the visual and interaction reference. Use PrototypingFiles/Claybank App Wireframes.html for Flet widget intent.
8. Use Docs/api/openapi.yaml, Docs/api/schemas/, and Docs/api/fixtures/ for API contracts. Do not silently resolve conflicts between these sources. Report conflicts and stop the affected implementation until the main developer clarifies them.

WHEN SOURCES DISAGREE
- Memory.md records the latest decisions.
- Rules.md contains hard boundaries and overrides convenient shortcuts.
- Documentation determines product meaning and behavior.
- Prototype v2 determines look and interaction appearance.
- API schemas and fixtures are the contract for payloads.
- If a material conflict remains, report it. Do not guess, invent fields, invent endpoints, or silently choose one version.
- The note auto-save decision recorded in Memory.md on 2026-11-01 is local-first and automatic. Do not implement a manual Save-to-persist flow. The older prototype's Save note label must be reconciled with the latest decision. A Done/exit-edit control may be used only if consistent with the current code and confirmed behavior.

STRICT SCOPE
- Work only on the frontend/UI and its directly related frontend tests.
- Do not implement or modify backend endpoints, database schemas/migrations, extraction, transcription, LLM providers, embeddings, FTS5, FAISS, or sync internals.
- Do not import backend pipeline internals into Flet UI modules. UI calls the existing client/use-case layer.
- Do not independently modify API schemas, OpenAPI files, generated fixtures, database SQL, ADRs, or product decisions.
- Do not add a new endpoint or payload field to make the UI easier.
- Do not add unapproved dependencies.
- If a required frontend integration seam does not exist, report the missing seam and propose the smallest frontend-side interface. Do not build the backend behind it.

PRODUCT AND DESIGN RULES
- Use Flet and Python only for the app UI.
- Use exactly four main tabs: Inbox, Folders, Search, Settings.
- Ask is opened from Search or a folder overflow menu. Ask is not a tab.
- No authentication screens in the hackathon UI.
- The floating bubble is post-hackathon and must not be implemented in the current scope.
- Notification capture is spike-gated. Do not implement native notification behavior unless the main developer confirms the spike succeeded.
- No Resume surfaces.
- No Unsorted, Other, or Misc folder.
- Never expose `kind` as an organizing or filtering axis in the UI.
- One save has zero or one folder. Folder nesting depth is at most three.
- Tags are flat labels. Child-folder chips navigate. Tag chips filter in place.
- Folder chips are outlined and show a path. Platform chips are muted and informational. Tag chips are filled and filter. Citation/confidence chips are links or confidence indicators. Match reasons are text, not chips.
- Every organization action must show a Snackbar with Undo.
- The review queue is optional and must never feel like debt.
- Every search result explains its match reason, matched fragment, and jump target.
- Every Ask answer must have citations.
- Degraded saves remain usable. Never replace them with a dead-end error page.
- Capture always succeeds as a save operation and must not wait for extraction or AI processing.
- Videos and audio are never persisted. Do not build media-player or media-manager UI.
- Notes are Markdown as source of truth. Parse frontmatter separately and render facts as properties. Folder and tags are live controls.
- Settings use the exact copy and states specified in Design.md. The setting is called Chat model, not AI model.
- Respect light and dark themes, reduced motion, comfortable contrast, and minimum 44 px touch targets.
- Keep desktop demo parity where specified in Design.md, including keyboard search navigation.

MANDATORY WORKFLOW
Every phase has three steps:
STEP 1: Analyze and gather information. No code edits, no commits, no pushes.
STEP 2: Implement one individual component only. Do not implement a whole page or multiple components.
STEP 3: Review and test that one component. If it passes, make one component-specific commit and push it to the `aqib` branch.

A phase may contain many components. Repeat Step 2 and Step 3 for each component separately. Never batch several components into one implementation or commit. Do not move to the next component until the current component is reviewed and pushed, or clearly blocked.

GIT SAFETY
- All my work must be committed and pushed only to branch `aqib` on the configured project remote, normally `origin`.
- Never push my work to `main`, `master`, or another developer's branch.
- Never force-push, reset, rebase shared work, amend another person's commit, or discard uncommitted changes.
- Before any Git mutation, inspect `git status`, current branch, remotes, and the exact diff.
- If there are pre-existing uncommitted changes that are not mine or cannot be attributed safely, stop and report them. Do not stage them.
- If branch `aqib` is missing, the remote is unavailable, or permissions are insufficient, stop. Do not create an alternative branch or push somewhere else without my instruction.
- Stage explicit component and directly related test paths only. Never use `git add .` or `git add -A`.
- A component can have its implementation file(s) and directly related test file(s) in the same commit. It cannot include unrelated UI components or whole-page changes.
- Use a clear conventional commit message such as `feat(inbox): add processing count chip`.
- Push immediately after the component passes review and tests. Report the commit hash and push result. Never claim a push succeeded unless Git confirms it.

TESTING RULES
- For API-connected UI components, test with the existing documented demo request JSON and matching response JSON from Docs/api/fixtures/. Test success and relevant error/degraded responses.
- Read schemas and the OpenAPI contract before using a fixture. Do not hand-edit generated fixtures.
- For a UI-only component with no API endpoint, use a small JSON demo input and an explicit expected UI state in a focused test. Do not invent an API request or response.
- Mock the client/use-case boundary. Tests must not call a live backend, real ASR, real LLM, or external network.
- Run the existing relevant tests. Run `python Docs/api/test_contract.py` and `python Docs/db/test_schema.py` when the change touches or relies on those contracts, but do not modify backend contract files.
- Follow existing project tooling. Use Ruff and the configured type checker if present. Do not add tools without approval.

OUTPUT STYLE
Be precise. Cite the exact repository file paths and relevant section names you used. Separate documented facts from assumptions. Keep a checklist of completed, remaining, and blocked components. Do not say a task is complete if it has not passed tests and been pushed.

Acknowledge these rules briefly, then inspect the repository state. Do not start implementation until I give you a phase-specific Step 1 prompt.
```

---

# B. The three reusable step prompts

Use these prompts for every phase. Replace the bracketed values.

## Step 1: Analyze the phase and gather all information

```text
PHASE: [PHASE NUMBER AND NAME]

Perform Step 1 only: ANALYSIS AND INFORMATION GATHERING.
Do not edit, create, delete, move, format, or rename any files. Do not commit or push.

First inspect the current working tree and branch state. Read Docs/Memory.md, Docs/Rules.md, Docs/Phases.md, Docs/UIUX.md, Docs/Design.md, and the relevant sections of Architecture.md, DataModel.md, GLOSSARY.md, ADRs, OpenAPI schemas, fixtures, and prototype v2. Do not assume that the uploaded planning snapshot and the current working repository are identical. Inspect the actual files in this workspace.

Analyze only the frontend scope of [PHASE NAME]. Exclude all backend-owned work.

Return the following:
1. Current repository state: existing app files, Flet version/configuration if present, tests, current branch, remote name, and whether `aqib` is available. Do not change Git state.
2. Exact source files and documentation sections inspected.
3. What the phase is expected to deliver according to Docs/Phases.md, translated into frontend-only tasks.
4. An ordered list of individual UI components. Give each component a separate identifier. Do not group an entire page into one component.
5. For each component: purpose, Flet controls, visual reference, states, interactions, accessibility requirements, dependencies, and acceptance criteria.
6. For each API-connected component: exact endpoint and method, exact request fixture path, exact response fixture path, schema references, success state, and relevant error/degraded state.
7. For a component without an API: the JSON demo input and expected UI state needed for a focused test. Do not invent an API.
8. Identify any disagreement between Memory.md, Rules.md, Phases.md, UIUX.md, Design.md, OpenAPI, schemas, fixtures, and prototype. Explain its impact and mark it BLOCKED if a decision is needed.
9. Identify which components can be implemented now and which depend on a client/use-case interface or a main-developer decision.
10. Recommend exactly ONE first component to implement, with a short reason.

Do not write code. Do not create a phase-level implementation. Do not silently expand the scope. End with a clear status: READY FOR STEP 2 or BLOCKED, followed by the single recommended component name.

Wait for my next instruction.
```

## Step 2: Implement one individual component

```text
PHASE: [PHASE NUMBER AND NAME]
COMPONENT: [ONE EXACT COMPONENT FROM THE APPROVED STEP 1 PLAN]

Perform Step 2 only: IMPLEMENTATION.

Implement exactly this one component and the minimum directly related frontend test needed to verify it. Do not implement the next component. Do not implement the whole page. Do not perform unrelated cleanup or refactoring.

Before editing:
1. Re-check the relevant files and the approved Step 1 analysis.
2. Confirm that the current branch is `aqib`, or report why it is not safe to proceed. Do not switch branches if the working tree has unrelated changes.
3. Confirm that the component is not already implemented. If it is, do not duplicate it. Report its actual state.
4. Confirm the exact existing client/use-case interface. The UI must call that seam rather than backend internals. If the seam is missing, do not invent backend behavior. Implement only a genuinely separable presentation component if possible, otherwise report BLOCKED.

Implementation requirements:
- Use Flet and Python, following existing project patterns and the planned app/ module layout where relevant.
- Match prototype v2 visually and follow the documented meaning in Docs/.
- Use the exact tokens, typography, spacing, card style, typed chips, and interaction rules in Design.md.
- Add loading, empty, success, error, and degraded states where this component needs them.
- Preserve 44 px minimum touch targets, keyboard/desktop behavior where specified, theme compatibility, and reduced-motion behavior.
- Keep UI state and presentation separate from backend logic.
- Do not alter backend modules, API contracts, generated fixtures, database files, ADRs, or product documentation.
- Do not add dependencies without approval.

DEMO AND TEST REQUIREMENTS
- Use the exact demo JSON request and response fixture identified in Step 1 for API-connected components. Mock the client/use-case call. Verify request fields and response mapping.
- Also test the relevant error or degraded payload.
- For UI-only components, use the approved JSON demo input and assert the expected UI state. Do not invent an endpoint.
- Add or update only the focused test directly related to this component.
- Do not modify generated JSON fixtures. If a required fixture is missing or invalid, report that as a contract issue for the main developer.

During this step:
- Do not commit.
- Do not push.
- Do not begin another component.
- Do not edit more files than necessary for this component and its direct test.

At the end, report:
1. Files created/changed.
2. What the component does.
3. Demo request/response fixture used, or UI-only JSON input used.
4. Tests added and tests run.
5. Known issues or blockers.
6. Exact proposed commit message.
7. Confirmation that no other component was implemented.

Stop and wait for Step 3. Do not claim the component is complete yet.
```

## Step 3: Review, test, commit, and push one component

```text
PHASE: [PHASE NUMBER AND NAME]
COMPONENT: [ONE EXACT COMPONENT]

Perform Step 3 only: REVIEW, TEST, COMMIT, AND PUSH THIS COMPONENT.

Review only the component implemented in Step 2. Do not add another component or bundle multiple UI changes.

A. REVIEW
1. Inspect `git status --short`, current branch, remote configuration, and the complete diff.
2. Verify the diff contains only this component and its directly related test. Identify unrelated or pre-existing changes and leave them untouched.
3. Compare the result with the approved analysis, Docs/UIUX.md, Docs/Design.md, Docs/Rules.md, and prototype v2.
4. Check visual states, loading/empty/error/degraded states, navigation, keyboard behavior where relevant, theme compatibility, contrast, 44 px targets, reduced motion, and responsive behavior.
5. Check that UI modules do not import backend pipeline internals and that no endpoint, payload field, schema, fixture, or database contract was invented or altered.
6. Check PEP 8, typing, docstrings, and project formatting/lint conventions where applicable.

B. TEST
1. Run the focused test for this component.
2. Run the relevant existing frontend tests.
3. For API-connected components, verify the documented demo request and matching response fixture, including relevant error/degraded behavior.
4. For UI-only components, verify the approved JSON demo input and expected UI state.
5. Run the relevant project checks. Run the API contract and DB schema tests if relevant, without changing their files.
6. If a test fails, fix only this component or its direct test, then rerun the affected tests. If a failure is caused by a backend contract or missing interface, stop and report BLOCKED. Do not change backend files to force a pass.

C. GIT SAFETY CHECK
1. Confirm branch is exactly `aqib`.
2. Confirm the configured remote and target branch are correct.
3. Confirm no unrelated files are staged.
4. Stage explicit paths only. Never use `git add .` or `git add -A`.
5. If any unrelated user changes exist, if the branch is not `aqib`, or if the remote/permissions are unavailable, do not commit or push. Explain the blocker.

D. COMMIT AND PUSH
Only if the component passes review and tests:
1. Stage only this component's implementation file(s) and directly related test file(s).
2. Commit with the approved component-specific message, using this pattern:
   `feat([page]): [one component action]`
3. Push only to `origin aqib` (or the verified configured remote's `aqib` branch).
4. Never force-push. Never push to main/master or another branch.
5. Verify Git confirms the push succeeded.

E. FINAL REPORT
Return:
- Review result: PASS or FAIL.
- Tests run and exact outcomes.
- Files included in the commit.
- Commit message and commit hash, if committed.
- Push destination and confirmed result, if pushed.
- Any remaining blocker.
- The next individual component from the approved phase backlog. Do not start it.

A component is DONE only when its focused review and tests pass and its own commit is confirmed on branch `aqib`. A local commit without a confirmed push is not DONE.
```

---

# C. Frontend phase map

The phases below translate the official build plan in Docs/Phases.md into your frontend-only responsibilities. They do not transfer backend responsibilities to you. For each phase, run Step 1 once, then repeat Step 2 and Step 3 separately for every listed component.

## Phase 0: Frontend foundation and shared design system

Purpose: create the reusable visual foundation before building the screens.

Individual components, in order:

1. Theme token module for the exact light and dark palette in Docs/Design.md.
2. Typography and spacing definitions based on Design.md and prototype v2.
3. Reusable card/container component following the 16 px card and 24 px sheet radii.
4. Folder chip component, outlined and path-based.
5. Platform chip component, muted and informational.
6. Tag chip component, filled and filter-based.
7. Citation/confidence chip component, source-opening or confidence-indicating.
8. Status/progress visual component for processing and success states.
9. Snackbar component with an Undo action.
10. Shared four-tab NavigationBar with Inbox, Folders, Search, Settings.

Do not create a new tab. Do not make all chip types look and behave identically.

## Phase 1: App shell, Splash, and Onboarding

Purpose: establish the navigation shell and the first-run experience.

Individual components:

1. App shell/root layout.
2. Splash screen.
3. Splash local warm-up progress indicator.
4. Onboarding header with Back and Skip.
5. Onboarding step progress indicator.
6. Onboarding demo card.
7. Onboarding Next action and step state.
8. Four-tab route/navigation state.

Splash and onboarding have no API calls. Use JSON demo input and expected UI states for component tests. Do not add authentication screens.

## Phase 2: Add-a-link capture sheet

Purpose: implement the guaranteed in-app capture path.

Individual components:

1. AddLinkBottomSheet and its drag handle/title structure.
2. URL TextField.
3. Clipboard detection and Use it banner.
4. Suggested folder selection chip/row.
5. Capture tag selection row.
6. Optional user-context TextField.
7. Save action button and loading state.
8. Cancel/dismiss behavior.
9. Duplicate-save 409 banner with Open existing and Save again actions.
10. Capture result handoff/navigation to Inbox.

Use `POST /saves` and the exact `save-capture` request fixture with the matching `save` response fixture. Verify `409 already_saved`. `url` is the only required request field. `platform` is server-derived and must not be sent by the client. The UI must not wait for extraction or note generation before showing the durable save.

Clipboard reading must occur while the app is foregrounded and the sheet is visible. Keep the URL field usable for manual paste.

## Phase 3: Inbox and processing UI

Purpose: show the unfiled state, recently added saves, review opportunities, and processing status.

Individual components:

1. Inbox header and processing count.
2. Search entry button, which navigates to Search without running a query.
3. Quick-check banner and Review toggle.
4. Single suggestion review row.
5. Cluster suggestion review row, if present in the documented suggestion contract.
6. One-tap filing action and confidence display.
7. Ignore/dismiss action.
8. Recently added save tile.
9. Recently added horizontal list.
10. Processing save card.
11. Inbox Add Link floating action button.
12. Job status label.
13. Processing progress bar/stage indicator.
14. Skipped/failed stage state and user-facing error text.
15. Degraded-save state, including transcript-unavailable chip.

Use the documented `save-page`, `suggestion`, `save`, and `job` fixtures. Test processing through queued, extracting, transcribing, analyzing, sorting, and ready, plus independent skipped/failed stages. Do not build pipeline logic.

Every filing or ignore action must expose undo. Keep the review queue skippable and capped as described by the project docs.

## Phase 4: Item Note and Markdown editor

Purpose: render one save as one editable Markdown note.

Individual components:

1. Note header and back control.
2. Breadcrumb navigation.
3. Note overflow menu.
4. Delete confirmation surface.
5. Read-only properties grid.
6. Editable folder property control.
7. Editable tags property control.
8. Markdown note renderer with frontmatter excluded.
9. Note section/heading renderer.
10. Transcript timestamp block.
11. Search/Ask jump-target highlight and scroll target.
12. Markdown edit-mode TextField.
13. Markdown quick-insert toolbar: H, Bold, List, Task, Link.
14. Local auto-save status display: `Saved on device ✓`.
15. Conflict/recovery banner when client state provides a conflict.
16. Filing sheet with searchable folder picker.
17. Tag editor sheet.
18. Reprocess menu action and state display.
19. Open original link control.

Use `note`, `note-put`, `save-patch`, `tags-put`, `tag`, `job`, and `error` fixtures as applicable.

Important latest decision: Memory.md records that note edits are auto-saved locally after a short debounce and on page close, and queued for sync. The user does not press Save to persist. UI should show `Saved on device ✓`. Do not independently implement SQLite or the outbox. Connect to the client/use-case interface supplied by the main developer. If that interface is missing, report the dependency instead of building persistence in the UI layer.

The frontmatter is parsed separately. Source, channel, URL, duration, published and saved values are read-only. Folder and tags are interactive controls. Search jump rendering may use block-split Markdown rendering when a jump target is provided.

## Phase 5: Folders, Folder View, Tags, and Suggestions UI

Purpose: implement folder browsing and organization surfaces.

Individual components:

1. Folders page header.
2. Create Folder action.
3. Folder sort chips: Recent, A to Z, Most saved.
4. Folder cover collage.
5. Folder card.
6. Folder grid.
7. Create Folder dialog.
8. Folder long-press/overflow menu.
9. Rename Folder dialog.
10. Archive/delete confirmation as documented.
11. Folder empty state.
12. Folder breadcrumb.
13. Folder title and count.
14. Child-folder chip row, with navigation behavior.
15. Separate tag-filter row, with in-place filter behavior.
16. Folder save card/list.
17. Folder depth/reserved-name inline errors.
18. Undo feedback for folder organization actions.

Use `folder-page`, `folder`, `folder-write`, `save-page`, `save`, `tag`, and `error` fixtures as applicable. Folders are the only container. No auto-created folders. Depth is at most three. Do not create Other, Misc, or Unsorted. A deleted folder's saves return to Inbox according to the documented contract. Do not implement folder persistence or CRUD backend logic.

Suggestions/review visuals remain in Inbox. Use the suggestion fixtures and keep cluster suggestions distinct from single-save suggestions.

## Phase 6: Search and Ask

Purpose: build understandable search results and cited answers.

Search components:

1. Ask Your Library entry banner.
2. SearchBar and query state.
3. Recent search chip.
4. Platform/time filter chip presentation.
5. Search result card.
6. Match reason text.
7. Matched fragment presentation.
8. Jump-target chip for timestamp or heading.
9. Folder/tag destination presentation.
10. Score/confidence presentation where documented.
11. Cursor/infinite-scroll loading state.
12. Search empty and error states.

Ask components:
13. Ask header and Back control.
14. Scope indicator.
15. User message bubble.
16. Typing indicator.
17. Answer card.
18. Citation chip/list.
19. Suggested prompt chip.
20. Ask input field and Send action.
21. Ask loading, unavailable, and error states.

Use `search-request`, `search-page`, `search-result`, `ask-request`, `ask-answer`, and `error` fixtures. Search results must show match reason, matched fragment and jump target. Ask is not a tab. Every answer must include citations, and citations must open the relevant note location.

Known contract discrepancy: UIUX.md describes `POST /search`, while the uploaded OpenAPI/schema documentation may specify another method. Step 1 must inspect the current live workspace's OpenAPI, schemas, README, and fixtures. If the discrepancy remains, mark search API integration BLOCKED and ask the main developer. Do not choose GET or POST by guesswork. The UI presentation can be implemented independently with fixture-backed tests while the contract is clarified.

## Phase 7: Settings and device-local states

Purpose: present settings and local-device status. The hackathon spec has no Settings API endpoint.

Individual components:

1. Profile card.
2. Last-backup label and sync status chip.
3. Chat model Cloud/Local selector.
4. Chat model explanatory copy.
5. Local model picker row.
6. Local model download/setup state.
7. Running on device · slower hint when local chat is active.
8. Split storage usage row: Library and Local model.
9. Auto-sort switch row.
10. Weekly digest switch row.
11. Wi-Fi-only processing switch row.
12. Quick-save notification switch row.
13. Privacy banner.
14. Settings page navigation placement.
15. Offline/sync conflict status surface if required by the documented client state.

Settings read and write the device-local settings through the app/client layer. Do not invent an API endpoint or implement the local model runtime. Use documented copy exactly. Notes are always generated in the cloud. Chat may run on the device. Do not call the setting `AI model`.

## Phase 8: Notification capture, only if the spike succeeds

Purpose: implement the in-app capture surface opened by a native notification action.

This phase is SPIKE-GATED. First verify the main developer's documented result for the two-hour notification spike. If it failed or has not been confirmed successful, do not implement native notification UI or extensions. The in-app paste sheet from Phase 2 remains the guaranteed path.

If approved, individual frontend components/tasks are:

1. Pre-filled Add Link sheet entry state.
2. Clipboard read after the sheet is visible.
3. Empty-clipboard fallback with the URL field focused.
4. Save action using the same capture flow as Phase 2.
5. Processing status display if the client provides it.
6. Permission explanation/state shown only at the documented point.

The OS notification itself and Flet native extension are not ordinary screen components. Do not create the floating bubble. Do not request POST_NOTIFICATIONS on launch. The first permission request is after the first successful save, as recorded in Memory.md.

## Phase 9: Frontend integration and final verification

Purpose: verify the assembled UI without creating a large mixed commit.

This phase is validation, not a reason to combine components into one commit.

Review these user journeys one at a time:

1. Launch → Splash → Onboarding → Inbox.
2. Inbox → Add Link → successful capture → Inbox processing card.
3. Duplicate capture → Open Existing or Save Again.
4. Inbox → review suggestion → file/ignore → Undo.
5. Inbox → Item Note → edit Markdown → `Saved on device ✓`.
6. Item Note → move folder/edit tags → Undo.
7. Folders → child folder → tag filter → Item Note.
8. Search → explained result → timestamp/heading jump.
9. Search → Ask your library → cited answer → citation navigation.
10. Settings → Cloud/Local selector → model setup/status and preference switches.
11. Offline/degraded/conflict states where the client exposes them.
12. Notification capture only if Phase 8 was approved.

Verify:

- Exactly four tabs.
- Ask is not a tab.
- No auth screen, Resume surface, Unsorted/Other/Misc folder, or floating bubble.
- Light and dark themes.
- Minimum 44 px targets.
- Reduced-motion behavior.
- Keyboard and desktop demo behavior where documented.
- Every list uses cursor/infinite-scroll behavior where specified.
- Folder, platform, tag and citation chips retain distinct meanings and actions.
- All organization actions provide Undo.
- Every search result explains itself.
- Every Ask answer includes citations.
- Degraded saves remain usable.
- UI does not persist or play video/audio.
- The UI calls client/use-case interfaces and does not import backend pipeline internals.

Run the relevant complete frontend test suite and the documented contract/database checks. Report any failed or unavailable area accurately. Do not create a phase-wide commit. If final validation reveals a defect, fix and review it as a separate individual component commit.

---

# D. Suggested component-specific commit messages

Use one commit per component. Adjust page names to match the actual module layout.

```text
feat(shell): add theme token module
feat(shell): add shared navigation bar
feat(shell): add splash screen
feat(onboarding): add onboarding progress indicator
feat(capture): add link bottom sheet
feat(capture): add clipboard detection banner
feat(capture): add duplicate save banner
feat(inbox): add inbox header
feat(inbox): add quick check banner
feat(inbox): add review queue row
feat(inbox): add recently added card
feat(inbox): add processing save card
feat(processing): add job stage indicator
feat(note): add note properties grid
feat(note): add markdown renderer
feat(note): add markdown quick insert toolbar
feat(note): add local autosave status
feat(folders): add folder card
feat(folders): add folder grid
feat(folders): add folder breadcrumb
feat(folders): add tag filter row
feat(search): add search result card
feat(search): add jump target chip
feat(ask): add answer citation chip
feat(ask): add ask input field
feat(settings): add chat model selector
feat(settings): add storage usage row
feat(settings): add preference toggle row
```

Do not use a generic message such as `finish inbox page` or `update frontend`. The message must name one specific component.

---

# E. Phase completion tracker template

Keep this tracker in the Antigravity conversation or a local work note. Do not modify project documentation unless the main developer explicitly asks.

```text
CLAYBANK FRONTEND TRACKER
Target branch: aqib

Phase 0 - Foundation: NOT STARTED
Components:
- [ ] Theme tokens
- [ ] Typography/spacing
- [ ] Shared card/container
- [ ] Folder chip
- [ ] Platform chip
- [ ] Tag chip
- [ ] Citation/confidence chip
- [ ] Status/progress component
- [ ] Snackbar with Undo
- [ ] Four-tab NavigationBar

Phase 1 - Shell and onboarding: NOT STARTED
Phase 2 - Add Link: NOT STARTED
Phase 3 - Inbox and processing: NOT STARTED
Phase 4 - Item Note: NOT STARTED
Phase 5 - Folders and organization: NOT STARTED
Phase 6 - Search and Ask: NOT STARTED
Phase 7 - Settings: NOT STARTED
Phase 8 - Notification capture: BLOCKED UNTIL SPIKE CONFIRMED
Phase 9 - Integration verification: NOT STARTED

For every component record:
- Analysis: PASS / BLOCKED
- Implementation: DONE / NOT DONE
- JSON demo: PASS / FAIL / N/A (UI-only)
- Focused test: PASS / FAIL
- Review: PASS / FAIL
- Commit hash:
- Push confirmed: YES / NO

A component is complete only when its own test and review pass and its individual commit is confirmed on aqib.
```

---

# F. First prompt to run now

After pasting the Project Guardrails Prompt and allowing Antigravity to acknowledge it, paste this:

```text
Start with Phase 0: Frontend foundation and shared design system.
Perform Step 1 only. Inspect the actual workspace, read the required project documents, inspect the current Git branch and remote without changing them, and produce the ordered component backlog with exact file references and acceptance criteria.
Do not edit files. Do not implement anything. Do not commit or push.
Recommend exactly one first component and wait for my approval before Step 2.
```
