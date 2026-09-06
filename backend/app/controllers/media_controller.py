"""HTTP and Socket.IO boundaries for match-scoped LiveKit credentials."""

from __future__ import annotations

from uuid import UUID

from flask import Flask, jsonify, request

from app import socketio
from app.services.livekit_service import LiveKitError, LiveKitService
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import StorageUnavailableError


def register_media_routes(
    app: Flask, service: LiveKitService, matchmaking_service: MatchmakingService
) -> None:
    @app.post("/api/matches/<uuid:match_id>/livekit-token")
    def livekit_token(match_id: UUID):
        payload = request.get_json(silent=True) or {}
        try:
            guest_id = UUID(str(payload["guest_id"]))
            credentials = _credentials_for(
                service, matchmaking_service, match_id, guest_id
            )
            return jsonify({"ok": True, "credentials": credentials.to_payload()})
        except (KeyError, TypeError, ValueError):
            return _error("INVALID_PAYLOAD", "guest_id must be a UUID", 400)
        except LiveKitError as error:
            return _error("LIVEKIT_UNAVAILABLE", str(error), 503)
        except StorageUnavailableError:
            return _error("STORAGE_UNAVAILABLE", "Match state is unavailable", 503)


def register_media_handlers(
    service: LiveKitService,
    matchmaking_service: MatchmakingService,
    socket_guests: dict[str, str],
) -> None:
    @socketio.on("media:credentials")
    def media_credentials(payload: dict | None) -> dict:
        try:
            match_id = UUID(str((payload or {})["match_id"]))
            guest_id = UUID(socket_guests[request.sid])
            credentials = _credentials_for(
                service, matchmaking_service, match_id, guest_id
            )
            return {"ok": True, "credentials": credentials.to_payload()}
        except (KeyError, TypeError, ValueError):
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_PAYLOAD",
                    "message": "match_id must be a UUID",
                },
            }
        except LiveKitError as error:
            return {
                "ok": False,
                "error": {"code": "LIVEKIT_UNAVAILABLE", "message": str(error)},
            }
        except StorageUnavailableError:
            return {
                "ok": False,
                "error": {
                    "code": "STORAGE_UNAVAILABLE",
                    "message": "Match state is unavailable",
                },
            }


def _credentials_for(
    service: LiveKitService,
    matchmaking_service: MatchmakingService,
    match_id: UUID,
    guest_id: UUID,
):
    if not service.is_configured:
        raise LiveKitError("LiveKit is not configured")
    guest = matchmaking_service.get_guest(guest_id)
    match = matchmaking_service.get_match_for_guest(guest_id)
    if guest is None or match is None or match.match_id != match_id:
        raise LiveKitError("Match participant was not found")
    return service.credentials_for(match, guest)


def _error(code: str, message: str, status: int):
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status
