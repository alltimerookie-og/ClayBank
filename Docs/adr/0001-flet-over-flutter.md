# ADR 0001 — Flet over Flutter for the app shell

**Status:** Accepted · **Date:** 2026-10-31
**Context:** The prototype names Flet controls ("Plain Flet controls only"), but the first draft of Architecture.md left "Flutter vs Flet" open because both target mobile for a Python-native team.

## Decision

The UI is **Flet (Python)**, Android-first via `flet build apk`. The demo runs on a laptop with the paste-a-link flow; Android is the capture surface. Flutter is not used in any milestone of the current build.

## Why

- **One language across the stack.** The backend is FastAPI; the extraction, ASR, LLM and embedding glue is Python libraries. Flet means the whole project is Python — no second toolchain, no Dart, no state-porting between artifacts.
- **The prototype was already annotated in Flet controls** (AppBar, SearchBar, Card, Dismissible, NavigationBar per screen in `Claybank App Wireframes.html`) — the screens map to their implementation widgets.
- **Binary wheels exist for the deferred features.** The post-hackathon on-device plan (`adr/0008`) needs `llama_cpp_python`, `onnxruntime`, `faiss-cpu`, and `flet-libffmpeg` inside the app; all ship as Android/iOS wheels on `pypi.flet.dev` for Flet's runtime.

## What we give up (and why it's fine)

- Flutter's polished navigation/gesture ecosystem and faster render speed. Claybank is a **list-and-note app** — scroll, cards, forms, a sheet. None of those features need 120 fps.
- The floating bubble needs a custom Flet extension regardless of framework; Flutter would not save that work.

## Consequences

- App code lives in `app/` (see Architecture.md §5), built with `flet build`.
- RTL/multiplatform concerns are accepted: iOS is deferred; desktop is the laptop demo.
- If a hard Flet blocker appears (capture from notification, share intent), the fallback is a thin native Android shim, not a rewrite of the app shell.
