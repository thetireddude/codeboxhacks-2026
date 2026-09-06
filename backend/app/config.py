import os
import random

from dotenv import load_dotenv

from .models.scenario import Tone

load_dotenv()


def _as_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _as_origins(name: str, default: str) -> list[str]:
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


def _as_words(name: str, default: str) -> tuple[str, ...]:
    """Read a comma-separated role blacklist without empty entries."""
    return tuple(
        item.strip().lower()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    )


_SCENARIO_WORD_POOL = (
    "mirror", "ticket", "ladder", "orange", "receipt", "bell", "helmet",
    "envelope", "candle", "key", "map", "clock", "paint", "coin",
    "window", "rope", "shoe", "menu", "bucket", "photograph",
)


def get_random_words() -> str:
    """Return lightweight inspiration without dictating the scene premise."""
    return ", ".join(random.sample(_SCENARIO_WORD_POOL, 3))


class AppConfig:
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _as_int("PORT", 5000)
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only")
    CORS_ORIGINS = _as_origins("CORS_ORIGINS", "http://localhost:5173")

    ROUND_DURATION_MS = _as_int("ROUND_DURATION_MS", 60_000)
    COUNTDOWN_DURATION_MS = _as_int("COUNTDOWN_DURATION_MS", 3_000)
    MATCH_CLEANUP_DELAY_MS = _as_int("MATCH_CLEANUP_DELAY_MS", 300_000)
    # Preserve result reconnects briefly, but release both guests when neither
    # browser returns after a shared disconnect.
    RESULT_DISCONNECT_GRACE_MS = _as_int("RESULT_DISCONNECT_GRACE_MS", 5_000)
    STARTING_SWITCH_COUNT = _as_int("STARTING_SWITCH_COUNT", 5)
    # Give the listener a practical Switch window before STT ends the turn.
    # This stays configurable for playtesting; the spec recommends 700–1200 ms.
    TURN_END_SILENCE_MS = _as_int("TURN_END_SILENCE_MS", 900)
    SWITCH_RESPONSE_MIN_MS = _as_int("SWITCH_RESPONSE_MIN_MS", 0)
    SWITCH_MODE = os.getenv("SWITCH_MODE", "ALWAYS_AVAILABLE_DURING_OPPONENT_TURN")
    CHAIN_SWITCH_WINDOW_MS = _as_int("CHAIN_SWITCH_WINDOW_MS", 500)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_SCENARIO_MODEL = os.getenv("GEMINI_SCENARIO_MODEL", "gemini-3.1-flash-lite")
    GEMINI_SCENARIO_MAX_ATTEMPTS = _as_int("GEMINI_SCENARIO_MAX_ATTEMPTS", 2)
    # Roles must support a spoken, back-and-forth scene. Deployments can extend
    # this comma-separated list through SCENARIO_ROLE_BLACKLIST.
    SCENARIO_ROLE_BLACKLIST = _as_words(
        "SCENARIO_ROLE_BLACKLIST",
        "mime,mimes,mute,muted,nonverbal,non-verbal",
    )
    GEMINI_JUDGE_MODEL = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.1-flash-lite")
    # Keep SDK retries disabled, but retry one failed structured judgment. This
    # protects live UUID-style transcripts from a transient/model-format miss
    # without slowing successful rounds.
    GEMINI_JUDGE_MAX_ATTEMPTS = _as_int("GEMINI_JUDGE_MAX_ATTEMPTS", 2)
    GEMINI_JUDGE_TIMEOUT_MS = _as_int("GEMINI_JUDGE_TIMEOUT_MS", 12_000)

    # A6 arcade-Speed curve. Points decay linearly per second after a Switch.
    SPEED_BASE_POINTS = _as_int("SPEED_BASE_POINTS", 500)
    SPEED_DECAY_POINTS_PER_SECOND = _as_int("SPEED_DECAY_POINTS_PER_SECOND", 120)
    SPEED_MAX_POINTS = _as_int("SPEED_MAX_POINTS", 2000)
    GEMINI_SCENARIO_TONES = (
        Tone.MUNDANE,
        Tone.RELATABLE,
        Tone.WACKY,
        Tone.FUNNY,
        Tone.STUPID,
        Tone.SERIOUS,
        Tone.SAD,
    )
    GEMINI_SCENARIO_PROMPT_TEMPLATE = "\n".join([
        "Create one original two-person improv scene starter in a {tone} tone.",
        "For a mundane tone, use an ordinary everyday situation without a hidden twist, coincidence, or heightened premise.",
        "", "The scene should be a simple, concrete, playable starting point, not a plot.",
        "Focus on what is happening between the two people right now. Include at most one meaningful complication.",
        "Leave the outcome, explanation, and escalation for the performers to invent.",
        "", "VARIETY:",
        "- Vary the fundamental reason the scene is interesting, not merely the setting or relationship.",
        "- Conflict is optional: people may cooperate, share a problem, misunderstand each other, or react to an unusual circumstance.",
        "- Do not default to opposing goals, arguments, ex-partners, estranged relatives, secrets, betrayals, confessions, or competing goals.",
        "- Do not use duplicate, identical, matching, or exact-same-item premises.",
        "- Do not use sibling, packing-up, moving-out, or moving-away premises.",
        "", "ROLES:",
        "- Describe only who each person is in the immediate situation; each role must be 8 words or fewer.",
        "- Roles may be asymmetric and do not need to oppose, contrast, or prescribe personality, emotion, speaking style, or strategy.",
        "", "LENGTH:", "- Scenario must be 18 words maximum.",
        "", "OPTIONAL INSPIRATION:",
        "- You may draw one abstract concept from: {random_words}.",
        "- Do not force these words into the scene.",
        "", "SAFETY:",
        "- Do not use real people, copyrighted characters, slurs, sexual content, graphic violence, illegal instructions, or stereotypes about protected groups.",
        f"- Do not assign roles containing these words: {', '.join(SCENARIO_ROLE_BLACKLIST)}.",
        "- Do not include a winner, scoring instruction, Switch rule, or gameplay modifier.",
    ])

    STT_PROVIDER = os.getenv("STT_PROVIDER") or "deepgram"
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL") or "flux-general-en"
    STT_SAMPLE_RATE = _as_int("STT_SAMPLE_RATE", 16_000)
    STT_CHUNK_MS = _as_int("STT_CHUNK_MS", 80)
    # This hook lets tests replace the network-backed session with a fake.
    TRANSCRIPTION_SESSION_FACTORY = None

    REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "improv-faceoff")
    USE_IN_MEMORY_REDIS = os.getenv("USE_IN_MEMORY_REDIS", "false").lower() == "true"

    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
    LIVEKIT_TOKEN_TTL_SECONDS = _as_int("LIVEKIT_TOKEN_TTL_SECONDS", 3_600)
