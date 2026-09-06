"""Round orchestration between authoritative state and A5/A6 services."""

from __future__ import annotations

from uuid import UUID

from app.models import MatchResults, MatchState
from app.models.judgment import JudgeInput
from app.models.scoring import ScoringInput
from .game_service import GameService
from .judge_service import JudgeService
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
        judgment = self._judge_service.judge(
            JudgeInput(
                scenario=match.scenario,
                transcript_events=match.transcript_events,
                switch_response_latencies=self._scoring_service.calculate_switch_response_latencies(
                    match.transcript_events
                ),
                round_duration_ms=self._game_service.round_duration_ms,
            )
        )
        results = self._scoring_service.score(
            ScoringInput(
                match_id=match.match_id,
                transcript_events=match.transcript_events,
                judgment=judgment,
                round_duration_ms=self._game_service.round_duration_ms,
            )
        )
        return self._game_service.complete_scoring(match_id, results), results
