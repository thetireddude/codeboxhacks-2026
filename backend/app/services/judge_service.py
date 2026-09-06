"""Gemini-backed post-round semantic judging for milestone A5."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.judgment import (
    JudgeInput,
    JudgeResult,
    JudgedPlayer,
    SemanticCategoryPoints,
)


logger = logging.getLogger(__name__)


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
                        # Live transcript IDs are UUID-length. The former 400
                        # token cap could truncate otherwise valid structured
                        # output that succeeded with the short fixture IDs.
                        "max_output_tokens": 2_048,
                        "temperature": 0.2,
                    },
                )
                if response.parsed is None:
                    raise ValueError(
                        "Gemini returned no parsed judgment"
                        f" (finish_reason={self._finish_reason(response)})."
                    )
                result = JudgeResult.model_validate(response.parsed)
                return self._sanitize_highlight_events(result, judge_input)
            except JudgeError:
                raise
            except Exception as error:
                last_error = error

        logger.error(
            "Gemini judging failed after %s attempt(s) using model %s.",
            self._max_attempts,
            self._model,
            exc_info=(type(last_error), last_error, last_error.__traceback__)
            if last_error is not None
            else None,
        )
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
    def _finish_reason(response: Any) -> str:
        """Return provider completion metadata without logging response content."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "unknown"
        reason = getattr(candidates[0], "finish_reason", None)
        return str(reason or "unknown")

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
                    "maxItems": 4,
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
    def _sanitize_highlight_events(
        result: JudgeResult, judge_input: JudgeInput
    ) -> JudgeResult:
        """Keep valid optional highlights without failing an otherwise usable score.

        Gemini's semantic player scores and coaching do not depend on highlight
        references. Live transcript IDs are generated UUID-like values, which a
        model can occasionally copy imperfectly. Rather than failing the entire
        round, omit only references that cannot be proven to belong to the
        authoritative transcript and drop a highlight that has none left.
        """
        known_ids = {event.id for event in judge_input.transcript_events}
        valid_highlights = []
        for event in result.highlight_events:
            event_ids = [
                event_id
                for event_id in event.transcript_event_ids
                if event_id in known_ids
            ]
            if not event_ids:
                logger.warning(
                    "Dropping Gemini highlight with no authoritative transcript IDs."
                )
                continue
            if len(event_ids) != len(event.transcript_event_ids):
                logger.warning(
                    "Removing unknown transcript IDs from a Gemini highlight."
                )
            valid_highlights.append(
                event.model_copy(update={"transcript_event_ids": event_ids})
            )
        return result.model_copy(update={"highlight_events": valid_highlights})


def create_judge_service(config: Any) -> JudgeService:
    """Build the configured A5 Gemini judge at the application boundary."""
    if _config_value(config, "TESTING", False):
        return TestJudgeService()
    return JudgeService(
        api_key=_config_value(config, "GEMINI_API_KEY"),
        model=_config_value(config, "GEMINI_JUDGE_MODEL"),
        max_attempts=_config_value(config, "GEMINI_JUDGE_MAX_ATTEMPTS"),
        timeout_ms=_config_value(config, "GEMINI_JUDGE_TIMEOUT_MS"),
    )


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    """Read either Flask's mapping config or the standalone script config class."""
    if hasattr(config, "get"):
        return getattr(config, "SOME_SETTING", None)
    return getattr(config, name, default)


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
