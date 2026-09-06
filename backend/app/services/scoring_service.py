"""Deterministic Switch Speed scoring and final A6 arcade aggregation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models.judgment import JudgeResult
from app.models.results import (
    CategoryPoints,
    HighlightEvent,
    MatchResults,
    PlayerResult,
    RubricCategoryLog,
    RubricLog,
)
from app.models.scoring import ScoringInput
from app.models.transcript import SwitchEvent, TranscriptEvent


class ScoringService:
    """Merge Gemini's semantic judgment with objective Switch-recovery timing."""

    def __init__(
        self,
        *,
        speed_base_points: int = 500,
        speed_decay_points_per_second: int = 120,
        speed_max_points: int = 2000,
    ) -> None:
        if speed_base_points < 0:
            raise ValueError("speed_base_points must not be negative")
        if speed_decay_points_per_second < 0:
            raise ValueError("speed_decay_points_per_second must not be negative")
        if speed_max_points < 0:
            raise ValueError("speed_max_points must not be negative")
        self._speed_base_points = speed_base_points
        self._speed_decay_points_per_second = speed_decay_points_per_second
        self._speed_max_points = speed_max_points

    def score(self, scoring_input: ScoringInput) -> MatchResults:
        """Return the complete, renderable final result for a finished round."""
        latencies = self.calculate_switch_response_latencies(
            scoring_input.transcript_events
        )
        speed_points = self._speed_points_by_player(
            scoring_input.transcript_events, latencies
        )
        player_a = self._player_result(scoring_input.judgment, "A", speed_points["A"])
        player_b = self._player_result(scoring_input.judgment, "B", speed_points["B"])
        winner = (
            "A"
            if player_a.total_points > player_b.total_points
            else "B"
            if player_b.total_points > player_a.total_points
            else "TIE"
        )
        return MatchResults(
            match_id=scoring_input.match_id,
            winner=winner,
            player_a=player_a,
            player_b=player_b,
            highlight_events=[
                HighlightEvent.model_validate(event.model_dump())
                for event in scoring_input.judgment.highlight_events
            ],
        )

    @staticmethod
    def calculate_switch_response_latencies(
        events: Iterable[TranscriptEvent],
    ) -> dict[str, int | None]:
        """Map each Switch to its target's next accepted response.

        When a target receives multiple Switches before an accepted replacement,
        only the newest Switch gets that response; earlier ones are superseded.
        This matches the rapid-Switch behavior owned by A4.
        """
        timeline = list(events)
        pending: list[SwitchEvent] = []
        latencies: dict[str, int | None] = {}
        for event in timeline:
            if event.type == "switch":
                pending.append(event)
                latencies[event.id] = None
                continue
            if not event.accepted:
                continue
            candidates = [
                switch
                for switch in pending
                if (
                    switch.target_player_id == event.player_id
                    and event.start_ms >= switch.timestamp_ms
                )
            ]
            if not candidates:
                continue
            latest = candidates[-1]
            latencies[latest.id] = event.start_ms - latest.timestamp_ms
            pending = [switch for switch in pending if switch not in candidates]
        return latencies

    def speed_points_for_latency(self, latency_ms: int | None) -> int:
        """Apply the tunable linear Speed curve to one completed recovery."""
        if latency_ms is None:
            return 0
        if latency_ms < 0:
            raise ValueError("Switch response latency must not be negative")
        points = self._speed_base_points - (
            self._speed_decay_points_per_second * latency_ms // 1000
        )
        return max(0, points)

    def _speed_points_by_player(
        self,
        events: Iterable[TranscriptEvent],
        latencies: dict[str, int | None],
    ) -> dict[str, int]:
        points = {"A": 0, "B": 0}
        for event in events:
            if event.type == "switch":
                points[event.target_player_id] += self.speed_points_for_latency(
                    latencies.get(event.id)
                )
        return {
            player: min(total, self._speed_max_points)
            for player, total in points.items()
        }

    @staticmethod
    def _player_result(
        judgment: JudgeResult, player: str, speed_points: int
    ) -> PlayerResult:
        judged_player = judgment.player_a if player == "A" else judgment.player_b
        semantic = judged_player.category_points
        categories = CategoryPoints(
            adaptability=semantic.adaptability,
            articulation=semantic.articulation,
            speed=speed_points,
            coherence=semantic.coherence,
            collaboration=semantic.collaboration,
        )
        return PlayerResult(
            total_points=sum(categories.model_dump().values()),
            category_points=categories,
            rubric_log=ScoringService._rubric_log(categories, judged_player.overview),
            highlight=judged_player.highlight,
            improvement=judged_player.improvement,
        )

    @staticmethod
    def _rubric_log(categories: CategoryPoints, overview: str) -> RubricLog:
        return RubricLog(
            overview=overview,
            **{
                category: RubricCategoryLog(
                    points=points,
                    rating=ScoringService._rating_for_points(points),
                )
                for category, points in categories.model_dump().items()
            },
        )

    @staticmethod
    def _rating_for_points(points: int) -> str:
        if points == 0:
            return "NO EVIDENCE"
        if points < 800:
            return "VERY LIMITED"
        if points < 1200:
            return "INCONSISTENT"
        if points < 1600:
            return "FUNCTIONAL"
        if points < 2000:
            return "STRONG"
        return "EXCEPTIONAL"


def create_scoring_service(config: Any) -> ScoringService:
    """Build the configured A6 score engine at the application boundary."""
    return ScoringService(
        speed_base_points=config["SPEED_BASE_POINTS"],
        speed_decay_points_per_second=config["SPEED_DECAY_POINTS_PER_SECOND"],
        speed_max_points=config["SPEED_MAX_POINTS"],
    )
