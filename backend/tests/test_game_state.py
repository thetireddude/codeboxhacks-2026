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


def _new_guest(client):
    response = client.emit("guest:create", {}, callback=True)
    assert response["ok"] is True
    return response["guest"]


def _paired_clients():
    app = create_app(FastRoundConfig)
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
