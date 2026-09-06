"""Gemini-backed scenario generation for AI milestone A1."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from random import choice
import re
from typing import Any

from app.config import get_random_words
from app.models import Scenario, Tone


class ScenarioGenerationError(RuntimeError):
    """Raised when a playable scenario cannot be generated."""


class MockScenarioService:
    """Development provider used until Gemini credentials are configured."""

    scenario = Scenario(
        tone="wacky",
        scenario=(
            "Two astronauts discover that neither knows how to land the spaceship."
        ),
        player_a_role="Overconfident captain",
        player_b_role="Intern pretending to know what they are doing",
    )

    def generate_scenario(self) -> Scenario:
        return self.scenario


class ScenarioService:
    """Generate one validated improv scenario with Gemini."""

    _SCENE_FRAMES = (
        ("location", ("at ", "inside ", "outside ", "near "), "Start with a location phrase followed by a comma."),
        ("time", ("when ", "after ", "before ", "while "), "Start with a time clause followed by a comma."),
        ("occasion", ("during ",), "Start with 'During ...,' to establish an occasion already in progress."),
        ("player-action", ("one player",), "Start with 'One player ...' and immediately involve the other player."),
        ("object", ("the ",), "Start with 'The ...' and let a concrete object or rule create the present interaction."),
        ("arrival", ("a ", "an "), "Start with 'A ...' or 'An ...' and make that concrete thing affect both players now."),
        ("spatial", ("on ", "under ", "beside ", "behind "), "Start with a spatial phrase followed by a comma."),
        ("simultaneous", ("as ",), "Start with 'As ...,' so both players are pulled into the same immediate moment."),
        ("collective", ("two ",), "Start directly with 'Two ...' for this one deliberately collective scene frame."),
    )

    _THIRD_PARTY_TASK_PATTERN = re.compile(
        r"\b(?:teach(?:ing)?|train(?:ing)?|coach(?:ing)?|babysit(?:ting)?|supervis(?:e|ing)|care\s+for|entertain(?:ing)?)\s+(?:an?|the)\s+\w+",
        re.IGNORECASE,
    )
    _GENERIC_PAIR_SUBJECT_PATTERN = re.compile(
        r"\b(?:two|both)\s+(?:people|persons|strangers|friends|guests|coworkers?)\b",
        re.IGNORECASE,
    )
    _GENERIC_MISIDENTIFICATION_PATTERN = re.compile(
        r"\btwo\s+people\s+(?:(?:are|become)\s+)?"
        r"(?:convinced|believe|insist)(?:\s+that)?\b.{0,120}?\b"
        r"(?:is|are)\s+(?:actually\s+)?(?:alive|living|sentient|food|edible)\b",
        re.IGNORECASE,
    )
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemma-4-26b-a4b-it",
        max_attempts: int = 2,
        tone_pool: Sequence[Tone],
        prompt_template: str,
        role_blacklist: Sequence[str] = (),
        quality_check_enabled: bool = False,
        min_coherence_score: int = 7,
        min_uniqueness_score: int = 8,
        client: Any | None = None,
        tone_selector: Callable[[Sequence[Tone]], Tone] = choice,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not tone_pool:
            raise ValueError("tone_pool must contain at least one tone")
        if "{tone}" not in prompt_template:
            raise ValueError("prompt_template must include a {tone} placeholder")
        if not 1 <= min_coherence_score <= 10:
            raise ValueError("min_coherence_score must be between 1 and 10")
        if not 1 <= min_uniqueness_score <= 10:
            raise ValueError("min_uniqueness_score must be between 1 and 10")

        self._api_key = api_key
        self._model = model
        self._max_attempts = max_attempts
        self._tone_pool = tuple(tone_pool)
        self._prompt_template = prompt_template
        self._role_blacklist = tuple(word.lower() for word in role_blacklist)
        self._quality_check_enabled = quality_check_enabled
        self._min_coherence_score = min_coherence_score
        self._min_uniqueness_score = min_uniqueness_score
        self._client = client
        self._tone_selector = tone_selector
        self._generation_index = 0

    def generate_scenario(self) -> Scenario:
        """Return a playable scenario or raise a clear generation error.

        The selected tone is system-owned. Callers cannot select it during the
        MVP because the product spec requires the app to randomize tones.
        """
        if not self._api_key:
            raise ScenarioGenerationError(
                "Scenario generation is unavailable: GEMINI_API_KEY is not configured."
            )

        tone = self._tone_selector(self._tone_pool)
        generation_index = self._generation_index
        self._generation_index += 1
        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                asymmetric_slot = generation_index % 2 == 0
                frame = self._scene_frame(generation_index, attempt, asymmetric_slot)
                prompt = self._build_prompt(tone, frame, asymmetric_slot)
                candidate = self._generate_structured(
                    prompt,
                    self._response_schema(),
                    "submit_scenario",
                )
                scenario = Scenario.model_validate(candidate)
                self._validate_opening_frame(scenario, frame, asymmetric_slot)
                self._reject_repetitive_structure(scenario)
                self._validate_roles(scenario)
                self._validate_quality(scenario, asymmetric_slot)
                return scenario
            except ScenarioGenerationError:
                raise
            except Exception as error:
                last_error = error

        raise ScenarioGenerationError(
            f"Scenario generation failed after {self._max_attempts} attempts."
        ) from last_error

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as error:
                raise ScenarioGenerationError(
                    "Scenario generation is unavailable: install the "
                    "google-genai package."
                ) from error
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _generate_structured(
        self, prompt: str, schema: dict[str, Any], function_name: str
    ) -> Any:
        """Use native schemas for Gemini and a forced function call for Gemma."""
        if self._model.startswith("gemma-"):
            response = self._get_client().models.generate_content(
                model=self._model,
                contents=f"{prompt}\nCall {function_name} exactly once with the completed result.",
                config={
                    "tools": [{
                        "function_declarations": [{
                            "name": function_name,
                            "description": "Submit the validated structured result.",
                            "parameters": schema,
                        }]
                    }],
                    "tool_config": {
                        "function_calling_config": {
                            "mode": "ANY",
                            "allowed_function_names": [function_name],
                        }
                    },
                },
            )
            function_calls = getattr(response, "function_calls", None) or ()
            if len(function_calls) != 1 or function_calls[0].name != function_name:
                raise ValueError(f"Gemma did not call {function_name} exactly once")
            return dict(function_calls[0].args)

        response = self._get_client().models.generate_content(
            model=self._model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        return response.parsed

    def _build_prompt(
        self,
        tone: Tone,
        frame: tuple[str, tuple[str, ...], str],
        asymmetric_slot: bool,
    ) -> str:
        prompt = self._prompt_template.format(
            tone=tone.value,
            random_words=get_random_words(),
        )
        _frame_name, _prefixes, instruction = frame
        structure_contract = (
            "- This is an ASYMMETRIC SUBJECT generation. Name two specific kinds of people in the scenario itself, "
            "each occupying a different role, place, responsibility, or relationship to the setting. Do not call "
            "them collectively 'two people', 'both people', or another generic pair. They may simply be present in "
            "the same setting; they do not need to be interacting yet, arguing, or pursuing the same task."
            if asymmetric_slot
            else "- This is a COLLECTIVE SUBJECT generation. Begin with 'Two people ...'. A shared action or situation is allowed, but the two role fields must still give the performers distinct positions."
        )
        return "\n".join(
            (
                prompt,
                "",
                "TWO-PLAYER CONTRACT:",
                "- Only Player A and Player B may be active characters. Both must be able to speak, decide, and affect the scene.",
                "- Do not make both players teach, train, coach, babysit, supervise, entertain, rescue, or care for a third character, animal, or creature.",
                "- Give the players different immediate relationships to the situation: one may know, control, need, deliver, inspect, request, or be responsible for something the other must answer, use, question, or change.",
                "- Their roles must describe distinct practical positions, not two interchangeable friends, guests, coworkers, customers, or people with different personality adjectives.",
                "- Establish a concrete setting, activity, request, discovery, decision, or handoff. The premise may begin before the players directly interact, provided both have a clear playable position in the setting.",
                "- Cooperation is valid; the asymmetry should create playable back-and-forth, not automatically make the players enemies.",
                structure_contract,
                "",
                "THIS ATTEMPT'S REQUIRED OPENING FRAME:",
                f"- {instruction}",
                "- The scenario must use that exact opening form; do not mention these instructions in the JSON.",
            )
        )

    def _scene_frame(
        self, generation_index: int, attempt: int, asymmetric_slot: bool
    ) -> tuple[str, tuple[str, ...], str]:
        if not asymmetric_slot:
            return self._SCENE_FRAMES[-1]
        asymmetric_frames = self._SCENE_FRAMES[:-1]
        return asymmetric_frames[(generation_index // 2 + attempt) % len(asymmetric_frames)]

    @staticmethod
    def _validate_opening_frame(
        scenario: Scenario,
        frame: tuple[str, tuple[str, ...], str],
        asymmetric_slot: bool,
    ) -> None:
        frame_name, prefixes, _instruction = frame
        opening = scenario.scenario.strip().lower()
        if not opening.startswith(prefixes):
            raise ValueError("Scenario did not follow this attempt's required opening frame")
        uses_generic_pair = ScenarioService._GENERIC_PAIR_SUBJECT_PATTERN.search(opening)
        if asymmetric_slot and uses_generic_pair:
            raise ValueError("Asymmetric scenario used a generic pair subject")
        if not asymmetric_slot and frame_name == "collective" and not uses_generic_pair:
            raise ValueError("Collective scenario did not use its required pair subject")

    def _reject_repetitive_structure(self, scenario: Scenario) -> None:
        text = scenario.scenario.strip()
        if self._GENERIC_MISIDENTIFICATION_PATTERN.search(text):
            raise ValueError("Scenario uses the overused collective misidentification premise")
        if self._THIRD_PARTY_TASK_PATTERN.search(text):
            raise ValueError("Scenario makes the players manage a third inactive character")

    def _validate_quality(self, scenario: Scenario, asymmetric_slot: bool) -> None:
        """Use Gemini as a compact semantic gate after local contract checks."""
        if not self._quality_check_enabled:
            return
        quality = self._generate_structured(
            self._quality_prompt(scenario, asymmetric_slot),
            {
                "type": "OBJECT",
                "properties": {
                    "coherence_score": {"type": "INTEGER", "minimum": 1, "maximum": 10},
                    "uniqueness_score": {"type": "INTEGER", "minimum": 1, "maximum": 10},
                },
                "required": ["coherence_score", "uniqueness_score"],
            },
            "submit_scenario_quality",
        )
        if not isinstance(quality, dict):
            raise ValueError("Scenario quality response was not an object")
        coherence = quality.get("coherence_score")
        uniqueness = quality.get("uniqueness_score")
        if not isinstance(coherence, int) or not isinstance(uniqueness, int):
            raise ValueError("Scenario quality response did not contain integer scores")
        if coherence < self._min_coherence_score:
            raise ValueError("Scenario coherence score was below the minimum")
        if uniqueness < self._min_uniqueness_score:
            raise ValueError("Scenario uniqueness score was below the minimum")

    def _quality_prompt(self, scenario: Scenario, asymmetric_slot: bool) -> str:
        assigned_structure = "asymmetric specific subjects" if asymmetric_slot else "collective subject"
        return "\n".join(
            (
                "Evaluate this two-player improv scene candidate. Return JSON only.",
                "Coherence means the roles, place, action, and reason for interaction fit together without arbitrary or nonsensical combinations.",
                "Uniqueness is judged independently, not against any history. Score 8 or higher only when the candidate has a specific, coherent relationship and a distinctive sentence frame.",
                f"This candidate was deliberately assigned the {assigned_structure} structure. Do not lower uniqueness merely for following that assigned subject structure.",
                "Score uniqueness 1 through 4 if the content is only a generic noun swap or gives the performers no distinct playable positions.",
                "Do not give high uniqueness solely because an ordinary noun was swapped for a strange noun. A strange noun that does not naturally fit the situation lowers coherence.",
                f"Candidate scenario: {scenario.scenario}",
                f"Player A role: {scenario.player_a_role}",
                f"Player B role: {scenario.player_b_role}",
            )
        )

    def _validate_roles(self, scenario: Scenario) -> None:
        """Reject a generated role that violates the deployment blacklist."""
        roles = (scenario.player_a_role, scenario.player_b_role)
        normalized_roles = tuple(re.sub(r"\s+", " ", role.strip().lower()) for role in roles)
        if normalized_roles[0] == normalized_roles[1]:
            raise ValueError("Scenario roles must give the two players distinct positions")
        if any(role.startswith("another ") for role in normalized_roles):
            raise ValueError("Scenario roles must not make one player a duplicate of the other")
        for word in self._role_blacklist:
            pattern = rf"(?<!\w){re.escape(word)}(?!\w)"
            if any(re.search(pattern, role, flags=re.IGNORECASE) for role in roles):
                raise ValueError(
                    "Scenario generation returned a blacklisted role; retrying."
                )

    def _response_schema(self) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "tone": {
                    "type": "STRING",
                    "enum": [tone.value for tone in self._tone_pool],
                },
                "scenario": {"type": "STRING"},
                "player_a_role": {"type": "STRING"},
                "player_b_role": {"type": "STRING"},
            },
            "required": ["tone", "scenario", "player_a_role", "player_b_role"],
        }


def create_scenario_service(config: Any) -> ScenarioService | MockScenarioService:
    """Build Gemini generation in production and deterministic generation in tests."""

    if _config_value(config, "TESTING", False):
        return MockScenarioService()

    return ScenarioService(
        api_key=_config_value(config, "GEMINI_API_KEY", ""),
        model=_config_value(config, "GEMINI_SCENARIO_MODEL", "gemma-4-26b-a4b-it"),
        max_attempts=_config_value(config, "GEMINI_SCENARIO_MAX_ATTEMPTS", 2),
        tone_pool=_config_value(config, "GEMINI_SCENARIO_TONES", ()),
        prompt_template=_config_value(config, "GEMINI_SCENARIO_PROMPT_TEMPLATE", ""),
        role_blacklist=_config_value(config, "SCENARIO_ROLE_BLACKLIST", ()),
        quality_check_enabled=_config_value(config, "SCENARIO_QUALITY_CHECK_ENABLED", True),
        min_coherence_score=_config_value(config, "SCENARIO_MIN_COHERENCE_SCORE", 7),
        min_uniqueness_score=_config_value(config, "SCENARIO_MIN_UNIQUENESS_SCORE", 8),
    )


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    """Read either Flask's mapping config or the standalone script config class."""
    if hasattr(config, "get"):
        return config.get(name, default)
    return getattr(config, name, default)
