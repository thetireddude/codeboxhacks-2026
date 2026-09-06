"""Round orchestration between authoritative state and A5/A6 services."""

from __future__ import annotations

import logging
from uuid import UUID

from app.models import MatchResults, MatchState
from app.models.judgment import (
    JudgeInput,
    JudgeResult,
    JudgedPlayer,
    SemanticCategoryPoints,
)
from app.models.scoring import ScoringInput
from .game_service import GameService
from .judge_service import JudgeError, JudgeService
from .leaderboard_service import LeaderboardUnavailableError
from .scenario_service import ScenarioService
from .scoring_service import ScoringService


logger = logging.getLogger(__name__)


class MatchIntegrationService:
    def __init__(
        self,
        game_service: GameService,
        scenario_service: ScenarioService,
        judge_service: JudgeService,
        scoring_service: ScoringService,
        leaderboard_repository,
    ) -> None:
        self._game_service = game_service
        self._scenario_service = scenario_service
        self._judge_service = judge_service
        self._scoring_service = scoring_service
        self._leaderboard_repository = leaderboard_repository

    def prepare_round(self, match_id: UUID) -> MatchState:
        return self._game_service.set_scenario(
            match_id, self._scenario_service.generate_scenario()
        )

    def judge_round(self, match_id: UUID) -> tuple[MatchState, MatchResults]:
        match = self._game_service.begin_scoring(match_id)
        if match.scenario is None:
            raise ValueError("A completed match needs a scenario before judging")
        judge_input = JudgeInput(
            scenario=match.scenario,
            transcript_events=match.transcript_events,
            switch_response_latencies=self._scoring_service.calculate_switch_response_latencies(
                match.transcript_events
            ),
            round_duration_ms=self._game_service.round_duration_ms,
        )
        try:
            judgment = self._judge_service.judge(judge_input)
        except JudgeError:
            # A completed match should still reach results if Gemini is down.
            # Preserve objective Speed scoring while avoiding invented semantic
            # points or coaching that pretends Gemini completed a review.
            logger.exception(
                "Using deterministic judging fallback for match %s; events=%s",
                match_id,
                self._safe_event_summary(match.transcript_events),
            )
            judgment = self._unavailable_judgment()
        results = self._scoring_service.score(
            ScoringInput(
                match_id=match.match_id,
                transcript_events=match.transcript_events,
                judgment=judgment,
                round_duration_ms=self._game_service.round_duration_ms,
            )
        )
        completed_match = self._game_service.complete_scoring(match_id, results)
        try:
            self._leaderboard_repository.record_completed_match(completed_match, results)
        except LeaderboardUnavailableError:
            # Match results remain authoritative even when the optional durable
            # leaderboard store is offline. A later retry/outbox can backfill.
            logger.exception("Could not persist leaderboard score for match %s", match_id)
        return completed_match, results

    @staticmethod
    def _unavailable_judgment() -> JudgeResult:
        points = SemanticCategoryPoints(
            adaptability=0,
            articulation=0,
            coherence=0,
            collaboration=0,
        )
        player = JudgedPlayer(
            category_points=points,
            highlight="Gemini feedback was unavailable for this round.",
            improvement="Start a new match to receive Gemini coaching.",
        )
        return JudgeResult(player_a=player, player_b=player)

    @staticmethod
    def _safe_event_summary(events) -> list[dict]:
        """Describe live judge input without transcript text or credentials."""
        return [
            {
                "id": event.id,
                "type": event.type,
                "player_id": getattr(event, "player_id", None),
                "accepted": getattr(event, "accepted", None),
                "truncated_by_switch": getattr(
                    event, "truncated_by_switch", None
                ),
                "truncated_by_round_end": getattr(
                    event, "truncated_by_round_end", None
                ),
                "start_ms": getattr(event, "start_ms", None),
                "end_ms": getattr(event, "end_ms", None),
                "timestamp_ms": getattr(event, "timestamp_ms", None),
            }
            for event in events
        ]
