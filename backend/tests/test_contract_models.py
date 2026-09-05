import json
from pathlib import Path

from pydantic import TypeAdapter

from app.models import MatchResults, MatchState, Scenario, TranscriptEvent

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "shared" / "fixtures"


def _fixture(name: str):
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_shared_fixtures_match_backend_models():
    Scenario.model_validate(_fixture("mock-scenario.json"))
    MatchState.model_validate(_fixture("mock-match.json"))
    MatchResults.model_validate(_fixture("mock-results.json"))

    transcript_adapter = TypeAdapter(TranscriptEvent)
    for event in _fixture("mock-transcript.json"):
        transcript_adapter.validate_python(event)
