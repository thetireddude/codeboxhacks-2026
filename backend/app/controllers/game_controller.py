"""Socket.IO handlers for the authoritative B2 game lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from flask import request

from app import socketio
from app.services.game_service import GameService, GameStateError
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import StorageUnavailableError
from app.views.socket_views import (
    match_error_payload,
    round_end_payload,
    round_prepare_payload,
    round_start_payload,
    turn_changed_payload,
)


def register_game_handlers(
    game_service: GameService,
    matchmaking_service: MatchmakingService,
    socket_guests: dict[str, str],
    countdown_duration_ms: int,
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
        match = game_service.end_round(match_id)
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
