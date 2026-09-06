from types import SimpleNamespace

import pytest

from app.models import Scenario, Tone
from app.services.scenario_service import ScenarioGenerationError, ScenarioService

VALID_SCENARIO = {
    "tone": "wacky",
    "scenario": "At the launch bay, two astronauts realize neither knows how to land the spaceship.",
    "player_a_role": "Overconfident captain",
    "player_b_role": "Intern pretending to know what they are doing",
}

RETRY_SCENARIO = {
    **VALID_SCENARIO,
    "scenario": "When the launch manual falls open, two astronauts disagree about which page matters.",
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
        if hasattr(outcome, "function_calls"):
            return outcome
        return SimpleNamespace(parsed=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def _service(outcomes, *, role_blacklist=()):
    return ScenarioService(
        api_key="test-key",
        model="gemini-3.1-flash-lite",
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
    assert "different immediate relationships" in call["contents"]
    assert "ASYMMETRIC SUBJECT generation" in call["contents"]


def test_gemma_uses_a_forced_function_call_for_structured_output():
    service = ScenarioService(
        api_key="test-key",
        model="gemma-4-26b-a4b-it",
        client=FakeClient([]),
        tone_pool=(Tone.WACKY,),
        prompt_template="Create an improv scene in a {tone} tone.",
        tone_selector=lambda _: Tone.WACKY,
    )
    service._client.models.outcomes.append(
        SimpleNamespace(
            function_calls=[SimpleNamespace(name="submit_scenario", args=VALID_SCENARIO)]
        )
    )

    scenario = service.generate_scenario()

    assert scenario.scenario == VALID_SCENARIO["scenario"]
    call = service._client.models.calls[0]
    assert call["model"] == "gemma-4-26b-a4b-it"
    assert call["config"]["tool_config"]["function_calling_config"]["mode"] == "ANY"


def test_retries_once_after_an_invalid_response():
    invalid_scenario = {"tone": "wacky", "scenario": "Incomplete"}
    service = _service([invalid_scenario, RETRY_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.scenario == RETRY_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 2


def test_retries_when_players_are_only_teaching_a_third_party():
    third_party_scene = {
        "tone": "wacky",
        "scenario": "Two people are trying to teach a turtle how to use a ticket machine.",
        "player_a_role": "Transit worker",
        "player_b_role": "Commuter",
    }
    service = _service([third_party_scene, RETRY_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.scenario == RETRY_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 2


def test_rejects_the_collective_object_is_alive_or_food_premise_family():
    service = _service([VALID_SCENARIO])

    with pytest.raises(ValueError, match="collective misidentification"):
        service._reject_repetitive_structure(
            Scenario(
                tone="wacky",
                scenario="Two people are convinced that a stapler is actually alive.",
                player_a_role="Store employee",
                player_b_role="Delivery recipient",
            )
        )


def test_alternates_asymmetric_and_collective_subject_generations():
    first_collective = {
        **VALID_SCENARIO,
        "scenario": "Two people are unpacking a delivery in a quiet office.",
    }
    second_asymmetric = {
        **VALID_SCENARIO,
        "scenario": "When the train arrives, a conductor waits while a traveler studies an expired ticket.",
    }
    second_collective = {
        **VALID_SCENARIO,
        "scenario": "Two people repair a display before the shop opens.",
    }
    service = _service([VALID_SCENARIO, first_collective, second_asymmetric, second_collective])

    scenarios = [service.generate_scenario().scenario for _ in range(4)]

    assert scenarios == [
        VALID_SCENARIO["scenario"],
        first_collective["scenario"],
        second_asymmetric["scenario"],
        second_collective["scenario"],
    ]
    prompts = [call["contents"] for call in service._client.models.calls]
    assert "ASYMMETRIC SUBJECT generation" in prompts[0]
    assert "COLLECTIVE SUBJECT generation" in prompts[1]
    assert "ASYMMETRIC SUBJECT generation" in prompts[2]
    assert "COLLECTIVE SUBJECT generation" in prompts[3]


def test_asymmetric_slot_retries_a_generic_pair_subject():
    generic_pair = {
        **VALID_SCENARIO,
        "scenario": "At the ticket booth, two people wait beside a broken turnstile.",
    }
    service = _service([generic_pair, RETRY_SCENARIO])

    assert service.generate_scenario().scenario == RETRY_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 2


def test_retry_prompt_uses_a_different_required_opening_frame():
    service = _service([{"tone": "wacky", "scenario": "Incomplete"}, RETRY_SCENARIO])

    service.generate_scenario()

    first_prompt = service._client.models.calls[0]["contents"]
    second_prompt = service._client.models.calls[1]["contents"]
    assert "REQUIRED OPENING FRAME" in first_prompt
    assert first_prompt != second_prompt


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
    service = _service([blacklisted, RETRY_SCENARIO], role_blacklist=("mime", "mute"))

    scenario = service.generate_scenario()

    assert scenario.player_b_role == RETRY_SCENARIO["player_b_role"]
    assert len(service._client.models.calls) == 2


def test_quality_gate_retries_a_low_coherence_or_uniqueness_candidate():
    incoherent = {
        **VALID_SCENARIO,
        "scenario": "At the post office, an accountant and a sentient umbrella mail one envelope.",
    }
    service = ScenarioService(
        api_key="test-key",
        model="gemini-3.1-flash-lite",
        client=FakeClient([
            incoherent,
            {"coherence_score": 3, "uniqueness_score": 4},
            RETRY_SCENARIO,
            {"coherence_score": 9, "uniqueness_score": 9},
        ]),
        tone_pool=(Tone.WACKY,),
        prompt_template="Create an improv scene in a {tone} tone.",
        quality_check_enabled=True,
        tone_selector=lambda _: Tone.WACKY,
    )

    scenario = service.generate_scenario()

    assert scenario.scenario == RETRY_SCENARIO["scenario"]
    assert len(service._client.models.calls) == 4
    assert "Uniqueness is judged independently" in service._client.models.calls[1]["contents"]


def test_retries_when_the_player_roles_are_interchangeable():
    duplicate_roles = {
        **VALID_SCENARIO,
        "player_a_role": "Museum guest",
        "player_b_role": "Museum guest",
    }
    service = _service([duplicate_roles, RETRY_SCENARIO])

    scenario = service.generate_scenario()

    assert scenario.player_a_role == RETRY_SCENARIO["player_a_role"]
    assert len(service._client.models.calls) == 2
