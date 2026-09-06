"""Round orchestration between authoritative state and A5/A6 services."""

from __future__ import annotations

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
from .scenario_service import ScenarioService
from .scoring_service import ScoringService


class MatchIntegrationService:
    def __init__(
        self,
        game_service: GameService,
        scenario_service: ScenarioService,
        judge_service: JudgeService,
        scoring_service: ScoringService,
    ) -> None:
        self._game_service = game_service
        self._scenario_service = scenario_service
        self._judge_service = judge_service
        self._scoring_service = scoring_service

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
            judgment = self._unavailable_judgment()
        results = self._scoring_service.score(
            ScoringInput(
                match_id=match.match_id,
                transcript_events=match.transcript_events,
                judgment=judgment,
                round_duration_ms=self._game_service.round_duration_ms,
            )
        )
        return self._game_service.complete_scoring(match_id, results), results

    @staticmethod
    def _unavailable_judgment() -> JudgeResult:
        points = SemanticCategoryPoints(
            adaptability=0,
            creativity=0,
            coherence=0,
            collaboration=0,
        )
        player = JudgedPlayer(
            category_points=points,
            highlight="Gemini feedback was unavailable for this round.",
            improvement="Start a new match to receive Gemini coaching.",
        )
        return JudgeResult(player_a=player, player_b=player)
