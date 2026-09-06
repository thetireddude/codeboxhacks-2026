"""Judge boundary used by B5 orchestration and replaced by A5 Gemini work."""

from __future__ import annotations

from typing import Protocol

from app.models.match import MatchState
from app.models.results import CategoryPoints, MatchResults, PlayerResult


class JudgeService(Protocol):
    def judge(self, match: MatchState) -> MatchResults: ...


class MockJudgeService:
    """Return a valid deterministic result for end-to-end B5 development."""

    def judge(self, match: MatchState) -> MatchResults:
        zero_points = CategoryPoints(
            adaptability=0, creativity=0, speed=0, coherence=0, collaboration=0
        )
        return MatchResults(
            match_id=match.match_id,
            winner="TIE",
            player_a=PlayerResult(
                total_points=0,
                category_points=zero_points,
                highlight="Mock judging is ready for Gemini integration.",
                improvement="Keep building on your partner's choices.",
            ),
            player_b=PlayerResult(
                total_points=0,
                category_points=zero_points,
                highlight="Mock judging is ready for Gemini integration.",
                improvement="Keep building on your partner's choices.",
            ),
            highlight_events=[],
        )


def create_judge_service(_config) -> JudgeService:
    return MockJudgeService()
