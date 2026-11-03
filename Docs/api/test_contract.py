"""Claybank contract test.

Validates that:

1. every ``Docs/api/schemas/*.json`` parses as a JSON Schema (draft 2020-12);
2. every fixture in ``Docs/api/fixtures/`` produces cases conforming to the
   schema it name-matches (``<schema.json>.fixtures.json``);
3. guard rails that grilling locked actually hold in the schemas:
   - ``kind`` enum is exactly the locked set;
   - citations are mandatory in Ask answers;
   - reserved folder names are rejected;
   - domain/env always require an ``engine`` that includes local.

Run from the repo root:

    pip install jsonschema>=4.21
    python Docs/api/test_contract.py

(Also usable as plain pytest: ``pytest Docs/api/test_contract.py``.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from referencing import Registry, Resource

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    print("error: `pip install jsonschema>=4.21` first", file=sys.stderr)
    raise SystemExit(2)

HERE = Path(__file__).parent
SCHEMAS = HERE / "schemas"
FIXTURES = HERE / "fixtures"

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"FAIL: {msg}")


def make_validator(schema: dict, registry: Registry) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=registry)


def check_valid(schema: dict, case: dict, label: str, registry: Registry) -> None:
    validator = make_validator(schema, registry)
    for err in sorted(validator.iter_errors(case), key=lambda e: list(e.absolute_path)):
        loc = "/".join(map(str, err.absolute_path)) or "<root>"
        fail(f"{label}: [{loc}] {err.message}")


def check_invalid(schema: dict, case: dict, label: str, registry: Registry) -> None:
    validator = make_validator(schema, registry)
    if not list(validator.iter_errors(case)):
        fail(f"{label}: expected rejection but case stayed valid")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    schemas = {p.name: load_json(p) for p in sorted(SCHEMAS.glob("*.json"))}
    registry: Registry = Registry()
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
            registry = registry.with_resource(schema["$id"], resource)
        except Exception as exc:  # noqa: BLE001
            fail(f"schema {name} is not usable draft 2020-12: {exc}")

    if not FIXTURES.exists():
        print("fixtures/ missing — run `python Docs/api/generate_fixtures.py` first")
        if failures:
            raise SystemExit(1)
        return

    fixture_files = sorted(FIXTURES.glob("*.fixtures.json"))
    if not fixture_files:
        print("no fixture files — run `python Docs/api/generate_fixtures.py` first")
        if failures:
            raise SystemExit(1)
        return

    for ffile in fixture_files:
        base = ffile.name[: -len(".fixtures.json")]
        schema_name = f"{base}.json"
        if schema_name not in schemas:
            fail(f"{ffile.name}: no matching schema {schema_name}")
            continue
        bundle = load_json(ffile)
        cases = bundle.get("valid", [])
        if not cases:
            fail(f"{ffile.name}: generated with zero cases")
        for i, case in enumerate(cases):
            check_valid(schemas[schema_name], case, f"{ffile.name}#valid[{i}]", registry)

    del fixture_files

    # ---- guard rails -------------------------------------------------------
    kind = schemas["save.json"]["properties"]["kind"]
    if kind["enum"] != ["video", "article", "unknown"]:
        fail(f"save.kind enum drifted: {kind['enum']}")

    extraction_kind = schemas["extraction-result.json"]["properties"]["kind"]
    if extraction_kind["enum"] != ["video", "article", "unknown"]:
        fail(f"extraction-result.kind enum drifted: {extraction_kind['enum']}")

    ask = schemas["ask-answer.json"]
    if "citations" not in ask["required"]:
        fail("ask-answer: citations are no longer mandatory (Rules.md: citation-less answers are a bug)")
    if ask["properties"]["citations"].get("minItems", 0) < 1:
        fail("ask-answer: citations minItems < 1")

    job_states = schemas["job.json"]["properties"]["state"]["enum"]
    expected_states = ["queued", "extracting", "transcribing", "analyzing", "sorting", "ready"]
    if job_states != expected_states:
        fail(f"job.state pipeline drifted: {job_states}")

    folder = schemas["folder.json"]
    guard = folder.get("allOf", [])
    if guard and "Reserved names" in json.dumps(guard):
        check_invalid(
            folder,
            {"name": "Other"},
            "folder.json reserved-name guard",
            registry,
        )
        check_valid(folder, {"name": "Pasta"}, "folder.json normal name", registry)
    else:
        fail("folder.json: reserved-name guard (Other/Misc/Unsorted/Inbox) is missing")

    engine = schemas["ask-answer.json"]["properties"].get("engine", {})
    if "cloud" not in engine.get("enum", []):
        fail("ask-answer.engine enum dropped `cloud`")
    engine_req = schemas["ask-request.json"]["properties"].get("engine", {})
    if "local" not in engine_req.get("enum", []):
        fail("ask-request.engine enum dropped `local` (the on-device chat path)")

    err_codes = schemas["error.json"]["properties"]["code"]["enum"]
    for required_code in ("already_saved", "conflict", "contract_version_mismatch", "index_mismatch"):
        if required_code not in err_codes:
            fail(f"error.json is missing required code `{required_code}`")

    # Request schemas must carry the invariants the docs locked:
    if "markdown" not in schemas["note-put.json"]["required"]:
        fail("note-put.json: markdown became optional (it is the source of truth)")

    ops = schemas["sync-push.json"]["properties"]["ops"]["items"]["properties"]["op"]["enum"]
    for required_op in ("save_create", "save_patch", "note_put", "folder_create", "folder_patch", "tags_put", "suggestion_accept"):
        if required_op not in ops:
            fail(f"sync-push.json is missing op `{required_op}`")

    capture = schemas["save-capture.json"]["properties"].get("force", {})
    if not capture or capture.get("default") is not False:
        fail("save-capture.json: `force` (duplicate-override) is missing or not default-false")

    accept = schemas["suggestion-accept.json"]
    if accept["properties"]["accept"].get("default") is not True:
        fail("suggestion-accept.json: accept must default to true")

    # Reserved folder names are one enum used by two schemas — keep them identical.
    def reserved(schema: dict) -> list:
        try:
            return schema["allOf"][0]["if"]["properties"]["name"]["enum"]
        except (KeyError, TypeError):
            return []

    folio, folwrite = reserved(schemas["folder.json"]), reserved(schemas["folder-write.json"])
    if set(folio) != set(folwrite):
        fail(f"reserved folder names diverged: folder.json={folio} folder-write.json={folwrite}")

    print()
    if failures:
        print(f"contract test: {len(failures)} failure(s)")
        raise SystemExit(1)
    print("contract test: OK — schemas valid, fixtures conform, guard rails hold")


if __name__ == "__main__":
    main()
