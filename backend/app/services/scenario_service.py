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

    # These premise shapes appeared repeatedly in live generations. They are
    # deliberately rejected after structured parsing so a retry can produce a
    # materially different playable starting point instead.
    _OVERUSED_PATTERNS = (
        re.compile(r"\b(?:the\s+)?(?:exact\s+)?same\b", re.IGNORECASE),
        re.compile(r"\b(?:identical|matching|duplicate)\b", re.IGNORECASE),
        re.compile(r"\b(?:estranged|long-lost)\b", re.IGNORECASE),
        re.compile(r"\b(?:sibling|siblings|brother|sister)\b", re.IGNORECASE),
        re.compile(r"\bpack(?:ing|ed)?\s+up\b", re.IGNORECASE),
        re.compile(r"\bmoving\s+(?:out|away)\b", re.IGNORECASE),
    )

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        max_attempts: int = 2,
        tone_pool: Sequence[Tone],
        prompt_template: str,
        role_blacklist: Sequence[str] = (),
        client: Any | None = None,
        tone_selector: Callable[[Sequence[Tone]], Tone] = choice,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not tone_pool:
            raise ValueError("tone_pool must contain at least one tone")
        if "{tone}" not in prompt_template:
            raise ValueError("prompt_template must include a {tone} placeholder")

        self._api_key = api_key
        self._model = model
        self._max_attempts = max_attempts
        self._tone_pool = tuple(tone_pool)
        self._prompt_template = prompt_template
        self._role_blacklist = tuple(word.lower() for word in role_blacklist)
        self._client = client
        self._tone_selector = tone_selector

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
        prompt = self._build_prompt(tone)
        last_error: Exception | None = None

        for _ in range(self._max_attempts):
            try:
                response = self._get_client().models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": self._response_schema(),
                    },
                )
                scenario = Scenario.model_validate(response.parsed)
                self._reject_overused_premise(scenario)
                self._validate_roles(scenario)
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

    def _build_prompt(self, tone: Tone) -> str:
        return self._prompt_template.format(
            tone=tone.value,
            random_words=get_random_words(),
        )

    @classmethod
    def _reject_overused_premise(cls, scenario: Scenario) -> None:
        text = " ".join(
            (scenario.scenario, scenario.player_a_role, scenario.player_b_role)
        )
        if any(pattern.search(text) for pattern in cls._OVERUSED_PATTERNS):
            raise ValueError("Scenario matches an overused premise pattern")

    def _validate_roles(self, scenario: Scenario) -> None:
        """Reject a generated role that violates the deployment blacklist."""
        roles = (scenario.player_a_role, scenario.player_b_role)
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
        model=_config_value(config, "GEMINI_SCENARIO_MODEL", "gemini-3.1-flash-lite"),
        max_attempts=_config_value(config, "GEMINI_SCENARIO_MAX_ATTEMPTS", 2),
        tone_pool=_config_value(config, "GEMINI_SCENARIO_TONES", ()),
        prompt_template=_config_value(config, "GEMINI_SCENARIO_PROMPT_TEMPLATE", ""),
        role_blacklist=_config_value(config, "SCENARIO_ROLE_BLACKLIST", ()),
    )


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    """Read either Flask's mapping config or the standalone script config class."""
    if hasattr(config, "get"):
        return config.get(name, default)
    return getattr(config, name, default)
