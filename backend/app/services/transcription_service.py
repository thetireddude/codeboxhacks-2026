"""Realtime PCM16 transcription through Deepgram Flux."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4

from app.models.transcript import PlayerSlot

PartialCallback = Callable[[str, str], None]
FinalCallback = Callable[[str, str], None]
StartedCallback = Callable[[str], None]
ErrorCallback = Callable[[str, str], None]
ReadyCallback = Callable[[], None]


class TranscriptionError(RuntimeError):
    """A live transcription stream could not be started or used."""


@dataclass(frozen=True)
class TranscriptionCallbacks:
    on_started: StartedCallback
    on_partial: PartialCallback
    on_final: FinalCallback
    on_error: ErrorCallback
    on_ready: ReadyCallback = lambda: None


class TranscriptionSession:
    """The small provider boundary used by the Socket.IO controller."""

    def send_audio(self, audio: bytes) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def interrupt(self) -> None:
        """Begin a new provider utterance after a successful Switch."""
        return None


class DeepgramSession(TranscriptionSession):
    """One Flux WebSocket session. The SDK keeps its receive loop on a thread."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        sample_rate: int,
        turn_end_silence_ms: int,
        switch_response_min_ms: int,
        callbacks: TranscriptionCallbacks,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._sample_rate = sample_rate
        self._turn_end_silence_ms = turn_end_silence_ms
        self._switch_response_min_ms = switch_response_min_ms
        self._callbacks = callbacks
        self._connection = None
        self._lock = Lock()
        self._pending_audio: Queue[bytes] = Queue(maxsize=50)
        self._speech_id: str | None = None
        self._switch_guard_ends_at = 0.0
        self._discard_interrupted_turn = False

    def start(self) -> None:
        if not self._api_key:
            raise TranscriptionError("DEEPGRAM_API_KEY is not configured")
        Thread(target=self._run, daemon=True, name="deepgram-transcription").start()

    def send_audio(self, audio: bytes) -> None:
        with self._lock:
            connection = self._connection
        if connection is None:
            try:
                self._pending_audio.put_nowait(audio)
                return
            except Full as error:
                raise TranscriptionError(
                    "Transcription stream is still connecting"
                ) from error
        try:
            connection.send_media(audio)
        except Exception as error:
            raise TranscriptionError("Unable to send audio to Deepgram") from error

    def stop(self) -> None:
        with self._lock:
            connection = self._connection
        if connection is not None:
            connection.send_close_stream()

    def interrupt(self) -> None:
        with self._lock:
            connection = self._connection
            self._speech_id = None
            # Flux sends an EndOfTurn for ForceEndTurn. It belongs to the
            # rejected response and must never become the replacement speech.
            self._discard_interrupted_turn = True
            self._switch_guard_ends_at = monotonic() + (
                self._switch_response_min_ms / 1000
            )
        if connection is not None:
            try:
                connection.send_force_end_turn()
            except Exception:
                # The local guard remains a safe fallback while reconnecting.
                pass

    def _run(self) -> None:
        try:
            from deepgram import DeepgramClient
            from deepgram.core.events import EventType

            client = DeepgramClient(api_key=self._api_key)
            with client.listen.v2.connect(
                model=self._model,
                encoding="linear16",
                sample_rate=self._sample_rate,
                eot_timeout_ms=self._turn_end_silence_ms,
            ) as connection:
                connection.on(EventType.MESSAGE, self._handle_message)
                connection.on(
                    EventType.ERROR,
                    lambda error: self._callbacks.on_error(
                        "STT_PROVIDER_ERROR", "Deepgram could not transcribe audio"
                    ),
                )
                with self._lock:
                    self._connection = connection
                self._send_pending_audio(connection)
                connection.start_listening()
        except Exception:
            self._callbacks.on_error(
                "STT_CONNECTION_FAILED", "Could not connect to Deepgram transcription"
            )
        finally:
            with self._lock:
                self._connection = None

    def _handle_message(self, message) -> None:
        event = getattr(message, "event", None)
        transcript = (getattr(message, "transcript", None) or "").strip()
        if self._discard_interrupted_turn and event in ("Update", "EndOfTurn"):
            if event == "EndOfTurn":
                self._speech_id = None
                self._discard_interrupted_turn = False
                self._callbacks.on_ready()
            return
        if event == "StartOfTurn":
            # A new provider turn is the authoritative boundary after Switch.
            self._discard_interrupted_turn = False
            self._begin_speech()
            return
        if event in ("Update", "EndOfTurn") and self._switch_guard_is_active():
            if event == "EndOfTurn":
                self._speech_id = None
            return
        if event == "Update" and transcript:
            self._callbacks.on_partial(self._begin_speech(), transcript)
        elif event == "EndOfTurn" and transcript:
            speech_id = self._begin_speech()
            self._callbacks.on_final(speech_id, transcript)
            self._speech_id = None

    def _switch_guard_is_active(self) -> bool:
        with self._lock:
            return monotonic() < self._switch_guard_ends_at

    def _send_pending_audio(self, connection) -> None:
        while True:
            try:
                connection.send_media(self._pending_audio.get_nowait())
            except Empty:
                return

    def _begin_speech(self) -> str:
        if self._speech_id is None:
            self._speech_id = f"speech_{uuid4().hex}"
            self._callbacks.on_started(self._speech_id)
        return self._speech_id


