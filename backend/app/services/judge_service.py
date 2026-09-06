"""Gemini-backed post-round semantic judging for milestone A5."""

from __future__ import annotations

import json
from typing import Any

from app.models.judgment import (
    JudgeInput,
    JudgeResult,
    JudgedPlayer,
    SemanticCategoryPoints,
)


class JudgeError(RuntimeError):
    """Raised when a completed scene cannot be judged safely."""


class JudgeService:
    """Submit one completed round to Gemini and validate its structured response."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        max_attempts: int = 1,
        timeout_ms: int = 12_000,
        client: Any | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_ms < 1:
            raise ValueError("timeout_ms must be at least 1")
        self._api_key = api_key
        self._model = model
        self._max_attempts = max_attempts
        self._timeout_ms = timeout_ms
        self._client = client

    def judge(self, judge_input: JudgeInput) -> JudgeResult:
        """Return one validated semantic judgment for a completed round."""
        if not self._api_key:
            raise JudgeError(
                "Judging is unavailable: GEMINI_API_KEY is not configured."
            )

        last_error: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                response = self._get_client().models.generate_content(
                    model=self._model,
                    contents=self._build_prompt(judge_input),
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": self._response_schema(),
                        "max_output_tokens": 400,
                        "temperature": 0.2,
                    },
                )
                result = JudgeResult.model_validate(response.parsed)
                self._validate_event_references(result, judge_input)
                return result
            except JudgeError:
                raise
            except Exception as error:
                last_error = error

        raise JudgeError(
            f"Judging failed after {self._max_attempts} attempts."
        ) from last_error

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as error:
                raise JudgeError(
                    "Judging is unavailable: install the google-genai package."
                ) from error
            self._client = genai.Client(
                api_key=self._api_key,
                http_options={
                    "timeout": self._timeout_ms,
                    # The SDK otherwise applies up to five retries, which can
                    # make a single UI submission look indefinitely stuck.
                    "retry_options": {"attempts": 1},
                },
            )
        return self._client

    @staticmethod
    def _build_prompt(judge_input: JudgeInput) -> str:
        scenario = judge_input.scenario
        accepted = [
            event.model_dump(mode="json")
            for event in judge_input.transcript_events
            if event.type == "speech" and event.accepted
        ]
        rejected = [
            event.model_dump(mode="json")
            for event in judge_input.transcript_events
            if event.type == "speech" and not event.accepted
        ]
        switches = [
            event.model_dump(mode="json")
            for event in judge_input.transcript_events
            if event.type == "switch"
        ]
        payload = {
            "scenario": scenario.model_dump(mode="json"),
            "accepted_speech": accepted,
            "rejected_speech": rejected,
            "switch_events": switches,
            "switch_response_latencies_ms": judge_input.switch_response_latencies,
            "round_duration_ms": judge_input.round_duration_ms,
        }
        return (
            "You are an encouraging but exacting improv coach judging a completed "
            "two-player scene. Player A is the first role and Player B is the "
            "second role. Score each player independently in arcade points from "
            "0 to 2000 for adaptability, creativity, coherence, and collaboration. "
            "Judge rejected speech only as evidence of Switch recovery; it is not "
            "scene canon. Do not score speed and do not infer timing quality from "
            "text; latency data is supplied only to explain Switch context. "
            "Give each player a specific strongest moment and one concrete, "
            "actionable improvement. Highlight events must cite one or more real "
            "transcript event IDs and use a concise arcade-style label. Never "
            "invent events, roles, or dialogue.\n\n"
            f"Round data:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        player = {
            "type": "OBJECT",
            "properties": {
                "category_points": {
                    "type": "OBJECT",
                    "properties": {
                        name: {"type": "INTEGER", "minimum": 0, "maximum": 2000}
                        for name in (
                            "adaptability",
                            "creativity",
                            "coherence",
                            "collaboration",
                        )
                    },
                    "required": [
                        "adaptability",
                        "creativity",
                        "coherence",
                        "collaboration",
                    ],
                },
                "highlight": {"type": "STRING"},
                "improvement": {"type": "STRING"},
            },
            "required": ["category_points", "highlight", "improvement"],
        }
        return {
            "type": "OBJECT",
            "properties": {
                "player_a": player,
                "player_b": player,
                "highlight_events": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "player_id": {"type": "STRING", "enum": ["A", "B"]},
                            "label": {"type": "STRING"},
                            "points": {"type": "INTEGER", "minimum": 0, "maximum": 500},
                            "transcript_event_ids": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            },
                        },
                        "required": [
                            "player_id",
                            "label",
                            "points",
                            "transcript_event_ids",
                        ],
                    },
                },
            },
            "required": ["player_a", "player_b", "highlight_events"],
        }

    @staticmethod
    def _validate_event_references(
        result: JudgeResult, judge_input: JudgeInput
    ) -> None:
        known_ids = {event.id for event in judge_input.transcript_events}
        for event in result.highlight_events:
            unknown_ids = set(event.transcript_event_ids) - known_ids
            if unknown_ids:
                unknown = ", ".join(sorted(unknown_ids))
                raise ValueError(
                    f"Highlight references unknown transcript event(s): {unknown}"
                )


def create_judge_service(config: Any) -> JudgeService:
    """Build the configured A5 Gemini judge at the application boundary."""
    if config.get("TESTING"):
        return TestJudgeService()
    return JudgeService(
        api_key=config["GEMINI_API_KEY"],
        model=config["GEMINI_JUDGE_MODEL"],
        max_attempts=config["GEMINI_JUDGE_MAX_ATTEMPTS"],
        timeout_ms=config["GEMINI_JUDGE_TIMEOUT_MS"],
    )


class TestJudgeService:
    """Deterministic semantic result used only by the application test configuration."""

    def judge(self, _judge_input: JudgeInput) -> JudgeResult:
        points = SemanticCategoryPoints(
            adaptability=0, creativity=0, coherence=0, collaboration=0
        )
        player = JudgedPlayer(
            category_points=points,
            highlight="Round complete.",
            improvement="Keep building together.",
        )
        return JudgeResult(player_a=player, player_b=player)
