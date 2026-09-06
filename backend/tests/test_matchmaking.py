from app import create_app, socketio
from app.config import AppConfig


class TestConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True


def _new_guest(client):
    response = client.emit("guest:create", {}, callback=True)
    assert response["ok"] is True
    return response["guest"]


def test_two_guests_pair_and_receive_complementary_match_payloads():
    app = create_app(TestConfig)
    first_client = socketio.test_client(app)
    second_client = socketio.test_client(app)

    first_guest = _new_guest(first_client)
    second_guest = _new_guest(second_client)

    assert first_client.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    ) == {"ok": True, "status": "waiting"}
    paired = second_client.emit(
        "queue:join", {"guest_id": second_guest["guest_id"]}, callback=True
    )

    assert paired["ok"] is True
    assert paired["status"] == "paired"
    first_match = first_client.get_received()[-1]
    second_match = second_client.get_received()[-1]
    assert first_match["name"] == second_match["name"] == "match:found"
    first_payload = first_match["args"][0]
    second_payload = second_match["args"][0]
    assert first_payload["match_id"] == second_payload["match_id"] == paired["match_id"]
    assert first_payload["player_id"] == "A"
    assert second_payload["player_id"] == "B"
    assert first_payload["state"]["state"] == "MATCH_FOUND"
    assert first_payload["state"]["switches_remaining"] == {"A": 5, "B": 5}


def test_duplicate_join_is_idempotent_and_queue_leave_removes_guest():
    app = create_app(TestConfig)
    client = socketio.test_client(app)
    guest = _new_guest(client)
    payload = {"guest_id": guest["guest_id"]}

    assert client.emit("queue:join", payload, callback=True) == {
        "ok": True,
        "status": "waiting",
    }
    assert client.emit("queue:join", payload, callback=True) == {
        "ok": True,
        "status": "queued",
    }
    assert client.emit("queue:leave", payload, callback=True) == {
        "ok": True,
        "removed": True,
    }
    assert client.emit("queue:join", payload, callback=True) == {
        "ok": True,
        "status": "waiting",
    }


def test_queue_rejects_guest_identity_from_a_different_socket():
    app = create_app(TestConfig)
    owner = socketio.test_client(app)
    intruder = socketio.test_client(app)
    guest = _new_guest(owner)

    response = intruder.emit(
        "queue:join", {"guest_id": guest["guest_id"]}, callback=True
    )

    assert response == {"ok": False}
    error = intruder.get_received()[-1]
    assert error["name"] == "match:error"
    assert error["args"][0]["code"] == "INVALID_PAYLOAD"
