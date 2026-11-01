# Claybank — Design

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**Source:** extracted from prototype CSS; flows updated for prototype v2
**Companion:** PRD.md · Architecture.md · UIUX.md · Rules.md · Phases.md · `PrototypingFiles/Claybank_ Interactive Workflow v2.html` (UI truth)

## 1. Product feel

Claybank is warm, calm, and personal. An earthy orange accent over a soft cream background; dark mode keeps the same proportions on deep charcoal. It should feel like a notebook, not a media player. "Videos are never saved" means the UI never screams "video app" — thumbnails and timestamps are details, not the identity.

## 2. Color palette

### Light mode (from prototype CSS)
- Background: `#FAF9F5` · Card: `#FFFFFF` · Ink: `#1F1E1D` · Muted: `#6B6860` · Line: `#E1DCCF`
- Accent: `#B5532F` · Accent fg: `#FFFFFF` · Accent bg: `#F6E4DA` · Accent ink: `#8A3E22`
- Ok: `#E3F0EA` · Ok ink: `#2E5E50` · Chip: `#EEEBE2` · Chip ink: `#4A4842` · Page: `#EFEBE1`

### Dark mode (from prototype CSS)
- Background: `#1C1B19` · Card: `#262421` · Ink: `#F2EFE8` · Muted: `#A8A398` · Line: `#3A3732`
- Accent: `#E08A64` · Accent fg: `#1F1E1D` · Accent bg: `#3A2A22` · Accent ink: `#F0B79C`
- Ok: `#1F3A31` · Ok ink: `#9FD3BF` · Chip: `#2F2D29` · Chip ink: `#CFCABF` · Page: `#121110`

### Cover-gradient tints (thumbnails, splash, folder collages)
- g1: `#E9A27F → #B5532F` · g2: `#8FB5A6 → #3F7766` · g3: `#9DB0D6 → #4A5F97` · g4: `#D6B36A → #9A7424`

Tasteful and consistent, not decorative noise. Folder/item thumbnails and the splash draw from these four.

## 3. Typography

- UI: `system-ui, sans-serif`, readable at small sizes.
- Note editing: `ui-monospace, monospace` for the Markdown source; rendered prose for the preview.
- Note headings: large, tight, editorial (`h1` 26 px, `h2` 17 px in the prototype).
- Meta text: muted, lightweight, clearly secondary. Do not over-style type; the prototype is restrained.

## 4. Component language

- Rounded cards (16 px; sheets 24 px), filled accent button for primary actions, card-style alt buttons for secondary.
- **Chips are typed — one shape per meaning.** This is a deliberate system upgrade over v1, where folder/platform/tag/citation all looked identical:
  | Chip type | Look | Verb |
  |---|---|---|
  | Folder | outlined + path (`Cooking / Pasta`) | navigate to folder |
  | Platform | muted, no fill (`Instagram`) | — (informational) |
  | Tag | filled chip, `#name` | filter in place |
  | Citation/AI confidence | underlined link / `· 94%` suffix | open source / explain |
  Match reasons are **text, not chips** (`Match in tag` as muted subtitle, match fragment above it). If two things look like the same chip, they must do the same verb — otherwise they don't share a look.
- Status: ok-colored for done, accent for active processing; toggle switches for settings; 4-tab bottom nav (icon + label, accent when active); bottom sheets slide up (e.g., Add link, Filing sheet); folder cover collages (4-tile gradients).
- Interaction tone: subtle entrances, not bouncy; processing stays visible and calm via progress bars; edit mode is a clear mode switch.

## 5. Icon style

Simple line icons, `stroke-width: 2`, rounded caps/joins. Set: inbox, folder, search, gear, check, back, play, tags (new), overflow `⋯`. Small, purposeful, consistent weight; used in nav, chips, cards.

## 6. Screens (prototype v2)

Splash · Onboarding · **Inbox** · Add-link sheet · Notification capture · Processing (inline) · Item note (view + edit) · Folders · Folder view · Search · Ask (from Search / folder `⋯`) · Settings. Deferred screens (kept in `PRD.md` §11): Sign in, Floating bubble.

## 7. Organization UX

The representation layer for the organization model (decisions in `PRD.md` §6): **browsing is a fallback, searching is the product** — folders are visible everywhere, navigable only on demand, and no organization action ever costs a screen transition.

### 7.1 Card anatomy (genre-agnostic, one card for video and article)
```
[thumb]  Title of the thing, two lines max
         ▶ YouTube · 12:04 · Cooking/Pasta   ← one muted meta line
         [ low-confidence dot, if any ]
```
Order is load-bearing: **title first** (what it is), mute meta line (where from, how long, where filed), optional confidence last. The folder path is **tappable text**, not a corner badge — it's where the filing sheet opens from. `kind` differences live in the note detail, never the list.