class TranscriptionService:
    """Tracks one provider stream per Socket.IO connection."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        sample_rate: int,
        chunk_ms: int,
        turn_end_silence_ms: int,
        switch_response_min_ms: int,
        session_factory: Callable[..., TranscriptionSession] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_ms
        self._max_chunk_bytes = sample_rate * 2 * chunk_ms // 1000
        self._turn_end_silence_ms = turn_end_silence_ms
        self._switch_response_min_ms = switch_response_min_ms
        self._session_factory = session_factory or DeepgramSession
        self._sessions: dict[str, TranscriptionSession] = {}

    @property
    def max_chunk_bytes(self) -> int:
        return self._max_chunk_bytes

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def chunk_ms(self) -> int:
        return self._chunk_ms

    def start_stream(
        self, socket_id: str, player_id: PlayerSlot, callbacks: TranscriptionCallbacks
    ) -> None:
        if not self._api_key:
            raise TranscriptionError("DEEPGRAM_API_KEY is not configured")
        if socket_id in self._sessions:
            self.stop_stream(socket_id)
        session = self._session_factory(
            api_key=self._api_key,
            model=self._model,
            sample_rate=self._sample_rate,
            turn_end_silence_ms=self._turn_end_silence_ms,
            switch_response_min_ms=self._switch_response_min_ms,
            callbacks=callbacks,
        )
        start = getattr(session, "start", None)
        if callable(start):
            start()
        self._sessions[socket_id] = session

    def send_audio(self, socket_id: str, audio: bytes) -> None:
        if not isinstance(audio, bytes) or not audio:
            raise TranscriptionError("Audio must be non-empty PCM16 bytes")
        if len(audio) > self._max_chunk_bytes:
            raise TranscriptionError(
                f"Audio chunk exceeds the {self._max_chunk_bytes}-byte limit"
            )
        session = self._sessions.get(socket_id)
        if session is None:
            raise TranscriptionError("No transcription stream is active")
        session.send_audio(audio)

    def stop_stream(self, socket_id: str) -> bool:
        session = self._sessions.pop(socket_id, None)
        if session is None:
            return False
        session.stop()
        return True

    def interrupt_stream(self, socket_id: str) -> bool:
        session = self._sessions.get(socket_id)
        if session is None:
            return False
        session.interrupt()
        return True


def create_transcription_service(config) -> TranscriptionService:
    if config["STT_PROVIDER"] != "deepgram":
        raise ValueError("Only the deepgram STT provider is supported")
    return TranscriptionService(
        api_key=config["DEEPGRAM_API_KEY"],
        model=config["DEEPGRAM_MODEL"],
        sample_rate=config["STT_SAMPLE_RATE"],
        chunk_ms=config["STT_CHUNK_MS"],
        turn_end_silence_ms=config["TURN_END_SILENCE_MS"],
        switch_response_min_ms=config["SWITCH_RESPONSE_MIN_MS"],
        session_factory=config["TRANSCRIPTION_SESSION_FACTORY"],
    )
