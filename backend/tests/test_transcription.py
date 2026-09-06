import time
from uuid import UUID

from app import create_app, socketio
from app.config import AppConfig
from app.models import MatchStatus
from app.services.transcription_service import TranscriptionSession


class FakeSession(TranscriptionSession):
    instances = []

    def __init__(self, *, callbacks, **_kwargs):
        self.callbacks = callbacks
        self.audio = []
        self.stopped = False
        self.instances.append(self)

    def send_audio(self, audio: bytes) -> None:
        self.audio.append(audio)

    def stop(self) -> None:
        self.stopped = True


class TestConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True
    DEEPGRAM_API_KEY = "test-key"
    TRANSCRIPTION_SESSION_FACTORY = FakeSession


class MatchTranscriptionConfig(TestConfig):
    COUNTDOWN_DURATION_MS = 10
    ROUND_DURATION_MS = 1_000


def _client():
    FakeSession.instances.clear()
    return socketio.test_client(create_app(TestConfig))


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


def test_final_match_speech_is_persisted_broadcast_and_completes_turn():
    FakeSession.instances.clear()
    app = create_app(MatchTranscriptionConfig)
    player_a = socketio.test_client(app)
    player_b = socketio.test_client(app)
    guest_a = player_a.emit("guest:create", {}, callback=True)["guest"]
    guest_b = player_b.emit("guest:create", {}, callback=True)["guest"]
    player_a.emit("queue:join", {"guest_id": guest_a["guest_id"]}, callback=True)
    paired = player_b.emit(
        "queue:join", {"guest_id": guest_b["guest_id"]}, callback=True
    )
    match_id = paired["match_id"]
    player_a.get_received()
    player_b.get_received()
    player_a.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": guest_a["guest_id"]},
        callback=True,
    )
    player_b.emit(
        "player:ready",
        {"match_id": match_id, "guest_id": guest_b["guest_id"]},
        callback=True,
    )
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        match = app.extensions["matchmaking_service"].get_match_for_guest(
            UUID(guest_a["guest_id"])
        )
        if match and match.state is MatchStatus.ROUND_ACTIVE:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("Round did not start")

    player_a.get_received()
    player_b.get_received()
    response = player_a.emit(
        "transcription:start",
        {"player_id": "A", "match_id": match_id},
        callback=True,
    )
    assert response["ok"] is True
    session = FakeSession.instances[0]
    session.callbacks.on_started("speech_b5")
    session.callbacks.on_final("speech_b5", "We should read the manual.")

    received = player_b.get_received()
    transcript = next(
        event for event in received if event["name"] == "transcript:event"
    )
    assert transcript["args"][0]["event"]["text"] == "We should read the manual."
    assert any(event["name"] == "turn:changed" for event in received)
    match = app.extensions["matchmaking_service"].get_match_for_guest(
        UUID(guest_a["guest_id"])
    )
    assert match.active_player_id == "B"
    assert match.transcript_events[-1].id == "speech_b5"
