from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.results import (
    CategoryPoints,
    MatchResults,
    PlayerResult,
    RubricCategoryLog,
    RubricLog,
)
from app.services.leaderboard_service import (
    InvalidLeaderboardCursor,
    LeaderboardRepository,
)


def result(match_id, winner: str, a_score: int, b_score: int) -> MatchResults:
    def points(score: int) -> CategoryPoints:
        return CategoryPoints(
            adaptability=score,
            articulation=0,
            speed=0,
            coherence=0,
            collaboration=0,
        )

    def player(score: int) -> PlayerResult:
        categories = points(score)
        rubric_log = RubricLog(
            overview="A focused practice round.",
            **{
                category: RubricCategoryLog(
                    points=value,
                    rating="NO EVIDENCE" if value == 0 else "FUNCTIONAL",
                )
                for category, value in categories.model_dump().items()
            },
        )
        return PlayerResult(
            total_points=score,
            category_points=categories,
            rubric_log=rubric_log,
            highlight="Good moment",
            improvement="Try again",
        )
    return MatchResults(
        match_id=match_id,
        winner=winner,
        player_a=player(a_score),
        player_b=player(b_score),
        highlight_events=[],
    )


def test_leaderboard_keeps_history_but_ranks_best_score_and_is_idempotent():
    repository = LeaderboardRepository("sqlite://", "test", auto_create_schema=True)
    player_a, player_b = uuid4(), uuid4()
    first_id, second_id = uuid4(), uuid4()
    first_match = SimpleNamespace(
        match_id=first_id, player_a_id=player_a, player_b_id=player_b
    )
    second_match = SimpleNamespace(
        match_id=second_id, player_a_id=player_a, player_b_id=player_b
    )
    repository.record_completed_match(first_match, result(first_id, "A", 50, 20))
    repository.record_completed_match(first_match, result(first_id, "A", 50, 20))
    repository.record_completed_match(second_match, result(second_id, "B", 40, 80))

    entries = repository.get_leaderboard(10)["entries"]
    assert [
        (entry["guest_id"], entry["best_score"], entry["games_played"])
        for entry in entries
    ] == [
        (str(player_b), 80, 2),
        (str(player_a), 50, 2),
    ]
    assert repository.get_player_rank(player_a)["rank"] == 2
    feedback = repository.get_player_feedback(player_a)
    assert len(feedback) == 2
    assert feedback[0]["guest_id"] == str(player_a)
    assert feedback[0]["what_went_well"] == "Good moment"
    assert feedback[0]["skills"]["adaptability"]["points"] in {40, 50}


def test_cursor_is_validated():
    repository = LeaderboardRepository("sqlite://", "test", auto_create_schema=True)
    with pytest.raises(InvalidLeaderboardCursor):
        repository.get_leaderboard(10, "not-a-cursor")
