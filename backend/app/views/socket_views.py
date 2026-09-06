"""Socket.IO outbound payload builders."""

from __future__ import annotations

from uuid import UUID

from app.models import Guest, MatchState, SwitchEvent


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


def round_prepare_payload(match: MatchState, starts_at: str) -> dict:
    return {
        "match_id": str(match.match_id),
        "scenario": match.scenario.model_dump(mode="json") if match.scenario else None,
        "starts_at": starts_at,
    }


def round_start_payload(match: MatchState, duration_ms: int) -> dict:
    return {
        "match_id": str(match.match_id),
        "started_at": match.round_started_at.isoformat(),
        "duration_ms": duration_ms,
        "active_player_id": match.active_player_id,
        "switches_remaining": match.switches_remaining.model_dump(),
    }


def turn_changed_payload(match: MatchState, timestamp_ms: int) -> dict:
    return {
        "match_id": str(match.match_id),
        "active_player_id": match.active_player_id,
        "timestamp_ms": timestamp_ms,
    }


def switch_triggered_payload(
    match: MatchState, event: SwitchEvent, request_id: str
) -> dict:
    return {
        "match_id": str(match.match_id),
        "event": event.model_dump(mode="json"),
        "switches_remaining": match.switches_remaining.model_dump(),
        "request_id": request_id,
    }


def switch_rejected_payload(
    match_id: UUID, code: str, message: str, request_id: str | None, inventory: dict
) -> dict:
    return {
        "match_id": str(match_id),
        "code": code,
        "message": message,
        "request_id": request_id,
        "switches_remaining": inventory,
    }


def round_end_payload(match: MatchState, ended_at: str) -> dict:
    return {
        "match_id": str(match.match_id),
        "ended_at": ended_at,
        "transcript_events": [
            event.model_dump(mode="json") for event in match.transcript_events
        ],
    }


def results_ready_payload(results) -> dict:
    return {
        "match_id": str(results.match_id),
        "results": results.model_dump(mode="json"),
    }


def transcript_event_payload(match: MatchState, event) -> dict:
    return {
        "match_id": str(match.match_id),
        "event": event.model_dump(mode="json"),
    }
