"""Socket.IO entry points for the A2 live speech-to-text stream."""

from __future__ import annotations

from flask import request

from app import socketio
from app.models import SpeechEvent
from app.services.game_service import GameService, GameStateError
from app.services.matchmaking_service import MatchmakingService
from app.services.transcription_service import (
    TranscriptionCallbacks,
    TranscriptionError,
    TranscriptionService,
)
from app.views.socket_views import transcript_event_payload, turn_changed_payload


def register_transcription_handlers(
    service: TranscriptionService,
    game_service: GameService | None = None,
    matchmaking_service: MatchmakingService | None = None,
    socket_guests: dict[str, str] | None = None,
) -> None:
    @socketio.on("transcription:start")
    def start_transcription(payload: dict | None) -> dict:
        player_id = (payload or {}).get("player_id")
        if player_id not in ("A", "B"):
            return _error("INVALID_PAYLOAD", "player_id must be A or B")
        try:
            match_context = _match_context(
                payload, player_id, matchmaking_service, socket_guests
            )
            service.start_stream(
                request.sid,
                player_id,
                _callbacks(
                    request.sid,
                    player_id,
                    game_service,
                    matchmaking_service,
                    match_context,
                ),
            )
        except (TranscriptionError, GameStateError, ValueError) as error:
            return _error("STT_UNAVAILABLE", str(error))
        return {
            "ok": True,
            "sample_rate": service.sample_rate,
            "chunk_ms": service.chunk_ms,
            "max_chunk_bytes": service.max_chunk_bytes,
        }

    @socketio.on("transcription:audio")
    def send_audio(audio: bytes) -> dict:
        try:
            service.send_audio(request.sid, audio)
        except TranscriptionError as error:
            return _error("INVALID_AUDIO", str(error))
        return {"ok": True}

    @socketio.on("transcription:stop")
    def stop_transcription() -> dict:
        return {"ok": True, "stopped": service.stop_stream(request.sid)}


def _callbacks(
    socket_id: str,
    player_id: str,
    game_service: GameService | None,
    matchmaking_service: MatchmakingService | None,
    match_context: tuple | None,
) -> TranscriptionCallbacks:
    start_ms: int | None = None

    def on_started(speech_id: str) -> None:
        nonlocal start_ms
        start_ms = (
            game_service.elapsed_ms(match_context[0])
            if game_service and match_context
            else 0
        )
        socketio.emit(
            "speech:started",
            {"player_id": player_id, "speech_id": speech_id},
            to=socket_id,
        )

    def on_final(speech_id: str, text: str) -> None:
        socketio.emit(
            "speech:final",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        )
        if not game_service or not matchmaking_service or not match_context:
            return
        match_id, guest_id = match_context
        try:
            event = SpeechEvent(
                type="speech",
                id=speech_id,
                player_id=player_id,
                text=text,
                start_ms=start_ms or game_service.elapsed_ms(match_id),
                end_ms=game_service.elapsed_ms(match_id),
                is_final=True,
                accepted=True,
                truncated_by_switch=False,
                truncated_by_round_end=False,
            )
            match = game_service.append_transcript_event(match_id, guest_id, event)
            _emit_to_match(
                matchmaking_service,
                match,
                "transcript:event",
                transcript_event_payload(match, event),
            )
            match = game_service.complete_turn(match_id, guest_id)
            _emit_to_match(
                matchmaking_service,
                match,
                "turn:changed",
                turn_changed_payload(match, game_service.elapsed_ms(match_id)),
            )
        except GameStateError as error:
            socketio.emit(
                "transcription:error",
                {"code": "TRANSCRIPT_REJECTED", "message": str(error)},
                to=socket_id,
            )

    return TranscriptionCallbacks(
        on_started=on_started,
        on_partial=lambda speech_id, text: socketio.emit(
            "speech:partial",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        ),
        on_final=on_final,
        on_error=lambda code, message: socketio.emit(
            "transcription:error", {"code": code, "message": message}, to=socket_id
        ),
    )


def _match_context(payload, player_id, matchmaking_service, socket_guests):
    match_id_text = (payload or {}).get("match_id")
    if not match_id_text:
        return None
    if matchmaking_service is None or socket_guests is None:
        raise ValueError("Match transcription is unavailable")
    from uuid import UUID

    guest_id = UUID(socket_guests[request.sid])
    match_id = UUID(str(match_id_text))
    match = matchmaking_service.get_match_for_guest(guest_id)
    if match is None or match.match_id != match_id:
        raise ValueError("Guest is not in this match")
    slot = "A" if match.player_a_id == guest_id else "B"
    if player_id != slot:
        raise ValueError("player_id does not match this guest")
    return match_id, guest_id


def _emit_to_match(matchmaking_service, match, event: str, payload: dict) -> None:
    for guest_id in (match.player_a_id, match.player_b_id):
        guest = matchmaking_service.get_guest(guest_id)
        if guest and guest.socket_id:
            socketio.emit(event, payload, to=guest.socket_id)


def _error(code: str, message: str) -> dict:
    socketio.emit(
        "transcription:error", {"code": code, "message": message}, to=request.sid
    )
    return {"ok": False, "error": {"code": code, "message": message}}
