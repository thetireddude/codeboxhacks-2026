import os

import secrets

import random

RANDOM_SEEDS = [
    "object",
    "place",
    "action",
    "relationship",
    "problem",
    "goal",
    "event",
]

def random_seed_bundle():
    return secrets.token_hex(8)

import random

WORD_POOL = [
    "mirror",
    "ticket",
    "ladder",
    "orange",
    "receipt",
    "bell",
    "helmet",
    "envelope",
    "candle",
    "key",
    "map",
    "clock",
    "paint",
    "coin",
    "window",
    "rope",
    "shoe",
    "menu",
    "bucket",
    "photograph",
]

def get_random_words() -> str:
    return ", ".join(random.sample(WORD_POOL, 3))

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


class AppConfig:
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _as_int("PORT", 5000)
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only")
    CORS_ORIGINS = _as_origins("CORS_ORIGINS", "http://localhost:5173")

    ROUND_DURATION_MS = _as_int("ROUND_DURATION_MS", 60_000)
    COUNTDOWN_DURATION_MS = _as_int("COUNTDOWN_DURATION_MS", 3_000)
    MATCH_CLEANUP_DELAY_MS = _as_int("MATCH_CLEANUP_DELAY_MS", 300_000)
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
        Tone.AWKWARD,
        Tone.TENSE,
        Tone.EMOTIONAL,
        Tone.CHAOTIC,
        Tone.WHOLESOME,
        Tone.DRAMATIC
    )
    GEMINI_SCENARIO_PROMPT_TEMPLATE = "\n".join([
        "Create one original two-person improv scene starter in a {tone} tone.",
        "For a mundane tone, use an ordinary everyday situation without a hidden twist, coincidence, or heightened premise.",
        "",
        "The scene should give two performers an immediate situation they can react to, discuss, or act within.",
        "It should provide a starting point, not a plot.",
        "",
        "SCENE REQUIREMENTS:",
        "- Keep the situation simple, concrete, playable, and open-ended.",
        "- Focus on what is happening between the two people right now.",
        "- Prefer one clear situation.",
        "- Include at most one meaningful complication.",
        "- Use no more than 2-3 important details total.",
        "- Extra details are optional.",
        "- Leave the outcome, explanation, and escalation for the performers to invent.",
        "- The tone describes the situation, not how the performers must act.",
        "",
        "VARY THE SCENE ENGINE:",
        "- Do not merely change the setting or relationship while reusing the same conflict structure.",
        "- Vary the fundamental reason the scene is interesting.",
        "- Possible scene engines include two people trying to complete something together.",
        "- Possible scene engines include one person making a request.",
        "- Possible scene engines include one person revealing useful or surprising information.",
        "- Possible scene engines include a misunderstanding.",
        "- Possible scene engines include an inconvenient discovery.",
        "- Possible scene engines include an unusual shared circumstance.",
        "- Possible scene engines include a routine interaction becoming difficult.",
        "- Possible scene engines include two people waiting for something.",
        "- Possible scene engines include someone needing help.",
        "- Possible scene engines include someone explaining or demonstrating something.",
        "- Possible scene engines include a negotiation.",
        "- Possible scene engines include a reunion or first meeting.",
        "- Possible scene engines include a shared responsibility.",
        "- Possible scene engines include an unexpected arrival or interruption.",
        "- Possible scene engines include two people reacting differently to the same event.",
        "- Possible scene engines include a practical problem with no obvious solution.",
        "- Possible scene engines include cooperation without conflict.",
        "- Possible scene engines include disagreement without opposite goals.",
        "- Possible scene engines include a situation where neither person initially has a clear goal.",
        "- This list is inspiration, not a checklist.",
        "",
        "STRUCTURAL VARIETY:",
        "- Do not default to Person A wanting X while Person B wants the opposite.",
        "- Do not default to two characters arguing.",
        "- Do not default to estranged relatives, ex-partners, rival coworkers, enemies, or people with unresolved history.",
        "- Do not repeatedly build scenes around secrets, betrayals, confessions, ultimatums, or competing goals.",
        "- Conflict is optional.",
        "- Characters may cooperate, be confused together, share a problem, misunderstand each other, or simply react to an unusual circumstance.",
        "- Relationships may be familiar, professional, transactional, accidental, temporary, or unspecified.",
        "- Some scenes should work without any prior relationship between the characters.",
        "",
        "AVOID OVERWRITING:",
        "- Do not stack adjectives.",
        "- Do not stack twists.",
        "- Do not give either character an elaborate backstory.",
        "- Do not give both characters separate hidden motivations.",
        "- Do not explain why every detail exists.",
        "- Do not include a predetermined ending.",
        "- Do not turn the setup into a movie premise.",
        "- Do not make the scenario depend on multiple revelations.",
        "",
        "ROLES:",
        "- Describe only who each person is in the immediate situation.",
        "- Roles do not need to oppose, contrast, or balance each other.",
        "- Roles may be asymmetric.",
        "- One role may be more ordinary than the other.",
        "- Do not prescribe personality, emotion, speaking style, or strategy.",
        "- Each role must be 8 words or fewer.",
        "",
        "LENGTH:",
        "- Scenario must be 18 words maximum.",
        "- Shorter is preferred when clear.",
        "",
        "OPTIONAL INSPIRATION:",
        "- You should draw one abstract concept from: {random_words}.",
        "- You do not need to mention any of these words directly.",
        "- Do not force them into the scene.",
        "- Use them only if they help produce a less predictable premise.",
        "",
        "SAFETY:",
        "- Do not include slurs, sexual content, graphic violence, illegal instructions, stereotypes about protected groups, scoring rules, Switch rules, or gameplay modifiers."
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
