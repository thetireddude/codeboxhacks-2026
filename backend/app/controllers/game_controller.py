"""Socket.IO handlers for the authoritative B2/B3 game lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from flask import request

from app import socketio
from app.services.game_service import GameService, GameStateError, SwitchRejectedError
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import StorageUnavailableError
from app.services.transcript_service import TranscriptService
from app.services.transcription_service import TranscriptionService
from app.views.socket_views import (
    match_error_payload,
    round_end_payload,
    round_prepare_payload,
    round_start_payload,
    switch_rejected_payload,
    switch_triggered_payload,
    turn_changed_payload,
)


def register_game_handlers(
    game_service: GameService,
    matchmaking_service: MatchmakingService,
    socket_guests: dict[str, str],
    countdown_duration_ms: int,
    transcript_service: TranscriptService | None = None,
    transcription_service: TranscriptionService | None = None,
) -> None:
    @socketio.on("player:ready")
    def player_ready(payload: dict | None) -> dict:
        try:
            match_id, guest_id = _owned_match_payload(
                payload, matchmaking_service, request.sid
            )
            match, starts_countdown = game_service.player_ready(match_id, guest_id)
            if starts_countdown:
                starts_at = datetime.now(UTC) + timedelta(
                    milliseconds=countdown_duration_ms
                )
                _emit_to_match(
                    matchmaking_service,
                    match,
                    "round:prepare",
                    round_prepare_payload(match, starts_at.isoformat()),
                )
                socketio.start_background_task(
                    _run_round,
                    game_service,
                    matchmaking_service,
                    match_id,
                    countdown_duration_ms,
                    transcript_service,
                )
            return {"ok": True, "state": match.state.value}
        except (GameStateError, ValueError) as error:
            _emit_error("INVALID_PAYLOAD", str(error))
            return {"ok": False}
        except StorageUnavailableError:
            _emit_error("STORAGE_UNAVAILABLE", "Game state is temporarily unavailable")
            return {"ok": False}

    @socketio.on("turn:complete")
    def complete_turn(payload: dict | None) -> dict:
        try:
            match_id, guest_id = _owned_match_payload(
                payload, matchmaking_service, request.sid
            )
            match = game_service.complete_turn(match_id, guest_id)
            _emit_to_match(
                matchmaking_service,
                match,
                "turn:changed",
                turn_changed_payload(match, _elapsed_ms(match)),
            )
            return {"ok": True, "active_player_id": match.active_player_id}
        except (GameStateError, ValueError) as error:
            _emit_error("ROUND_NOT_ACTIVE", str(error))
            return {"ok": False}
        except StorageUnavailableError:
            _emit_error("STORAGE_UNAVAILABLE", "Game state is temporarily unavailable")
            return {"ok": False}

    @socketio.on("switch:press")
    def press_switch(payload: dict | None) -> dict:
        match_id: UUID | None = None
        request_id: str | None = None
        try:
            match_id, guest_id = _owned_match_payload(
                payload, matchmaking_service, request.sid
            )
            request_id = _required_request_id(payload)
            if transcript_service is None:
                match, event, is_replay = game_service.press_switch(
                    match_id, guest_id, request_id
                )
                interrupted = None
            else:
                match, event, is_replay, interrupted = transcript_service.press_switch(
                    match_id, guest_id, request_id
                )
            if not is_replay:
                if interrupted is not None:
                    _emit_to_match(
                        matchmaking_service,
                        match,
                        "transcript:event",
                        {
                            "match_id": str(match.match_id),
                            "event": interrupted.model_dump(mode="json"),
                        },
                    )
                target_guest_id = (
                    match.player_a_id
                    if event.target_player_id == "A"
                    else match.player_b_id
                )
                target_guest = matchmaking_service.get_guest(target_guest_id)
                if (
                    transcription_service is not None
                    and target_guest is not None
                    and target_guest.socket_id
                ):
                    transcription_service.interrupt_stream(target_guest.socket_id)
                _emit_to_match(
                    matchmaking_service,
                    match,
                    "switch:triggered",
                    switch_triggered_payload(match, event, request_id),
                )
            return {
                "ok": True,
                "event": event.model_dump(mode="json"),
                "switches_remaining": match.switches_remaining.model_dump(),
                "replayed": is_replay,
            }
        except SwitchRejectedError as error:
            _emit_switch_rejected(
                matchmaking_service,
                socket_guests,
                match_id,
                error.code,
                str(error),
                request_id,
            )
            return {"ok": False, "code": error.code}
        except (GameStateError, ValueError) as error:
            _emit_switch_rejected(
                matchmaking_service,
                socket_guests,
                match_id,
                "INVALID_PAYLOAD",
                str(error),
                request_id,
            )
            return {"ok": False, "code": "INVALID_PAYLOAD"}
        except StorageUnavailableError:
            _emit_switch_rejected(
                matchmaking_service,
                socket_guests,
                match_id,
                "STORAGE_UNAVAILABLE",
                "Game state is temporarily unavailable",
                request_id,
            )
            return {"ok": False, "code": "STORAGE_UNAVAILABLE"}

    @socketio.on("disconnect")
    def disconnect() -> None:
        guest_id_text = socket_guests.pop(request.sid, None)
        if not guest_id_text:
            return
        try:
            guest_id = UUID(guest_id_text)
            match = matchmaking_service.get_match_for_guest(guest_id)
            if match is None:
                return
            match = game_service.disconnect_player(match.match_id, guest_id)
            slot = "A" if match.player_a_id == guest_id else "B"
            _emit_to_match(
                matchmaking_service,
                match,
                "player:disconnected",
                {
                    "match_id": str(match.match_id),
                    "player_id": slot,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except (GameStateError, StorageUnavailableError, ValueError):
            return


def _run_round(
    game_service: GameService,
    matchmaking_service: MatchmakingService,
    match_id: UUID,
    countdown_duration_ms: int,
    transcript_service: TranscriptService | None,
) -> None:
    socketio.sleep(countdown_duration_ms / 1000)
    try:
        match = game_service.start_round(match_id)
        _emit_to_match(
            matchmaking_service,
            match,
            "round:start",
            round_start_payload(match, game_service.round_duration_ms),
        )
        socketio.sleep(game_service.round_duration_ms / 1000)
        truncated_events = (
            transcript_service.finalize_round(match_id)
            if transcript_service is not None
            else []
        )
        match = game_service.end_round(match_id)
        for event in truncated_events:
            _emit_to_match(
                matchmaking_service,
                match,
                "transcript:event",
                {
                    "match_id": str(match.match_id),
                    "event": event.model_dump(mode="json"),
                },
            )
        _emit_to_match(
            matchmaking_service,
            match,
            "round:end",
            round_end_payload(match, datetime.now(UTC).isoformat()),
        )
        game_service.begin_scoring(match_id)
    except (GameStateError, StorageUnavailableError):
        # A disconnect or already-ended match makes this scheduled task obsolete.
        return


def _owned_match_payload(
    payload: dict | None, matchmaking_service: MatchmakingService, socket_id: str
) -> tuple[UUID, UUID]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")
    match_id = UUID(str(payload["match_id"]))
    guest_id = UUID(str(payload["guest_id"]))
    guest = matchmaking_service.get_guest(guest_id)
    if guest is None or guest.socket_id != socket_id:
        raise ValueError("Guest is not connected from this socket")
    return match_id, guest_id


def _required_request_id(payload: dict | None) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("request_id"), str):
        raise ValueError("request_id is required")
    return payload["request_id"]


def _emit_to_match(
    matchmaking_service: MatchmakingService, match, event: str, payload: dict
) -> None:
    for guest_id in (match.player_a_id, match.player_b_id):
        guest = matchmaking_service.get_guest(guest_id)
        if guest and guest.socket_id:
            socketio.emit(event, payload, to=guest.socket_id)


def _elapsed_ms(match) -> int:
    if match.round_started_at is None:
        return 0
    return max(
        0,
        int((datetime.now(UTC) - match.round_started_at).total_seconds() * 1000),
    )


def _emit_error(code: str, message: str) -> None:
    socketio.emit("match:error", match_error_payload(code, message), to=request.sid)


def _emit_switch_rejected(
    matchmaking_service: MatchmakingService,
    socket_guests: dict[str, str],
    match_id: UUID | None,
    code: str,
    message: str,
    request_id: str | None,
) -> None:
    if match_id is None:
        _emit_error(code, message)
        return

    inventory = {"A": 0, "B": 0}
    guest_id_text = socket_guests.get(request.sid)
    if guest_id_text:
        match = matchmaking_service.get_match_for_guest(UUID(guest_id_text))
        if match is not None:
            inventory = match.switches_remaining.model_dump()
    socketio.emit(
        "switch:rejected",
        switch_rejected_payload(match_id, code, message, request_id, inventory),
        to=request.sid,
    )
