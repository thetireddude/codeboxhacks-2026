"""Standalone mockup judging endpoint for the A5/A6 demo flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from pydantic import TypeAdapter, ValidationError

from app.models import JudgeInput, ScoringInput, TranscriptEvent
from app.services.game_service import GameService
from app.services.judge_service import JudgeError, JudgeService
from app.services.scoring_service import ScoringService

scoring_blueprint = Blueprint("scoring", __name__, url_prefix="/api/mockup")


@scoring_blueprint.get("/round-prepare")
def mock_round_prepare():
    """Expose the same scenario shape sent by the live `round:prepare` event."""
    starts_at = datetime.now(UTC) + timedelta(seconds=3)
    return jsonify(
        {
            "match_id": "mock-i3-scenario-match",
            "scenario": GameService.MOCK_SCENARIO.model_dump(mode="json"),
            "starts_at": starts_at.isoformat(),
        }
    )


@scoring_blueprint.post("/judge")
def judge_mockup_transcript():
    """Judge the standalone mic-check page's final transcript."""
    judge_service: JudgeService = current_app.extensions["judge_service"]
    scoring_service: ScoringService = current_app.extensions["scoring_service"]
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("INVALID_PAYLOAD", "Body must be a JSON object", 400)
    try:
        raw_events = payload["transcript_events"]
        if not isinstance(raw_events, list):
            raise ValueError("transcript_events must be an array")
        transcript_adapter = TypeAdapter(TranscriptEvent)
        events = [transcript_adapter.validate_python(event) for event in raw_events]
        if not any(event.type == "speech" and event.accepted for event in events):
            raise ValueError("At least one final accepted speech line is required")
        round_duration_ms = payload.get("round_duration_ms", 60_000)
        latencies = ScoringService.calculate_switch_response_latencies(events)
        judgment = judge_service.judge(
            JudgeInput(
                scenario=GameService.MOCK_SCENARIO,
                transcript_events=events,
                switch_response_latencies=latencies,
                round_duration_ms=round_duration_ms,
            )
        )
        results = scoring_service.score(
            ScoringInput(
                match_id=uuid4(),
                judgment=judgment,
                transcript_events=events,
                round_duration_ms=round_duration_ms,
            )
        )
    except (KeyError, TypeError, ValidationError, ValueError) as error:
        return _error("INVALID_TRANSCRIPT", str(error), 400)
    except JudgeError as error:
        return _error("JUDGING_UNAVAILABLE", str(error), 503)

    return jsonify(
        {
            "scenario": GameService.MOCK_SCENARIO.model_dump(mode="json"),
            "results": results.model_dump(mode="json"),
        }
    )


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status
