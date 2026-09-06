"""Authoritative ready, turn, and round lifecycle business logic."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from app.models import MatchResults, MatchState, MatchStatus, PlayerSlot, Scenario

from .redis_service import RedisService


class GameStateError(ValueError):
    """A requested game transition is not valid for the current match state."""


class GameService:
    """Own state transitions; controllers own Socket.IO scheduling and broadcasts."""

    MOCK_SCENARIO = Scenario(
        tone="wacky",
        scenario=(
            "Two astronauts discover that neither knows how to land the spaceship."
        ),
        player_a_role="Overconfident captain",
        player_b_role="Intern pretending to know what they are doing",
    )

    def __init__(self, storage: RedisService, round_duration_ms: int) -> None:
        self._storage = storage
        self._round_duration_ms = round_duration_ms
        self._lock = Lock()

    def player_ready(self, match_id: UUID, guest_id: UUID) -> tuple[MatchState, bool]:
        """Record readiness and return whether both players just started countdown."""
        with self._lock:
            match = self._require_match(match_id)
            self._require_player(match, guest_id)
            if match.state not in (MatchStatus.MATCH_FOUND, MatchStatus.READY):
                raise GameStateError("Match is not accepting ready signals")

            ready_ids = list(dict.fromkeys([*match.ready_player_ids, guest_id]))
            if len(ready_ids) == 2:
                match = match.model_copy(
                    update={
                        "ready_player_ids": ready_ids,
                        "state": MatchStatus.COUNTDOWN,
                        "scenario": match.scenario or self.MOCK_SCENARIO,
                    }
                )
                starts_countdown = True
            else:
                match = match.model_copy(
                    update={"ready_player_ids": ready_ids, "state": MatchStatus.READY}
                )
                starts_countdown = False
            self._storage.save_match(match)
            return match, starts_countdown

    def start_round(self, match_id: UUID) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.COUNTDOWN:
                raise GameStateError("Match is not in countdown")
            match = match.model_copy(
                update={
                    "state": MatchStatus.ROUND_ACTIVE,
                    "round_started_at": datetime.now(UTC),
                    "active_player_id": "A",
                }
            )
            self._storage.save_match(match)
            return match

    def complete_turn(self, match_id: UUID, guest_id: UUID) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.ROUND_ACTIVE:
                raise GameStateError("Round is not active")
            active_guest_id = self._guest_for_slot(match, match.active_player_id)
            if guest_id != active_guest_id:
                raise GameStateError("Only the active speaker can complete a turn")
            next_player: PlayerSlot = "B" if match.active_player_id == "A" else "A"
            match = match.model_copy(update={"active_player_id": next_player})
            self._storage.save_match(match)
            return match

    def end_round(self, match_id: UUID) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.ROUND_ACTIVE:
                raise GameStateError("Round is not active")
            match = match.model_copy(
                update={"state": MatchStatus.ROUND_END, "active_player_id": None}
            )
            self._storage.save_match(match)
            return match

    def begin_scoring(self, match_id: UUID) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.ROUND_END:
                raise GameStateError("Round has not ended")
            match = match.model_copy(update={"state": MatchStatus.SCORING})
            self._storage.save_match(match)
            return match

    def complete_scoring(self, match_id: UUID, results: MatchResults) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.SCORING:
                raise GameStateError("Match is not being scored")
            if results.match_id != match_id:
                raise GameStateError("Result match_id does not match the active match")
            match = match.model_copy(update={"state": MatchStatus.RESULTS})
            self._storage.save_match(match)
            return match

    def disconnect_player(self, match_id: UUID, guest_id: UUID) -> MatchState:
        with self._lock:
            match = self._require_match(match_id)
            self._require_player(match, guest_id)
            if match.state in (MatchStatus.COUNTDOWN, MatchStatus.ROUND_ACTIVE):
                match = match.model_copy(
                    update={"state": MatchStatus.ROUND_END, "active_player_id": None}
                )
                self._storage.save_match(match)
            return match

    @property
    def round_duration_ms(self) -> int:
        return self._round_duration_ms

    def _require_match(self, match_id: UUID) -> MatchState:
        match = self._storage.get_match(match_id)
        if match is None:
            raise GameStateError("Match was not found")
        return match

    @staticmethod
    def _require_player(match: MatchState, guest_id: UUID) -> None:
        if guest_id not in (match.player_a_id, match.player_b_id):
            raise GameStateError("Guest is not in this match")

    @staticmethod
    def _guest_for_slot(match: MatchState, slot: PlayerSlot | None) -> UUID:
        if slot == "A":
            return match.player_a_id
        if slot == "B":
            return match.player_b_id
        raise GameStateError("Match has no active speaker")
