"""Gemini-backed scenario generation for AI milestone A1."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from random import choice
from typing import Any

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

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        max_attempts: int = 2,
        tone_pool: Sequence[Tone],
        prompt_template: str,
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
                return Scenario.model_validate(response.parsed)
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
        return self._prompt_template.format(tone=tone.value)

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
    """Build the configured A1 scenario service at the application boundary."""
    if config.get("TESTING") or not config["GEMINI_API_KEY"]:
        return MockScenarioService()
    return ScenarioService(
        api_key=config["GEMINI_API_KEY"],
        model=config["GEMINI_SCENARIO_MODEL"],
        max_attempts=config["GEMINI_SCENARIO_MAX_ATTEMPTS"],
        tone_pool=config["GEMINI_SCENARIO_TONES"],
        prompt_template=config["GEMINI_SCENARIO_PROMPT_TEMPLATE"],
    )
