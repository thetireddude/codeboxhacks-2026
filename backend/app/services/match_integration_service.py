"""B5 coordination between authoritative game state and AI service boundaries."""

from __future__ import annotations

from uuid import UUID

from app.models import MatchResults, MatchState

from .game_service import GameService
from .judge_service import JudgeService
from .scenario_service import MockScenarioService, ScenarioService


class MatchIntegrationService:
    """Keep provider calls outside controllers while GameService owns transitions."""

    def __init__(
        self,
        game_service: GameService,
        scenario_service: ScenarioService | MockScenarioService,
        judge_service: JudgeService,
    ) -> None:
        self._game_service = game_service
        self._scenario_service = scenario_service
        self._judge_service = judge_service

    def prepare_round(self, match_id: UUID) -> MatchState:
        scenario = self._scenario_service.generate_scenario()
        return self._game_service.set_scenario(match_id, scenario)

    def judge_round(self, match_id: UUID) -> tuple[MatchState, MatchResults]:
        """Move ROUND_END -> SCORING once, then accept one validated result."""
        scoring_match = self._game_service.begin_scoring(match_id)
        results = self._judge_service.judge(scoring_match)
        completed_match = self.accept_judge_result(match_id, results)
        return completed_match, results

    def accept_judge_result(
        self, match_id: UUID, results: MatchResults
    ) -> MatchState:
        """Accept the validated final object supplied by the A5 judge boundary."""
        return self._game_service.complete_scoring(match_id, results)
