from types import SimpleNamespace

import pytest

from app.models import Tone
from app.services.scenario_service import ScenarioGenerationError, ScenarioService

VALID_SCENARIO = {
    "tone": "wacky",
    "scenario": "Two astronauts discover that neither knows how to land the spaceship.",
    "player_a_role": "Overconfident captain",
    "player_b_role": "Intern pretending to know what they are doing",
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
        return SimpleNamespace(parsed=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def _service(outcomes, *, role_blacklist=()):
    return ScenarioService(
        api_key="test-key",
        client=FakeClient(outcomes),
        tone_pool=(Tone.WACKY,),
        prompt_template="Create an improv scene in a {tone} tone.",
        role_blacklist=role_blacklist,
        tone_selector=lambda _: Tone.WACKY,
    )


def test_generates_a_valid_scenario_with_structured_output():
    service = _service([VALID_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.tone is Tone.WACKY
    assert scenario.player_a_role == VALID_SCENARIO["player_a_role"]
    call = service._client.models.calls[0]
    assert call["model"] == "gemini-3.1-flash-lite"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_schema"]["properties"]["tone"]["enum"] == ["wacky"]
    assert "wacky tone" in call["contents"]


def test_retries_once_after_an_invalid_response():
    invalid_scenario = {"tone": "wacky", "scenario": "Incomplete"}
    service = _service([invalid_scenario, VALID_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.scenario == VALID_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 2


def test_retries_when_gemini_returns_an_overused_premise():
    overused_scenario = {
        "tone": "wacky",
        "scenario": "Two guests realize they brought the exact same potato salad.",
        "player_a_role": "Potluck guest",
        "player_b_role": "Another potluck guest",
    }
    service = _service([overused_scenario, VALID_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.scenario == VALID_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 2


def test_raises_a_clear_error_after_two_failed_attempts():
    service = _service(
        [RuntimeError("temporary outage"), RuntimeError("temporary outage")]
    )

    with pytest.raises(
        ScenarioGenerationError,
        match="Scenario generation failed after 2 attempts",
    ):
        service.generate_scenario()

    assert len(service._client.models.calls) == 2


def test_reports_a_missing_api_key_without_calling_gemini():
    service = ScenarioService(
        api_key="",
        client=FakeClient([VALID_SCENARIO]),
        tone_pool=(Tone.WACKY,),
        prompt_template="Create an improv scene in a {tone} tone.",
    )

    with pytest.raises(
        ScenarioGenerationError, match="GEMINI_API_KEY is not configured"
    ):
        service.generate_scenario()


def test_retries_when_a_role_contains_a_blacklisted_word():
    blacklisted = {**VALID_SCENARIO, "player_b_role": "Silent mime"}
    service = _service([blacklisted, VALID_SCENARIO], role_blacklist=("mime", "mute"))

    scenario = service.generate_scenario()

    assert scenario.player_b_role == VALID_SCENARIO["player_b_role"]
    assert len(service._client.models.calls) == 2
