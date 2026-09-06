"""Print a Gemini judgment for the shared completed-round fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from app.config import AppConfig
from app.models import JudgeInput, Scenario, TranscriptEvent
from app.services.judge_service import JudgeError, create_judge_service

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "shared" / "fixtures"


def _load_input() -> JudgeInput:
    with (FIXTURE_DIR / "mock-scenario.json").open(encoding="utf-8") as handle:
        scenario = Scenario.model_validate(json.load(handle))
    with (FIXTURE_DIR / "mock-transcript.json").open(encoding="utf-8") as handle:
        raw_events = json.load(handle)
    transcript_adapter = TypeAdapter(TranscriptEvent)
    return JudgeInput(
        scenario=scenario,
        transcript_events=[
            transcript_adapter.validate_python(event) for event in raw_events
        ],
        # Fixture timing is illustrative only; A6 will calculate this authoritatively.
        switch_response_latencies={"switch_001": 380},
        round_duration_ms=60_000,
    )


def main() -> int:
    try:
        result = create_judge_service(AppConfig).judge(_load_input())
    except JudgeError as error:
        print(f"Judging failed: {error}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
