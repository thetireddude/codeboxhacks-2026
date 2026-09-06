import time
from uuid import UUID

from app import create_app, socketio
from app.config import AppConfig
from app.services.transcription_service import TranscriptionSession


class FakeSession(TranscriptionSession):
    instances = []

    def __init__(self, *, callbacks, **_kwargs):
        self.callbacks = callbacks
        self.audio = []
        self.stopped = False
        self.turn_end_silence_ms = _kwargs["turn_end_silence_ms"]
        self.instances.append(self)

    def send_audio(self, audio: bytes) -> None:
        self.audio.append(audio)

    def stop(self) -> None:
        self.stopped = True


class TestConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True
    DEEPGRAM_API_KEY = "test-key"
    TURN_END_SILENCE_MS = 750
    TRANSCRIPTION_SESSION_FACTORY = FakeSession


class AuthoritativeTestConfig(TestConfig):
    COUNTDOWN_DURATION_MS = 10
    ROUND_DURATION_MS = 2_000


def _client():
    FakeSession.instances.clear()
    return socketio.test_client(create_app(TestConfig))


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


def test_pcm_audio_is_forwarded_and_provider_events_reach_the_same_socket():
    client = _client()

    assert client.emit("transcription:start", {"player_id": "A"}, callback=True) == {
        "ok": True,
        "sample_rate": 16000,
        "chunk_ms": 80,
        "max_chunk_bytes": 2560,
    }
    assert client.emit("transcription:audio", b"\x00" * 2560, callback=True) == {
        "ok": True
    }
    session = FakeSession.instances[0]
    assert session.audio == [b"\x00" * 2560]
    assert session.turn_end_silence_ms == 750

    session.callbacks.on_started("speech_demo")
    session.callbacks.on_partial("speech_demo", "Hello")
    session.callbacks.on_final("speech_demo", "Hello there")

    received = client.get_received()
    assert [(event["name"], event["args"][0]) for event in received] == [
        ("speech:started", {"player_id": "A", "speech_id": "speech_demo"}),
        (
            "speech:partial",
            {"player_id": "A", "speech_id": "speech_demo", "text": "Hello"},
        ),
        (
            "speech:final",
            {"player_id": "A", "speech_id": "speech_demo", "text": "Hello there"},
        ),
    ]


def test_audio_requires_an_active_stream_and_stays_within_the_pcm_chunk_limit():
    client = _client()

    response = client.emit("transcription:audio", b"\x00", callback=True)
    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_AUDIO"

    assert client.emit("transcription:start", {"player_id": "B"}, callback=True)["ok"]
    response = client.emit("transcription:audio", b"\x00" * 2561, callback=True)
    assert response["ok"] is False
    assert "2560-byte limit" in response["error"]["message"]


def test_start_rejects_an_unknown_mock_player():
    client = _client()

    response = client.emit("transcription:start", {"player_id": "C"}, callback=True)

    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_PAYLOAD"


def test_final_speech_is_persisted_broadcast_and_changes_authoritative_turn():
    FakeSession.instances.clear()
    app = create_app(AuthoritativeTestConfig)
    first_client = socketio.test_client(app)
    second_client = socketio.test_client(app)
    first_guest = first_client.emit("guest:create", {}, callback=True)["guest"]
    second_guest = second_client.emit("guest:create", {}, callback=True)["guest"]
    first_client.emit(
        "queue:join", {"guest_id": first_guest["guest_id"]}, callback=True
    )
    paired = second_client.emit(
        "queue:join", {"guest_id": second_guest["guest_id"]}, callback=True
    )
    match_id = paired["match_id"]
    first_client.get_received()
    second_client.get_received()
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

    response = first_client.emit(
        "transcription:start",
        {
            "player_id": "B",
            "match_id": match_id,
            "guest_id": first_guest["guest_id"],
        },
        callback=True,
    )
    assert response["ok"] is True
    session = FakeSession.instances[0]
    session.callbacks.on_started("speech_live")
    session.callbacks.on_partial("speech_live", "Hello")
    session.callbacks.on_final("speech_live", "Hello there")

    first_events = first_client.get_received()
    assert next(
        event for event in first_events if event["name"] == "speech:started"
    )["args"][0]["player_id"] == "A"
    first_transcript = next(
        event for event in first_events if event["name"] == "transcript:event"
    )["args"][0]
    second_events = second_client.get_received()
    second_transcript = next(
        event for event in second_events if event["name"] == "transcript:event"
    )["args"][0]

    assert first_transcript == second_transcript
    assert first_transcript["event"]["text"] == "Hello there"
    assert first_transcript["event"]["player_id"] == "A"
    assert next(
        event for event in second_events if event["name"] == "turn:changed"
    )["args"][0]["active_player_id"] == "B"
    match = app.extensions["matchmaking_service"].get_match_for_guest(
        UUID(first_guest["guest_id"])
    )
    assert match.active_player_id == "B"
    assert [event.id for event in match.transcript_events] == ["speech_live"]


def test_match_context_requires_guest_id_instead_of_raising_a_server_error():
    client = _client()

    response = client.emit(
        "transcription:start",
        {"player_id": "A", "match_id": "00000000-0000-0000-0000-000000000000"},
        callback=True,
    )

    assert response["ok"] is False
    assert response["error"] == {
        "code": "STT_UNAVAILABLE",
        "message": "guest_id is required when match_id is provided",
    }
