"""Print one Gemini-generated scenario for local A1 verification."""

from __future__ import annotations

import sys

from app.config import AppConfig
from app.services.scenario_service import (
    ScenarioGenerationError,
    create_scenario_service,
)


def main() -> int:
    try:
        scenario = create_scenario_service(AppConfig).generate_scenario()
    except ScenarioGenerationError as error:
        print(f"Scenario generation failed: {error}", file=sys.stderr)
        return 1

    print(scenario.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
