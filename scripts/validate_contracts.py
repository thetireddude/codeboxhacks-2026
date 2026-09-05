"""Validate shared JSON schemas and their Milestone 0 fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas"
FIXTURE_DIR = ROOT / "shared" / "fixtures"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    schemas = {path.name: load_json(path) for path in SCHEMA_DIR.glob("*.json")}
    fixtures = {path.name: load_json(path) for path in FIXTURE_DIR.glob("*.json")}

    expected_schemas = {
        "match-state.json",
        "transcript-event.json",
        "scenario.json",
        "results.json",
    }
    expected_fixtures = {
        "mock-match.json",
        "mock-transcript.json",
        "mock-scenario.json",
        "mock-results.json",
    }
    if set(schemas) != expected_schemas:
        raise AssertionError(f"Schema set differs: {set(schemas) ^ expected_schemas}")
    if set(fixtures) != expected_fixtures:
        raise AssertionError(f"Fixture set differs: {set(fixtures) ^ expected_fixtures}")

    registry = Registry()
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))

    def validate(schema_name: str, instance) -> None:
        Draft202012Validator(
            schemas[schema_name],
            registry=registry,
            format_checker=FormatChecker(),
        ).validate(instance)

    validate("scenario.json", fixtures["mock-scenario.json"])
    validate("match-state.json", fixtures["mock-match.json"])
    validate("results.json", fixtures["mock-results.json"])
    for event in fixtures["mock-transcript.json"]:
        validate("transcript-event.json", event)

    print(
        f"Validated {len(schemas)} schemas and {len(fixtures)} fixtures "
        "(including every mock transcript event)."
    )


if __name__ == "__main__":
    main()
