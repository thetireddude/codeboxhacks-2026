"""Socket.IO handlers for anonymous public matchmaking."""

from __future__ import annotations

from uuid import UUID

from flask import request

from app import socketio
from app.services.matchmaking_service import MatchmakingError, MatchmakingService
from app.services.redis_service import StorageUnavailableError
from app.views.socket_views import (
    guest_created_payload,
    match_error_payload,
    match_found_payload,
)


def register_matchmaking_handlers(
    service: MatchmakingService, socket_guests: dict[str, str]
) -> None:
    @socketio.on("guest:create")
    def create_guest(payload: dict | None = None) -> dict:
        try:
            guest_id = _optional_uuid((payload or {}).get("guest_id"))
            guest = service.create_guest(request.sid, guest_id)
            socket_guests[request.sid] = str(guest.guest_id)
            return {"ok": True, "guest": guest_created_payload(guest)}
        except (MatchmakingError, ValueError) as error:
            return {
                "ok": False,
                "error": match_error_payload("INVALID_PAYLOAD", str(error)),
            }
        except StorageUnavailableError:
            return {
                "ok": False,
                "error": match_error_payload(
                    "STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable"
                ),
            }

    @socketio.on("queue:join")
    def join_queue(payload: dict | None) -> dict:
        try:
            guest_id = _required_uuid(payload)
            status, match = service.join_queue(guest_id, request.sid)
            if match is None:
                return {"ok": True, "status": status}
            _emit_match_found(service, match)
            return {"ok": True, "status": status, "match_id": str(match.match_id)}
        except (MatchmakingError, ValueError) as error:
            error_payload = match_error_payload("INVALID_PAYLOAD", str(error))
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}
        except StorageUnavailableError:
            error_payload = match_error_payload(
                "STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable"
            )
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}

    @socketio.on("queue:leave")
    def leave_queue(payload: dict | None) -> dict:
        try:
            guest_id = _required_uuid(payload)
            return {"ok": True, "removed": service.leave_queue(guest_id, request.sid)}
        except (MatchmakingError, ValueError) as error:
            _emit_error("INVALID_PAYLOAD", str(error))
            return {"ok": False}
        except StorageUnavailableError:
            _emit_error("STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable")
            return {"ok": False}

    @socketio.on("match:cancel")
    def cancel_match(payload: dict | None) -> dict:
        try:
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            guest_id = _required_uuid(payload)
            match_id = UUID(str(payload["match_id"]))
            match = service.cancel_unstarted_match(guest_id, request.sid, match_id)
            if match is not None:
                _emit_match_cancelled(service, match)
            # Cancellation is idempotent; a retry after a lost ack is harmless.
            return {"ok": True, "cancelled": match is not None}
        except (KeyError, MatchmakingError, ValueError) as error:
            error_payload = match_error_payload("INVALID_PAYLOAD", str(error))
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}
        except StorageUnavailableError:
            error_payload = match_error_payload("STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable")
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}

    @socketio.on("match:requeue")
    def requeue_match(payload: dict | None) -> dict:
        try:
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            guest_id = _required_uuid(payload)
            match_id = UUID(str(payload["match_id"]))
            status, match = service.requeue_completed_match(guest_id, request.sid, match_id)
            if match is not None:
                _emit_match_found(service, match)
                return {"ok": True, "status": "paired", "match_id": str(match.match_id)}
            return {"ok": True, "status": status}
        except (KeyError, MatchmakingError, ValueError) as error:
            error_payload = match_error_payload("INVALID_PAYLOAD", str(error))
            error_payload["match_id"] = str((payload or {}).get("match_id", ""))
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}
        except StorageUnavailableError:
            error_payload = match_error_payload("STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable")
            _emit_error(**error_payload)
            return {"ok": False, "error": error_payload}

    @socketio.on("match:leave")
    def leave_completed_match(payload: dict | None) -> dict:
        try:
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            guest_id = _required_uuid(payload)
            match_id = UUID(str(payload["match_id"]))
            service.leave_completed_match(guest_id, request.sid, match_id)
            return {"ok": True}
        except (KeyError, MatchmakingError, ValueError) as error:
            _emit_error("INVALID_PAYLOAD", str(error))
            return {"ok": False}
        except StorageUnavailableError:
            _emit_error("STORAGE_UNAVAILABLE", "Matchmaking is temporarily unavailable")
            return {"ok": False}


def _emit_match_found(service: MatchmakingService, match) -> None:
    player_a = service.get_guest(match.player_a_id)
    player_b = service.get_guest(match.player_b_id)
    if player_a is None or player_b is None:
        raise RuntimeError("Matched guests were not found")
    socketio.emit(
        "match:found",
        match_found_payload(match, player_a, player_b),
        to=player_a.socket_id,
    )
    socketio.emit(
        "match:found",
        match_found_payload(match, player_b, player_a),
        to=player_b.socket_id,
    )


def _emit_match_cancelled(service: MatchmakingService, match) -> None:
    payload = {
        "match_id": str(match.match_id),
        "message": "This match was cancelled before either player was ready.",
    }
    for guest_id in (match.player_a_id, match.player_b_id):
        guest = service.get_guest(guest_id)
        if guest is not None and guest.socket_id:
            socketio.emit("match:cancelled", payload, to=guest.socket_id)


def _emit_error(code: str, message: str) -> None:
    socketio.emit("match:error", match_error_payload(code, message), to=request.sid)


def _required_uuid(payload: dict | None) -> UUID:
    if not isinstance(payload, dict) or not payload.get("guest_id"):
        raise ValueError("guest_id is required")
    return UUID(str(payload["guest_id"]))


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value else None
