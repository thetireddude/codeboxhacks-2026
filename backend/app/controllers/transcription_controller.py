"""Socket.IO entry points for the A2 live speech-to-text stream."""

from __future__ import annotations

from flask import request

from app import socketio
from app.services.transcription_service import (
    TranscriptionCallbacks,
    TranscriptionError,
    TranscriptionService,
)


def register_transcription_handlers(service: TranscriptionService) -> None:
    @socketio.on("transcription:start")
    def start_transcription(payload: dict | None) -> dict:
        player_id = (payload or {}).get("player_id")
        if player_id not in ("A", "B"):
            return _error("INVALID_PAYLOAD", "player_id must be A or B")
        try:
            service.start_stream(
                request.sid, player_id, _callbacks(request.sid, player_id)
            )
        except TranscriptionError as error:
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


def _callbacks(socket_id: str, player_id: str) -> TranscriptionCallbacks:
    return TranscriptionCallbacks(
        on_started=lambda speech_id: socketio.emit(
            "speech:started",
            {"player_id": player_id, "speech_id": speech_id},
            to=socket_id,
        ),
        on_partial=lambda speech_id, text: socketio.emit(
            "speech:partial",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        ),
        on_final=lambda speech_id, text: socketio.emit(
            "speech:final",
            {"player_id": player_id, "speech_id": speech_id, "text": text},
            to=socket_id,
        ),
        on_error=lambda code, message: socketio.emit(
            "transcription:error", {"code": code, "message": message}, to=socket_id
        ),
    )


def _error(code: str, message: str) -> dict:
    socketio.emit(
        "transcription:error", {"code": code, "message": message}, to=request.sid
    )
    return {"ok": False, "error": {"code": code, "message": message}}
