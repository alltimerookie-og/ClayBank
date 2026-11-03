# Claybank — Setup and Environment

## Prerequisites

- **Python 3.12.x** — `python --version` should print `3.12.*`. `pyproject.toml:requires-python >=3.12` declares the floor; the tested version for this submission is **3.12.10** (see `Docs/TEST_REPORT.md`).
- `pip`, `venv` available.
- Windows / macOS / Linux for the Flet desktop preview.

## Installation

From the repo root, in a clean virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install --upgrade pip
pip install -e .
pip install jsonschema>=4.21 referencing pytest
```

`pyproject.toml` pins `flet==1.0.5` and declares `fastapi>=0.110.0` (no upper bound at this submission; see Reproducibility below).

## Launch

```bash
flet run
# equivalent: python -m flet run
```

The app boots to **Inbox**. Add Link sheet and notification preview run against `Docs/api/fixtures/*.json` when no backend is attached. Exact entry point is the Flet project root (no extra `main.py` indirection is configured here).

## Tests

```bash
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
```

- Contracts and schemas must be green on a fresh clone.
- `pytest` covers `tests/` (52 files, 374 tests at last run).

## Configuration

Hackathon shape uses a seeded dev identity — no login screens (`Docs/adr/0006`, `Docs/Architecture.md:98-99`):

- `DEV_TOKEN` — `Authorization: Bearer <token>` expected by the eventual FastAPI backend.
- `X-Device-Id` — device identifier per request.

Both are **placeholders only**; no real secret is committed. Provide them via environment (see `.env.example`). Never commit `.env`.

## Reproducibility

- `flet` is pinned (`==1.0.5`). `fastapi` is ranged (`>=0.110.0`) at this submission — fastest compatibility, but a frozen upper bound or `uv.lock`/`requirements.lock` is recommended before freezing a release. Do not add an arbitrary upper pin without verifying `fastapi 0.162.0` (currently installed) still satisfies `Docs/api/openapi.yaml`.
- Remove or neutralize `pyrefly.toml:python-interpreter-path` absolute Windows path when sharing the repo (see `chore(repo): improve portable release hygiene`).
- A clean `pip install` from an empty venv was verified for this report.

## Troubleshooting

- `jsonschema` missing -> `pip install jsonschema>=4.21 referencing`.
- Flet not found -> `pip install -e .` inside the venv.
- Contract green but pytest fails -> check `python -m pytest -q --tb=short` for a single broken fixture import.

## Known platform restrictions

- Native notification delivery is desktop-preview only (INCONCLUSIVE spike) — guaranteed capture is the in-app paste sheet.
- Local GGUF inference requires actual `llama_cpp_python` device runtime.
- Background clipboard reads are forbidden on Android 10+; reads are foreground-timed.
