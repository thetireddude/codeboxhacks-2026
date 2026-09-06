from types import SimpleNamespace
from uuid import uuid4

from app import create_app
from app.config import AppConfig
from app.models.results import (
    CategoryPoints,
    MatchResults,
    PlayerResult,
    RubricCategoryLog,
    RubricLog,
)


class ProgressTestConfig(AppConfig):
    TESTING = True
    DATABASE_URL = "sqlite://"
    LEADERBOARD_AUTO_CREATE_SCHEMA = True
    USE_IN_MEMORY_REDIS = True


def _result(match_id, score: int) -> MatchResults:
    categories = CategoryPoints(
        adaptability=score,
        articulation=20,
        speed=30,
        coherence=40,
        collaboration=50,
    )
    rubric_log = RubricLog(
        overview=f"Overview for {score}.",
        **{
            category: RubricCategoryLog(points=value, rating="FUNCTIONAL")
            for category, value in categories.model_dump().items()
        },
    )
    player = PlayerResult(
        total_points=score,
        category_points=categories,
        rubric_log=rubric_log,
        highlight=f"Strength for {score}.",
        improvement=f"Improve {score}.",
    )
    return MatchResults(
        match_id=match_id,
        winner="TIE",
        player_a=player,
        player_b=player,
        highlight_events=[],
    )


def _record_match(app, match_id, player_a, player_b, score: int) -> None:
    app.extensions["leaderboard_repository"].record_completed_match(
        SimpleNamespace(match_id=match_id, player_a_id=player_a, player_b_id=player_b),
        _result(match_id, score),
    )


def test_match_feedback_endpoint_returns_complete_chronological_history():
    app = create_app(ProgressTestConfig)
    player_a, player_b = uuid4(), uuid4()
    first_match, second_match = uuid4(), uuid4()
    _record_match(app, first_match, player_a, player_b, 100)
    _record_match(app, second_match, player_a, player_b, 200)

    response = app.test_client().get(f"/api/players/{player_a}/match-feedback")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["guest_id"] == str(player_a)
    assert [entry["match_id"] for entry in payload["matches"]] == [
        str(first_match),
        str(second_match),
    ]
    assert [entry["match_number"] for entry in payload["matches"]] == [1, 2]
    first = payload["matches"][0]
    assert first["total_score"] == 100
    assert first["skills"]["adaptability"] == {
        "points": 100,
        "rating": "FUNCTIONAL",
    }
    assert first["overview"] == "Overview for 100."
    assert first["what_went_well"] == "Strength for 100."
    assert first["what_to_improve"] == "Improve 100."
    assert first["rubric_log"]["speed"] == {"points": 30, "rating": "FUNCTIONAL"}
    assert payload["summary"] == {
        "status": "ready",
        "tips": [
            {"label": "AI OVERVIEW", "text": "Overview for 200."},
            {"label": "KEEP BUILDING", "text": "Strength for 200."},
            {"label": "NEXT MATCH", "text": "Improve 200."},
        ],
    }


def test_match_feedback_endpoint_handles_empty_invalid_and_bad_limits():
    app = create_app(ProgressTestConfig)
    player_id = uuid4()
    client = app.test_client()

    empty = client.get(f"/api/players/{player_id}/match-feedback")
    assert empty.status_code == 200
    assert empty.get_json() == {
        "guest_id": str(player_id),
        "matches": [],
        "summary": {"status": "empty", "tips": []},
    }
    assert client.get("/api/players/not-a-uuid/match-feedback").status_code == 400
    assert client.get(f"/api/players/{player_id}/match-feedback?limit=0").status_code == 400
    assert client.get(f"/api/players/{player_id}/match-feedback?limit=nope").status_code == 400
