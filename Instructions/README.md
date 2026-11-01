# Developer instructions — index

Two role files live here. Pick the one matching the work; both assume the orientation order below.

| I am working on… | Read |
|---|---|
| The Flet app (`app/` in `Docs/Architecture.md` §5) | [ui-developer.md](ui-developer.md) |
| The FastAPI backend (`backend/` in `Docs/Architecture.md` §5) | [backend-developer.md](backend-developer.md) |

**Orientation, both roles (before your first commit):**

1. `README.md` (repo root) — repo map, entry points, phase list.
2. `Docs/Rules.md` — hard boundaries; sections 2, 3, 5, 8 and 9 are binding on every commit.
3. `Docs/GLOSSARY.md` — use these exact words in code and UI copy.
4. `Docs/api/test_contract.py` + `Docs/db/test_schema.py` — run both from the repo root; both must be green before and after every change that touches the contract or the schema.

**Where product truth lives:** prototype v2 (`PrototypingFiles/Claybank_ Interactive Workflow v2.html`) is UI truth; the docs win on meaning when they disagree on *what things mean*; the prototype wins on *how things look*.

These instructions are mirrors of decisions already locked in the other docs — when a conflict appears between an instruction here and `Docs/Rules.md`, Rules wins and the discrepancy should be fixed here.
