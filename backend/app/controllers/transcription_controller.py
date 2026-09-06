"""Socket.IO entry points for the A2 live speech-to-text stream."""

from __future__ import annotations

from uuid import UUID

from flask import request

from app import socketio
from app.services.game_service import GameService, GameStateError
from app.services.matchmaking_service import MatchmakingService
from app.services.transcript_service import TranscriptService
from app.services.transcription_service import (
    TranscriptionCallbacks,
    TranscriptionError,
    TranscriptionService,
)


def register_transcription_handlers(
    service: TranscriptionService,
    transcript_service: TranscriptService,
    game_service: GameService,
    matchmaking_service: MatchmakingService,
) -> None:
    @socketio.on("transcription:start")
    def start_transcription(payload: dict | None) -> dict:
        player_id = (payload or {}).get("player_id")
        if player_id not in ("A", "B"):
            return _error("INVALID_PAYLOAD", "player_id must be A or B")
        try:
            context = _authoritative_context(payload, game_service, matchmaking_service)
            if context is not None:
                match_id, guest_id, player_id = context
            service.start_stream(
                request.sid,
                player_id,
                _callbacks(
                    request.sid,
                    player_id,
                    context,
                    transcript_service,
                    matchmaking_service,
                ),
            )
        except (GameStateError, TranscriptionError, ValueError) as error:
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
    context: tuple[UUID, UUID, str] | None,
    transcript_service: TranscriptService,
    matchmaking_service: MatchmakingService,
) -> TranscriptionCallbacks:
    def started(speech_id: str) -> None:
        if context is not None:
            try:
                transcript_service.speech_started(context[0], context[1], speech_id)
            except GameStateError as error:
                _emit_transcription_error(socket_id, "ROUND_NOT_ACTIVE", str(error))
                return
        socketio.emit(
            "speech:started",
            {"player_id": player_id, "speech_id": speech_id},
            to=socket_id,
        )

    def final(speech_id: str, text: str) -> None:
        if context is None:
            socketio.emit(
                "speech:final",
                {"player_id": player_id, "speech_id": speech_id, "text": text},
                to=socket_id,
            )
            return
        try:
            match, event = transcript_service.speech_final(speech_id, text)
        except GameStateError as error:
            _emit_transcription_error(socket_id, "ROUND_NOT_ACTIVE", str(error))
            return
        socketio.emit(
            "speech:final",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        )
        for guest_id in (match.player_a_id, match.player_b_id):
            guest = matchmaking_service.get_guest(guest_id)
            if guest and guest.socket_id:
                socketio.emit(
                    "transcript:event",
                    {
                        "match_id": str(match.match_id),
                        "event": event.model_dump(mode="json"),
                    },
                    to=guest.socket_id,
                )
                socketio.emit(
                    "turn:changed",
                    {
                        "match_id": str(match.match_id),
                        "active_player_id": match.active_player_id,
                        "timestamp_ms": event.end_ms,
                    },
                    to=guest.socket_id,
                )

    def partial(speech_id: str, text: str) -> None:
        if context is not None:
            try:
                transcript_service.speech_partial(speech_id, text)
            except GameStateError as error:
                _emit_transcription_error(socket_id, "ROUND_NOT_ACTIVE", str(error))
                return
        socketio.emit(
            "speech:partial",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        )

    return TranscriptionCallbacks(
        on_started=started,
        on_partial=partial,
        on_final=final,
        on_error=lambda code, message: socketio.emit(
            "transcription:error", {"code": code, "message": message}, to=socket_id
        ),
    )


def _authoritative_context(
    payload: dict | None,
    game_service: GameService,
    matchmaking_service: MatchmakingService,
) -> tuple[UUID, UUID, str] | None:
    if not isinstance(payload, dict) or not payload.get("match_id"):
        return None
    if not payload.get("guest_id"):
        raise ValueError("guest_id is required when match_id is provided")
    match_id = UUID(str(payload["match_id"]))
    guest_id = UUID(str(payload["guest_id"]))
    guest = matchmaking_service.get_guest(guest_id)
    if guest is None or guest.socket_id != request.sid:
        raise ValueError("Guest is not connected from this socket")
    match = matchmaking_service.get_match_for_guest(guest_id)
    if match is None or match.match_id != match_id:
        raise ValueError("Guest is not in this match")
    player_id, _ = game_service.begin_speech(match_id, guest_id)
    return match_id, guest_id, player_id


def _emit_transcription_error(socket_id: str, code: str, message: str) -> None:
    socketio.emit(
        "transcription:error", {"code": code, "message": message}, to=socket_id
    )


def _error(code: str, message: str) -> dict:
    socketio.emit(
        "transcription:error", {"code": code, "message": message}, to=request.sid
    )
    return {"ok": False, "error": {"code": code, "message": message}}
