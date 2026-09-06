import time
from uuid import UUID

from app import create_app, socketio
from app.config import AppConfig
from app.models import MatchStatus


class FastRoundConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True
    COUNTDOWN_DURATION_MS = 10
    ROUND_DURATION_MS = 80


class SwitchRoundConfig(FastRoundConfig):
    ROUND_DURATION_MS = 1_000


def _new_guest(client):
    response = client.emit("guest:create", {}, callback=True)
    assert response["ok"] is True
    return response["guest"]


def _paired_clients(config=FastRoundConfig):
    app = create_app(config)
    first_client = socketio.test_client(app)
    second_client = socketio.test_client(app)
    first_guest = _new_guest(first_client)
    second_guest = _new_guest(second_client)
    first_client.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    )
    paired = second_client.emit(
        "queue:join", {"guest_id": second_guest["guest_id"]}, callback=True
    )
    first_client.get_received()
    second_client.get_received()
    return (
        app,
        first_client,
        second_client,
        first_guest,
        second_guest,
        paired["match_id"],
    )


def _wait_for(client, event_name, timeout_seconds=1):
    deadline = time.monotonic() + timeout_seconds
    received = []
    while time.monotonic() < deadline:
        received.extend(client.get_received())
        for event in received:
            if event["name"] == event_name:
                return event["args"][0]
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {event_name}; received {received}")


def _wait_for_state(app, guest_id, state, timeout_seconds=1):
    deadline = time.monotonic() + timeout_seconds
    service = app.extensions["matchmaking_service"]
    while time.monotonic() < deadline:
        match = service.get_match_for_guest(UUID(guest_id))
        if match and match.state == state:
            return match
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for state {state}")


def test_ready_countdown_turns_and_authoritative_round_end():
    (
        app,
        first_client,
        second_client,
        first_guest,
        second_guest,
        match_id,
    ) = _paired_clients()

    assert first_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": True, "state": "READY"}
    assert second_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    ) == {"ok": True, "state": "COUNTDOWN"}

    prepare = _wait_for(first_client, "round:prepare")
    assert prepare["match_id"] == match_id
    assert prepare["scenario"]["tone"] == "wacky"
    started = _wait_for(first_client, "round:start")
    assert started["active_player_id"] == "A"
    assert started["duration_ms"] == FastRoundConfig.ROUND_DURATION_MS

    assert second_client.emit(
        "turn:complete",
        {"match_id": match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    ) == {"ok": False}
    assert first_client.emit(
        "turn:complete",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": True, "active_player_id": "B"}
    assert _wait_for(second_client, "turn:changed")["active_player_id"] == "B"
    assert _wait_for(first_client, "round:end")["match_id"] == match_id

    _wait_for_state(app, first_guest["guest_id"], MatchStatus.SCORING)
    assert first_client.emit(
        "turn:complete",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": False}


def test_disconnect_stops_an_active_round_and_notifies_opponent():
    (
        app,
        first_client,
        second_client,
        first_guest,
        second_guest,
        match_id,
    ) = _paired_clients()
    first_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    )
    second_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    )
    _wait_for(first_client, "round:start")

    first_client.disconnect()
    disconnected = _wait_for(second_client, "player:disconnected")
    assert disconnected["player_id"] == "A"
    _wait_for_state(app, second_guest["guest_id"], MatchStatus.ROUND_END)


def test_listener_switches_are_broadcast_repeatable_and_idempotent():
    (
        app,
        first_client,
        second_client,
        first_guest,
        second_guest,
        match_id,
    ) = _paired_clients(SwitchRoundConfig)
    first_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    )
    second_client.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    )
    _wait_for(first_client, "round:start")
    second_client.get_received()

    first_switch = second_client.emit(
        "switch:press",
        {
            "match_id": match_id,
            "guest_id": second_guest["guest_id"],
            "request_id": "switch-request-1",
        },
        callback=True,
    )
    assert first_switch["ok"] is True
    assert first_switch["replayed"] is False
    assert first_switch["event"]["from_player_id"] == "B"
    assert first_switch["event"]["target_player_id"] == "A"
    assert first_switch["switches_remaining"] == {"A": 5, "B": 4}
    assert _wait_for(first_client, "switch:triggered")["event"] == first_switch["event"]

    replay = second_client.emit(
        "switch:press",
        {
            "match_id": match_id,
            "guest_id": second_guest["guest_id"],
            "request_id": "switch-request-1",
        },
        callback=True,
    )
    assert replay["ok"] is True
    assert replay["replayed"] is True
    assert replay["event"] == first_switch["event"]
    assert replay["switches_remaining"] == {"A": 5, "B": 4}

    owner_attempt = first_client.emit(
        "switch:press",
        {
            "match_id": match_id,
            "guest_id": first_guest["guest_id"],
            "request_id": "owner-request",
        },
        callback=True,
    )
    assert owner_attempt == {"ok": False, "code": "NOT_LISTENER"}
    assert _wait_for(first_client, "switch:rejected")["code"] == "NOT_LISTENER"

    for request_number in range(2, 6):
        response = second_client.emit(
            "switch:press",
            {
                "match_id": match_id,
                "guest_id": second_guest["guest_id"],
                "request_id": f"switch-request-{request_number}",
            },
            callback=True,
        )
        assert response["ok"] is True

    exhausted = second_client.emit(
        "switch:press",
        {
            "match_id": match_id,
            "guest_id": second_guest["guest_id"],
            "request_id": "switch-request-6",
        },
        callback=True,
    )
    assert exhausted == {"ok": False, "code": "NO_SWITCHES_REMAINING"}
    assert _wait_for(second_client, "switch:rejected")["switches_remaining"] == {
        "A": 5,
        "B": 0,
    }

    match = app.extensions["matchmaking_service"].get_match_for_guest(
        UUID(first_guest["guest_id"])
    )
    assert match.active_player_id == "A"
    assert len(match.transcript_events) == 5
    assert all(event.type == "switch" for event in match.transcript_events)

    _wait_for(first_client, "round:end", timeout_seconds=2)
    after_round = second_client.emit(
        "switch:press",
        {
            "match_id": match_id,
            "guest_id": second_guest["guest_id"],
            "request_id": "after-round-request",
        },
        callback=True,
    )
    assert after_round == {"ok": False, "code": "ROUND_NOT_ACTIVE"}
    assert _wait_for(second_client, "switch:rejected")["code"] == "ROUND_NOT_ACTIVE"
