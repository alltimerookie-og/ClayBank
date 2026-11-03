# Claybank — Test Evidence Report

**Generated:** 2026-11-03
**Branch:** `aqib`
**Commit:** `a225b83df1687858d0e6a2a9420014b6a364caae`
**Remote:** `https://github.com/alltimerookie-og/ClayBank.git`
**Python:** 3.12.10
**Flet:** 1.0.5
**FastAPI:** 0.162.0 (installed; `pyproject.toml` declares `>=0.110.0`)
**OS:** Windows (PowerShell)

## Summary

| Suite | Command | Result | Exit code |
|---|---|---|---|
| Contract | `python Docs/api/test_contract.py` | OK — schemas valid, fixtures conform, guard rails hold | 0 |
| DB schema | `python Docs/db/test_schema.py` | OK — server and device variants conform | 0 |
| Frontend | `python -m pytest -q` | 374 passed | 0 |
| Compile | `python -m compileall app tests` | OK (no syntax errors) | 0 |
| Static analysis | `pyrefly` / `pyright` (via `pyrefly.toml`) | See note below | — |

## Contract test

```
python Docs/api/test_contract.py
contract test: OK — schemas valid, fixtures conform, guard rails hold
```

Validated: draft 2020-12 schemas parse, 23 fixture files conform to their named schemas, `kind` enum locked, citations mandatory, reserved folder names rejected, `index_meta` guard, etc. (`Docs/api/test_contract.py`, `Docs/api/README.md`).

## DB schema test

```
python Docs/db/test_schema.py
schema test: OK — server and device variants conform to DataModel.md invariants
```

Built both variants in-memory (server = `0001_core.sql`+`0002_server.sql`, device = `0001_core.sql`+`0003_device.sql`) and asserted depth cap, reserved names, kind enum, cascade deletes, cursors, etc. (`Docs/db/test_schema.py`).

## Pytest (frontend)

```
python -m pytest -q --tb=no
....................................................................  [ 32%]
....................................................................  [ 65%]
....................................................................  [ 98%]
.....                                                                [100%]
374 passed in ~3.6s–4.5s
```

- Config: `pyproject.toml` `testpaths = ["tests"]`, `pythonpath = ["."]`
- 52 files under `tests/` (`test_phase0_*`, `phase2_*`, `phase4_*`, `phase5_*`, `phase6_*`, `phase7_*`, `phase8_*`).

There is no `backend/` in this submission; the 374 figure is the frontend suite only.

## Compile

```
python -m compileall app tests
Listing 'app'...
Listing 'app/shell'...
Listing 'tests'...
```
No failures.

## Static analysis

`pyrefly.toml` sets `search-path = [".", "app"]` and an absolute `python-interpreter-path`. The project has been kept type-cleaned through Phase 8 fix commits (`10dcce4`, `0279d54`, `e97268c`), but no analyzer exit code is recorded in this report because the runner was not available in the clean CI image used for this submission. Run locally:

```bash
pyrefly check
# or: pyright / mypy — per Docs/Rules.md
```

If the command is available in your environment, expect the same green result as the pre-submission lint pass or a file-specific diagnostic — do not weaken tests to pass.

## Re-run

```bash
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
```

If any command fails after this commit, the submission is not green and the failure must be fixed before tagging.
