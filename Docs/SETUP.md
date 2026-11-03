# Claybank — Developer Setup

This guide lets you clone `aqib`, install Claybank, run the Flet frontend locally, and verify the submission package. It assumes no prior knowledge of the project.

## Prerequisites

Inspect these before you start:

- **Python 3.12.x** — verified on this machine with `python --version` → `Python 3.12.10`. `pyproject.toml` declares `requires-python = ">=3.12"`. Use 3.12; 3.13 is not verified.
- **pip** + **venv** — both ship with Python 3.12. Run `python -m pip --version` to check. `venv` is the stdlib virtual-env tool.
- **Git** — any recent version. Verified command used in this guide: `git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git`.
- **Flet 1.0.5** — `pip show flet` should report `Version: 1.0.5` (pinned in `pyproject.toml: dependencies`).
- **OS** — Windows 10/11, macOS 13+, or Linux (x64). Flet's desktop preview works on all three. No Android build is required for local inspection.
- **Optional dev tools** — `jsonschema>=4.21` + `referencing` for `Docs/api/test_contract.py`, `pytest` for the frontend suite. `pyrefly` is configured via `pyrefly.toml: search-path = [".", "app"]` if you want static analysis; it is not required to run the app.

Do not invent version requirements. If `python --version` is not 3.12, install 3.12 and re-check before continuing.

## 1. Clone the repository

From any empty parent folder:

```powershell
git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git
cd ClayBank
```

You are now on branch `aqib`.

## 2. Create a virtual environment

**Windows PowerShell (verified):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that session, or use `\.venv\Scripts\activate.bat`.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

## 3. Install dependencies

Inside the activated venv, from the repo root:

```bash
python -m pip install --upgrade pip
pip install -e .
pip install jsonschema>=4.21 referencing pytest
```

- `pip install -e .` reads `pyproject.toml` → `flet==1.0.5` (pinned) + `fastapi>=0.110.0` (ranged; installed 0.162.0).
- Verify: `pip show flet` → `Version: 1.0.5`, `python -c "import app.app; print('app imports ok')"`.
- Fallback if `pip install -e .` fails on Windows: `pip install flet==1.0.5 fastapi referencing jsonschema pytest`.

## 4. Run the application

The Flet entry point is the project root — no extra `main.py` is needed:

```powershell
flet run
```

- A desktop window opens (or a browser tab — both are valid desktop preview modes).
- The app boots to Splash → Onboarding (if `has_seen_onboarding` is false) → Inbox. Use the bottom bar to switch tabs: Inbox · Folders · Search · Settings. Ask is not a tab — it opens from Search or a folder `⋯` (`app/shell/nav.py: TAB_COUNT = 4`).
- Add Link sheet slides up from the Inbox header's Add action. Paste a link there; fixtures in `Docs/api/fixtures/*.json` back the save when no backend is running (`app/app.py: _resolve_default_markdown`).

How to stop: close the Flet window, or press `Ctrl+C`.

When startup fails:

- `No module named 'flet'` → not in venv: re-run `\.venv\Scripts\Activate.ps1` and `pip install -e .`.
- `flet: command not found` → venv `Scripts/` not on PATH: re-activate the venv.
- Port already in use → stop the previous `flet run` process and retry.
- Python version mismatch (e.g. 3.11) → install Python 3.12 and recreate `.venv`.

Do not claim Android APK support from this host — `flet build apk` requires Android SDK/NDK.

## 5. Run automated checks

From the repo root with the venv active:

```powershell
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
```

- `test_contract.py` — every `Docs/api/schemas/*.json` parses as draft 2020-12; every fixtures file conforms; guard rails hold (locked `kind` enum, mandatory `citations`, reserved names, `engine` includes `local`). Needs `jsonschema>=4.21`.
- `test_schema.py` — stdlib `sqlite3` only; builds both store variants in memory and asserts depth cap, reserved names, kind enum, unique tags, cascades, FTS rows, `settings.chat_model` enum.
- `pytest` — 52 files (phase 0/2/4/5/6/7/8) — 374 passed. Config: `pyproject.toml` `testpaths = ["tests"]`, `pythonpath = ["."]`. Fixture/mock-backed — not proof of a live backend.
- `compileall` — syntax-only check; no output means no syntax errors.

All four must be green before any contract change (`Docs/Rules.md` §7). Evidence: `Docs/TEST_REPORT.md`.

## 6. Configuration

Hackathon shape uses a seeded dev identity — no login screens (`Docs/adr/0006`):

- `DEV_TOKEN` — `Authorization: Bearer <token>` expected by the eventual FastAPI backend.
- `X-Device-Id` — device identifier per request.

Both are placeholders only. Copy `.env.example` → `.env` and fill locally only if a backend is running. Never commit `.env`.

## 7. Reproducibility

- `flet==1.0.5` is pinned. `fastapi>=0.110.0` is ranged. Freezing an upper bound or adding `uv.lock` is recommended before a release, but do not add an arbitrary pin without verifying it still satisfies `Docs/api/openapi.yaml`.
- `pyrefly.toml` now contains only `search-path = [".", "app"]`.

## 8. Known platform restrictions

- Native notification delivery is desktop-preview only (INCONCLUSIVE spike) — guaranteed path is the in-app paste sheet.
- Local GGUF inference requires actual `llama_cpp_python` device runtime.
- Background clipboard reads are forbidden on Android 10+; reads are foreground-timed.

---

Next: `Docs/MANUAL_TESTING.md` — step-by-step manual workflows for every screen.
