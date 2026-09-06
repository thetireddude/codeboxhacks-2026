"""Authoritative ready, turn, and round lifecycle business logic."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import UUID, uuid4

from app.models import (
    MatchResults,
    MatchState,
    MatchStatus,
    PlayerSlot,
    Scenario,
    SpeechEvent,
    SwitchEvent,
)

from .redis_service import RedisService


class GameStateError(ValueError):
    """A requested game transition is not valid for the current match state."""


class SwitchRejectedError(GameStateError):
    """A Switch request failed a gameplay validation rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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

    def set_scenario(self, match_id: UUID, scenario: Scenario) -> MatchState:
        """Persist the one validated scenario shared by both participants."""
        with self._lock:
            match = self._require_match(match_id)
            if match.state != MatchStatus.COUNTDOWN:
                raise GameStateError("Scenario can only be set during countdown")
            match = match.model_copy(update={"scenario": scenario})
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

    def begin_speech(self, match_id: UUID, guest_id: UUID) -> tuple[PlayerSlot, int]:
        """Validate the authoritative speaker and capture a round-relative start."""
        with self._lock:
            match = self._require_active_speaker(match_id, guest_id)
            return match.active_player_id, min(
                self._elapsed_ms(match), self._round_duration_ms
            )

    def finalize_speech(
        self,
        match_id: UUID,
        guest_id: UUID,
        speech_id: str,
        text: str,
        start_ms: int,
        *,
        truncated_by_round_end: bool = False,
    ) -> tuple[MatchState, SpeechEvent]:
        """Persist an accepted speech line and advance to the next player."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise GameStateError("Speech text cannot be empty")
        with self._lock:
            match = self._require_active_speaker(match_id, guest_id)
            end_ms = (
                self._round_duration_ms
                if truncated_by_round_end
                else min(
                    self._round_duration_ms,
                    max(start_ms, self._elapsed_ms(match)),
                )
            )
            event = SpeechEvent(
                type="speech",
                id=speech_id,
                player_id=match.active_player_id,
                text=cleaned_text,
                start_ms=start_ms,
                end_ms=end_ms,
                is_final=True,
                accepted=True,
                truncated_by_switch=False,
                truncated_by_round_end=truncated_by_round_end,
            )
            next_player: PlayerSlot = (
                match.active_player_id
                if truncated_by_round_end
                else "B" if match.active_player_id == "A" else "A"
            )
            match = match.model_copy(
                update={
                    "active_player_id": next_player,
                    "transcript_events": [*match.transcript_events, event],
                }
            )
            self._storage.save_match(match)
            return match, event

    def record_switch_response(
        self, match_id: UUID, guest_id: UUID, speech_start_ms: int
    ) -> MatchState:
        """Persist latency for the latest pending Switch and supersede older ones."""
        with self._lock:
            match = self._require_active_speaker(match_id, guest_id)
            latencies = dict(match.switch_response_latencies)
            pending = [
                event
                for event in match.transcript_events
                if (
                    event.type == "switch"
                    and event.target_player_id == match.active_player_id
                    and event.id not in latencies
                    and event.timestamp_ms <= speech_start_ms
                )
            ]
            for event in pending[:-1]:
                latencies[event.id] = None
            if pending:
                latest = pending[-1]
                latencies[latest.id] = speech_start_ms - latest.timestamp_ms
            if latencies == match.switch_response_latencies:
                return match
            match = match.model_copy(update={"switch_response_latencies": latencies})
            self._storage.save_match(match)
            return match

    def press_switch(
        self, match_id: UUID, guest_id: UUID, request_id: str
    ) -> tuple[MatchState, SwitchEvent, bool]:
        """Apply a listener Switch and return whether it was previously accepted."""
        match, event, is_replay, _ = self._apply_switch(
            match_id, guest_id, request_id
        )
        return match, event, is_replay

    def press_switch_with_interruption(
        self,
        match_id: UUID,
        guest_id: UUID,
        request_id: str,
        *,
        speech_id: str | None,
        text: str | None,
        start_ms: int | None,
    ) -> tuple[MatchState, SwitchEvent, bool, SpeechEvent | None]:
        """Apply a Switch and atomically place an interrupted speech before it."""
        interrupted = None
        if speech_id is not None and text is not None and start_ms is not None:
            cleaned_text = text.strip()
            if cleaned_text:
                interrupted = (speech_id, cleaned_text, start_ms)
        return self._apply_switch(match_id, guest_id, request_id, interrupted)

    def _apply_switch(
        self,
        match_id: UUID,
        guest_id: UUID,
        request_id: str,
        interrupted: tuple[str, str, int] | None = None,
    ) -> tuple[MatchState, SwitchEvent, bool, SpeechEvent | None]:
        if not isinstance(request_id, str) or not request_id.strip():
            raise SwitchRejectedError("INVALID_PAYLOAD", "request_id is required")

        with self._lock:
            match = self._require_match(match_id)
            self._require_player(match, guest_id)
            switching_player = self._slot_for_guest(match, guest_id)
            existing_event = self._storage.get_switch_request(match_id, request_id)
            if existing_event is not None:
                if existing_event.from_player_id != switching_player:
                    raise SwitchRejectedError(
                        "DUPLICATE_REQUEST",
                        "request_id was already used by the other player",
                    )
                return match, existing_event, True, None

            if match.state != MatchStatus.ROUND_ACTIVE:
                raise SwitchRejectedError("ROUND_NOT_ACTIVE", "Round is not active")

            active_guest_id = self._guest_for_slot(match, match.active_player_id)
            if guest_id == active_guest_id:
                raise SwitchRejectedError(
                    "NOT_LISTENER", "Only the listener can use a Switch"
                )

            remaining = getattr(match.switches_remaining, switching_player)
            if remaining < 1:
                raise SwitchRejectedError("NO_SWITCHES_REMAINING", "No Switches remain")

            timestamp_ms = min(self._elapsed_ms(match), self._round_duration_ms)
            interrupted_event = None
            if interrupted is not None:
                speech_id, text, start_ms = interrupted
                interrupted_event = SpeechEvent(
                    type="speech",
                    id=speech_id,
                    player_id=match.active_player_id,
                    text=text,
                    start_ms=start_ms,
                    end_ms=max(start_ms, timestamp_ms),
                    is_final=True,
                    accepted=False,
                    truncated_by_switch=True,
                    truncated_by_round_end=False,
                )

            event = SwitchEvent(
                type="switch",
                id=f"switch_{uuid4().hex}",
                from_player_id=switching_player,
                target_player_id=match.active_player_id,
                timestamp_ms=timestamp_ms,
            )
            inventory = match.switches_remaining.model_copy(
                update={switching_player: remaining - 1}
            )
            match = match.model_copy(
                update={
                    "switches_remaining": inventory,
                    "transcript_events": [
                        *match.transcript_events,
                        *([interrupted_event] if interrupted_event else []),
                        event,
                    ],
                }
            )
            self._storage.save_match(match)
            self._storage.save_switch_request(match_id, request_id, event)
            return match, event, False, interrupted_event

    def append_transcript_event(
        self, match_id: UUID, guest_id: UUID, event
    ) -> MatchState:
        """Accept one canonical service-produced transcript event.

        Speech is accepted only from the authoritative active speaker. Switch
        events are already created by ``press_switch`` and must not be submitted
        through this path.
        """
        with self._lock:
            match = self._require_match(match_id)
            self._require_player(match, guest_id)
            if match.state != MatchStatus.ROUND_ACTIVE:
                raise GameStateError("Round is not active")
            if getattr(event, "type", None) != "speech":
                raise GameStateError("Only speech events may be appended here")
            if event.player_id != self._slot_for_guest(match, guest_id):
                raise GameStateError("Speech event does not belong to this guest")
            if event.player_id != match.active_player_id:
                raise GameStateError("Only the active speaker may submit speech")
            match = match.model_copy(
                update={"transcript_events": [*match.transcript_events, event]}
            )
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

    def elapsed_ms(self, match_id: UUID) -> int:
        """Return authoritative milliseconds from round start for service events."""
        match = self._require_match(match_id)
        return self._elapsed_ms(match)

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

    def _require_active_speaker(self, match_id: UUID, guest_id: UUID) -> MatchState:
        match = self._require_match(match_id)
        if match.state != MatchStatus.ROUND_ACTIVE:
            raise GameStateError("Round is not active")
        if guest_id != self._guest_for_slot(match, match.active_player_id):
            raise GameStateError("Only the active speaker can provide speech")
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

    @staticmethod
    def _slot_for_guest(match: MatchState, guest_id: UUID) -> PlayerSlot:
        if guest_id == match.player_a_id:
            return "A"
        if guest_id == match.player_b_id:
            return "B"
        raise GameStateError("Guest is not in this match")

    @staticmethod
    def _elapsed_ms(match: MatchState) -> int:
        if match.round_started_at is None:
            return 0
        return max(
            0,
            int((datetime.now(UTC) - match.round_started_at).total_seconds() * 1000),
        )
