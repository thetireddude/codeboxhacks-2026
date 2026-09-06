"""A3 bridge from provider speech callbacks to authoritative game events."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from app.models import MatchState, SpeechEvent, SwitchEvent
from app.services.game_service import GameService, GameStateError


@dataclass(frozen=True)
class ActiveSpeech:
    match_id: UUID
    guest_id: UUID
    start_ms: int
    latest_text: str = ""


class TranscriptService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service
        self._active: dict[str, ActiveSpeech] = {}
        self._lock = Lock()

    def speech_started(self, match_id: UUID, guest_id: UUID, speech_id: str) -> None:
        _, start_ms = self._game_service.begin_speech(match_id, guest_id)
        self._game_service.record_switch_response(match_id, guest_id, start_ms)
        with self._lock:
            if speech_id in self._active:
                raise GameStateError("Speech is already active")
            if any(speech.match_id == match_id for speech in self._active.values()):
                raise GameStateError("The match already has active speech")
            self._active[speech_id] = ActiveSpeech(match_id, guest_id, start_ms)

    def speech_partial(self, speech_id: str, text: str) -> None:
        cleaned_text = text.strip()
        if not cleaned_text:
            return
        with self._lock:
            speech = self._active.get(speech_id)
            if speech is None:
                raise GameStateError("Speech did not have an authoritative start")
            self._active[speech_id] = ActiveSpeech(
                speech.match_id,
                speech.guest_id,
                speech.start_ms,
                cleaned_text,
            )

    def speech_final(self, speech_id: str, text: str):
        with self._lock:
            speech = self._active.pop(speech_id, None)
        if speech is None:
            raise GameStateError("Speech did not have an authoritative start")
        return self._game_service.finalize_speech(
            speech.match_id,
            speech.guest_id,
            speech_id,
            text,
            speech.start_ms,
        )

    def finalize_round(self, match_id: UUID):
        """Finalize the current partial at the authoritative round boundary."""
        with self._lock:
            active = [
                (speech_id, speech)
                for speech_id, speech in self._active.items()
                if speech.match_id == match_id
            ]
            for speech_id, _ in active:
                self._active.pop(speech_id, None)

        events = []
        for speech_id, speech in sorted(active, key=lambda item: item[1].start_ms):
            if not speech.latest_text:
                continue
            _, event = self._game_service.finalize_speech(
                speech.match_id,
                speech.guest_id,
                speech_id,
                speech.latest_text,
                speech.start_ms,
                truncated_by_round_end=True,
            )
            events.append(event)
        return events

    def press_switch(
        self, match_id: UUID, guest_id: UUID, request_id: str
    ) -> tuple[MatchState, SwitchEvent, bool, SpeechEvent | None]:
        """Atomically reject any current partial before recording the Switch."""
        with self._lock:
            active = next(
                (
                    (speech_id, speech)
                    for speech_id, speech in self._active.items()
                    if speech.match_id == match_id
                ),
                None,
            )
            speech_id = active[0] if active else None
            speech = active[1] if active else None
            match, event, is_replay, interrupted = (
                self._game_service.press_switch_with_interruption(
                    match_id,
                    guest_id,
                    request_id,
                    speech_id=speech_id,
                    text=speech.latest_text if speech else None,
                    start_ms=speech.start_ms if speech else None,
                )
            )
            if active is not None and not is_replay:
                self._active.pop(speech_id, None)
            return match, event, is_replay, interrupted