### 7.2 Three-effort model
| Effort | Example | Rule |
|---|---|---|
| Zero | capture lands in Inbox, fully usable | nothing is asked |
| One tap | suggestion chip `→ Cooking / Pasta · 94%` | **must show an undo snackbar** |
| Deliberate | card `⋯` or long-press → filing sheet | never the default path |

Auto-filing without a visible, undoable trace is the most trust-destroying thing this app could do — the one-tap accept is not silent.

### 7.3 The filing sheet (bottom sheet, never a page)
```
│  File this save                       │
│  [ search folders…              ]     │  recent: Cooking/Pasta · Research
│  ── tags ──                           │
│  [recipe ×] [sourdough ×] [+]         │  autocomplete from existing tags
│  [        Done        ]               │
```
One surface, dismissible, no navigation. The picker is **searchable** — no user should have to memorize the tree to file one save. Sheet must open **above the keyboard**, not under it.

### 7.4 Folder detail: two rows, two verbs
```
Folders / Cooking / Pasta
[ Pasta 6 ] [ Baking 9 ] [ Quick 4 ]      ← child folders → drill-down
Tags  recipe · sourdough · weeknight       ← tags → filter in place
```
Child-folder chips **navigate**; tag chips **filter**. Different verbs, visually different (filled vs outlined; chevron vs `#`). Mixing them in one unlabeled row is exactly how users stop trusting the UI. Counts hide at zero.

### 7.5 Search explains itself
Every result carries: match reason (title/transcript/body/tag/folder/semantic) → matched fragment highlighted → jump target (video timestamp / article heading), tappable. Recent searches + platform/time filter chips remain from the prototype.

### 7.6 Ask
- Reachable from Search header (*"Ask your library"*) and a folder's `⋯` (pre-scoped) — never a tab.
- Answers cite saves as chips opening the note at the right offset. Answer without citations = bug.
- Suggested prompts (from the prototype): *Summarize this week*, *What did I never open?*

### 7.7 The note is the editing surface
Frontmatter is rendered as **controls**, not code: `folder: …` → filing sheet; `tags: …` → editable chips with `+`; source/channel/duration/published → read-only facts. This removes any separate "edit details" screen and keeps the note as the single surface a user edits. Raw Markdown editing stays available (quick-insert chips + textarea).

### 7.8 Interaction rules (write-into-builds)
- **Undo on every organization action.** AI suggestions are guesses; reversibility is what makes one-tap filing acceptable.
- **No drag-and-drop filing.** `⋯` menu is primary, long-press is shortcut (and never the only discoverable path on touch).
- **The review queue is skippable forever.** It reads as an opportunity, never debt; cap what's shown, no penalty for ignoring it.
- **Empty states teach the model.** Zero folders → *"Folders appear when you have a project to put them in."* That's the onboarding — no tour.
- **Desktop parity for the demo:** search focus on load, arrow keys to navigate, `Enter` opens, `F` files.
- 44 px minimum targets; sheets above keyboard; no tap-highlight flashes; the four data rows (needs a quick check / recently added / review cap) are all one-tap from the Inbox.

## 8. Settings copy (locked)

- **`Chat model: Cloud | Local`** + a local model picker row (MiniCPM5-2B · Qwen3-1.7B) and one line under the toggle:
  *"Notes are always generated in the cloud. Chat can run on this device."*
- When Local is selected but the device is online, show **"running on device · slower"** next to the toggle while it's in use, and a visible **"setting up local model…"** state during first download. No silent downloads, no fake-fast UX.
- **Storage row (split):** `Library 4 MB · Local model 1.1 GB` — v1's "4 MB (text only)" was understated once model weights enter the picture.
- Toggles: Auto-sort new saves · Weekly digest of unopened saves · Wi-Fi only processing · Quick-save notification.
- Privacy banner (unchanged): *"videos are never saved. Cloud AI gets the transcript and metadata only."*

## 9. Accessibility and motion

- Respect `prefers-reduced-motion` (the prototype already does; Flet honors the OS setting).
- Contrast comfortable in both modes; active states use accent contrast, not color alone.
- Tap targets ≥ 44 px; labels never rely on color alone to convey a verb (folder vs tag chips differ by shape *and* label).

## 10. What "consistent with the prototype" means

Prototype v2 is look-and-feel truth; the docs are meaning-truth. If a prototype choice is odd, grill it rather than silently redesign — but "odd" is not a reason to keep a v1 inconsistency that grilling rejected (v1's three-in-one chip, its resume surfaces, its Unsorted card, its 5-tab bar are all decided: gone in v2).
