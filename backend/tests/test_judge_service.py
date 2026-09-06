import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter

from app.models import JudgeInput, Scenario, TranscriptEvent
from app.services.judge_service import JudgeError, JudgeService, create_judge_service

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "shared" / "fixtures"

VALID_JUDGMENT = {
    "player_a": {
        "category_points": {
            "adaptability": 1900,
            "articulation": 1800,
            "coherence": 1700,
            "collaboration": 1600,
        },
        "highlight": "Turned the upside-down manual into a captain's ritual.",
        "improvement": "Invite the intern into the landing decision earlier.",
        "overview": "Used a confident recovery to keep the scene moving.",
    },
    "player_b": {
        "category_points": {
            "adaptability": 1600,
            "articulation": 1700,
            "coherence": 1600,
            "collaboration": 1600,
        },
        "highlight": "Used the upside-down manual to raise the stakes.",
        "improvement": "Commit to a specific landing plan sooner.",
        "overview": "Raised the stakes while leaving a clear opening for the partner.",
    },
    "highlight_events": [
        {
            "player_id": "A",
            "label": "GREAT RECOVERY",
            "points": 220,
            "transcript_event_ids": ["speech_003", "switch_001", "speech_004"],
        }
    ],
}


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if hasattr(outcome, "parsed"):
            return outcome
        return SimpleNamespace(parsed=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def _judge_input() -> JudgeInput:
    with (FIXTURE_DIR / "mock-scenario.json").open(encoding="utf-8") as handle:
        scenario = Scenario.model_validate(json.load(handle))
    with (FIXTURE_DIR / "mock-transcript.json").open(encoding="utf-8") as handle:
        raw_events = json.load(handle)
    adapter = TypeAdapter(TranscriptEvent)
    return JudgeInput(
        scenario=scenario,
        transcript_events=[adapter.validate_python(event) for event in raw_events],
        switch_response_latencies={"switch_001": 380},
        round_duration_ms=60_000,
    )


def _service(outcomes, *, max_attempts=1):
    return JudgeService(
        api_key="test-key",
        client=FakeClient(outcomes),
        max_attempts=max_attempts,
    )


def test_judges_fixture_transcript_with_structured_output():
    service = _service([VALID_JUDGMENT])

    result = service.judge(_judge_input())

    assert result.player_a.category_points.adaptability == 1900
    assert result.highlight_events[0].transcript_event_ids == [
        "speech_003",
        "switch_001",
        "speech_004",
    ]
    call = service._client.models.calls[0]
    assert call["model"] == "gemini-3.1-flash-lite"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["max_output_tokens"] == 2_048
    assert call["config"]["response_schema"]["properties"]["highlight_events"][
        "maxItems"
    ] == 4
    assert call["config"]["temperature"] == 0
    assert call["config"]["seed"] == 17
    assert "rejected_speech" in call["contents"]
    assert "switch_response_latencies_ms" in call["contents"]
    assert "public-speaking-v1" in call["contents"]
    assert "never infer pronunciation" in call["contents"]


def test_normalizes_scores_to_the_standard_hundred_point_steps():
    inconsistent = {
        **VALID_JUDGMENT,
        "player_a": {
            **VALID_JUDGMENT["player_a"],
            "category_points": {
                **VALID_JUDGMENT["player_a"]["category_points"],
                "articulation": 1750,
            },
        },
    }

    result = _service([inconsistent]).judge(_judge_input())

    assert result.player_a.category_points.articulation == 1800


def test_retries_when_gemini_returns_an_invalid_result():
    invalid = {"player_a": {}}
    service = _service([invalid, VALID_JUDGMENT], max_attempts=2)

    result = service.judge(_judge_input())

    assert result.player_b.highlight
    assert len(service._client.models.calls) == 2


def test_reports_safe_finish_reason_when_structured_output_is_not_parsed(caplog):
    response = SimpleNamespace(
        parsed=None,
        candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")],
    )
    service = _service([response])

    with pytest.raises(JudgeError):
        service.judge(_judge_input())

    assert "finish_reason=MAX_TOKENS" in caplog.text


def test_drops_a_highlight_that_references_an_unknown_event_without_failing_score():
    invalid = {
        **VALID_JUDGMENT,
        "highlight_events": [
            {
                **VALID_JUDGMENT["highlight_events"][0],
                "transcript_event_ids": ["speech_missing"],
            }
        ],
    }
    service = _service([invalid])

    result = service.judge(_judge_input())

    assert result.player_a.highlight
    assert result.highlight_events == []
    assert len(service._client.models.calls) == 1


def test_removes_only_unknown_ids_from_a_mixed_highlight_reference():
    partial = {
        **VALID_JUDGMENT,
        "highlight_events": [
            {
                **VALID_JUDGMENT["highlight_events"][0],
                "transcript_event_ids": ["speech_003", "speech_missing"],
            }
        ],
    }

    result = _service([partial]).judge(_judge_input())

    assert result.highlight_events[0].transcript_event_ids == ["speech_003"]


def test_drops_a_highlight_with_an_empty_reference_list():
    empty = {
        **VALID_JUDGMENT,
        "highlight_events": [
            {**VALID_JUDGMENT["highlight_events"][0], "transcript_event_ids": []}
        ],
    }

    result = _service([empty]).judge(_judge_input())

    assert result.highlight_events == []


def test_reports_a_missing_api_key_without_calling_gemini():
    service = JudgeService(api_key="", client=FakeClient([VALID_JUDGMENT]))

    with pytest.raises(JudgeError, match="GEMINI_API_KEY is not configured"):
        service.judge(_judge_input())

    assert service._client.models.calls == []


def test_factory_accepts_the_script_configuration_class():
    class ScriptConfig:
        TESTING = False
        GEMINI_API_KEY = "test-key"
        GEMINI_JUDGE_MODEL = "gemini-test-model"
        GEMINI_JUDGE_MAX_ATTEMPTS = 1
        GEMINI_JUDGE_TIMEOUT_MS = 12_000

    service = create_judge_service(ScriptConfig)

    assert isinstance(service, JudgeService)
    assert service._model == "gemini-test-model"
