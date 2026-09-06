from uuid import UUID

from flask import Blueprint, current_app, jsonify, request

from app.services.leaderboard_service import (
    InvalidLeaderboardCursor,
    LeaderboardUnavailableError,
)

leaderboard_blueprint = Blueprint("leaderboard", __name__, url_prefix="/api")


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@leaderboard_blueprint.get("/leaderboard")
def get_leaderboard():
    raw_limit = request.args.get("limit", "50")
    try:
        limit = int(raw_limit)
    except ValueError:
        return _error(
            "INVALID_LEADERBOARD_LIMIT", "limit must be an integer from 1 to 100", 400
        )
    if not 1 <= limit <= 100:
        return _error("INVALID_LEADERBOARD_LIMIT", "limit must be from 1 to 100", 400)
    try:
        payload = current_app.extensions["leaderboard_repository"].get_leaderboard(
            limit, request.args.get("cursor")
        )
    except InvalidLeaderboardCursor:
        return _error("INVALID_LEADERBOARD_CURSOR", "cursor is invalid", 400)
    except LeaderboardUnavailableError:
        return _error(
            "LEADERBOARD_UNAVAILABLE", "Leaderboard is temporarily unavailable", 503
        )
    return jsonify(payload)


@leaderboard_blueprint.get("/players/<guest_id>/rank")
def get_player_rank(guest_id: str):
    try:
        player_id = UUID(guest_id)
    except ValueError:
        return _error("INVALID_GUEST_ID", "guest_id must be a UUID", 400)
    try:
        entry = current_app.extensions["leaderboard_repository"].get_player_rank(
            player_id
        )
    except LeaderboardUnavailableError:
        return _error(
            "LEADERBOARD_UNAVAILABLE", "Leaderboard is temporarily unavailable", 503
        )
    if entry is None:
        return _error("PLAYER_NOT_RANKED", "Player has no completed matches", 404)
    return jsonify(entry)


@leaderboard_blueprint.get("/players/<guest_id>/match-feedback")
def get_player_feedback(guest_id: str):
    try:
        player_id = UUID(guest_id)
    except ValueError:
        return _error("INVALID_GUEST_ID", "guest_id must be a UUID", 400)

    raw_limit = request.args.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError:
        return _error("INVALID_FEEDBACK_LIMIT", "limit must be an integer from 1 to 100", 400)
    if not 1 <= limit <= 100:
        return _error("INVALID_FEEDBACK_LIMIT", "limit must be from 1 to 100", 400)

    try:
        feedback = current_app.extensions["leaderboard_repository"].get_player_feedback(
            player_id, limit
        )
    except LeaderboardUnavailableError:
        return _error(
            "LEADERBOARD_UNAVAILABLE", "Player feedback is temporarily unavailable", 503
        )

    matches = [
        {"match_number": index, **entry} for index, entry in enumerate(feedback, start=1)
    ]
    return jsonify(
        {
            "guest_id": str(player_id),
            "matches": matches,
            "summary": _feedback_summary(matches),
        }
    )


def _feedback_summary(matches: list[dict]) -> dict:
    """Expose the latest persisted AI coaching without another model request."""
    if not matches:
        return {"status": "empty", "tips": []}
    latest = matches[-1]
    return {
        "status": "ready",
        "tips": [
            {"label": "AI OVERVIEW", "text": latest["overview"]},
            {"label": "KEEP BUILDING", "text": latest["what_went_well"]},
            {"label": "NEXT MATCH", "text": latest["what_to_improve"]},
        ],
    }
