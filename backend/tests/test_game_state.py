import time
from uuid import UUID

from app import create_app, socketio
from app.config import AppConfig
from app.models import GuestStatus, MatchStatus
from app.services.judge_service import JudgeError


class FastRoundConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True
    COUNTDOWN_DURATION_MS = 10
    ROUND_DURATION_MS = 80


class SwitchRoundConfig(FastRoundConfig):
    ROUND_DURATION_MS = 1_000


class CleanupRoundConfig(FastRoundConfig):
    MATCH_CLEANUP_DELAY_MS = 10


class RequeueCleanupRoundConfig(FastRoundConfig):
    MATCH_CLEANUP_DELAY_MS = 100


class ResultDisconnectGraceConfig(FastRoundConfig):
    MATCH_CLEANUP_DELAY_MS = 10_000
    RESULT_DISCONNECT_GRACE_MS = 10


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
    opponent_prepare = _wait_for(second_client, "round:prepare")
    assert prepare["match_id"] == match_id
    assert prepare["scenario"]["tone"] == "wacky"
    assert opponent_prepare["scenario"] == prepare["scenario"]
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

    results = _wait_for(second_client, "results:ready")
    assert results["match_id"] == match_id
    assert results["results"]["winner"] == "TIE"
    _wait_for_state(app, first_guest["guest_id"], MatchStatus.RESULTS)
    assert first_client.emit(
        "turn:complete",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": False}


def test_judge_failure_still_returns_objective_round_results():
    app, first_client, second_client, first_guest, second_guest, match_id = (
        _paired_clients()
    )

    class FailingJudge:
        def judge(self, _judge_input):
            raise JudgeError("provider timeout")

    app.extensions["match_integration_service"]._judge_service = FailingJudge()
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

    first_results = _wait_for(first_client, "results:ready")
    second_results = _wait_for(second_client, "results:ready")
    assert first_results == second_results
    assert first_results["results"]["player_a"]["highlight"].startswith(
        "Gemini feedback was unavailable"
    )
    assert first_results["results"]["player_a"]["category_points"]["speed"] == 0
    _wait_for_state(app, first_guest["guest_id"], MatchStatus.RESULTS)


def test_reconnecting_player_receives_the_retained_final_results():
    app, first_client, second_client, first_guest, second_guest, match_id = (
        _paired_clients()
    )
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
    original_results = _wait_for(first_client, "results:ready")
    _wait_for(second_client, "results:ready")

    first_client.disconnect()
    reconnecting_client = socketio.test_client(app)
    restored = reconnecting_client.emit(
        "guest:create", {"guest_id": first_guest["guest_id"]}, callback=True
    )
    assert restored["ok"] is True
    assert reconnecting_client.emit(
        "match:resume",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": True, "state": "RESULTS"}
    assert _wait_for(reconnecting_client, "results:ready") == original_results


def test_both_disconnected_players_are_released_after_result_grace_period():
    app, first_client, second_client, first_guest, second_guest, _match_id = (
        _paired_clients(ResultDisconnectGraceConfig)
    )
    first_client.emit(
        "player:ready",
        {"match_id": _match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    )
    second_client.emit(
        "player:ready",
        {"match_id": _match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    )
    _wait_for(first_client, "results:ready")
    _wait_for(second_client, "results:ready")

    first_client.disconnect()
    second_client.disconnect()

    deadline = time.monotonic() + 1
    service = app.extensions["matchmaking_service"]
    while time.monotonic() < deadline:
        if service.get_match_for_guest(UUID(first_guest["guest_id"])) is None:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("Abandoned retained result was not released")

    first_reconnect = socketio.test_client(app)
    second_reconnect = socketio.test_client(app)
    assert first_reconnect.emit(
        "guest:create", {"guest_id": first_guest["guest_id"]}, callback=True
    )["ok"] is True
    assert second_reconnect.emit(
        "guest:create", {"guest_id": second_guest["guest_id"]}, callback=True
    )["ok"] is True
    assert first_reconnect.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    ) == {"ok": True, "status": "waiting"}
    assert second_reconnect.emit(
        "queue:join", {"guest_id": second_guest["guest_id"]}, callback=True
    )["status"] == "paired"


def test_player_can_leave_results_and_requeue_without_releasing_opponent_results():
    app, first_client, second_client, first_guest, second_guest, match_id = (
        _paired_clients()
    )
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
    _wait_for(first_client, "results:ready")
    _wait_for(second_client, "results:ready")

    assert first_client.emit(
        "match:leave",
        {"match_id": match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": True}

    service = app.extensions["matchmaking_service"]
    assert service.get_match_for_guest(UUID(first_guest["guest_id"])) is None
    assert service.get_match_for_guest(UUID(second_guest["guest_id"])) is not None
    assert first_client.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    ) == {"ok": True, "status": "waiting"}


def test_old_result_cleanup_does_not_release_a_player_new_match():
    app, first_client, second_client, first_guest, second_guest, old_match_id = (
        _paired_clients(RequeueCleanupRoundConfig)
    )
    first_client.emit(
        "player:ready",
        {"match_id": old_match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    )
    second_client.emit(
        "player:ready",
        {"match_id": old_match_id, "guest_id": second_guest["guest_id"]},
        callback=True,
    )
    _wait_for(first_client, "results:ready")
    _wait_for(second_client, "results:ready")

    assert first_client.emit(
        "match:leave",
        {"match_id": old_match_id, "guest_id": first_guest["guest_id"]},
        callback=True,
    ) == {"ok": True}
    assert first_client.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    ) == {"ok": True, "status": "waiting"}

    third_client = socketio.test_client(app)
    third_guest = _new_guest(third_client)
    new_match = third_client.emit(
        "queue:join", {"guest_id": third_guest["guest_id"]}, callback=True
    )
    assert new_match["ok"] is True
    assert new_match["match_id"] != old_match_id

    time.sleep(RequeueCleanupRoundConfig.MATCH_CLEANUP_DELAY_MS / 1000 + 0.1)
    service = app.extensions["matchmaking_service"]
    active_match = service.get_match_for_guest(UUID(first_guest["guest_id"]))
    assert active_match is not None
    assert str(active_match.match_id) == new_match["match_id"]
    assert service.get_guest(UUID(first_guest["guest_id"])).status == GuestStatus.MATCHED


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


def test_completed_match_state_is_cleaned_up_after_result_delivery():
    app, first_client, second_client, first_guest, second_guest, match_id = (
        _paired_clients(CleanupRoundConfig)
    )
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
    _wait_for(first_client, "results:ready")

    deadline = time.monotonic() + 1
    service = app.extensions["matchmaking_service"]
    while time.monotonic() < deadline:
        if service.get_match_for_guest(UUID(first_guest["guest_id"])) is None:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("Completed match was not cleaned up")
