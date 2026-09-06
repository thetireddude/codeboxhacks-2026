"""Socket.IO outbound payload builders."""

from __future__ import annotations

from app.models import Guest, MatchState


def match_found_payload(match: MatchState, player: Guest, opponent: Guest) -> dict:
    slot = "A" if player.guest_id == match.player_a_id else "B"
    return {
        "match_id": str(match.match_id),
        "player_id": slot,
        "opponent": {
            "guest_id": str(opponent.guest_id),
            "display_name": opponent.display_name,
        },
        "state": match.model_dump(mode="json"),
    }


def match_error_payload(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def guest_created_payload(guest: Guest) -> dict:
    return {
        "guest_id": str(guest.guest_id),
        "display_name": guest.display_name,
    }
