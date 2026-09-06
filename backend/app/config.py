import os

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
    STARTING_SWITCH_COUNT = _as_int("STARTING_SWITCH_COUNT", 5)
    TURN_END_SILENCE_MS = _as_int("TURN_END_SILENCE_MS", 900)
    SWITCH_MODE = os.getenv("SWITCH_MODE", "ALWAYS_AVAILABLE_DURING_OPPONENT_TURN")
    CHAIN_SWITCH_WINDOW_MS = _as_int("CHAIN_SWITCH_WINDOW_MS", 500)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_SCENARIO_MODEL = os.getenv("GEMINI_SCENARIO_MODEL", "gemini-3.1-flash-lite")
    GEMINI_SCENARIO_MAX_ATTEMPTS = _as_int("GEMINI_SCENARIO_MAX_ATTEMPTS", 2)
    GEMINI_SCENARIO_TONES = (
        Tone.RELATABLE,
        Tone.WACKY,
        Tone.FUNNY,
        Tone.STUPID,
        Tone.SERIOUS,
        Tone.SAD,
    )
    GEMINI_SCENARIO_PROMPT_TEMPLATE = (
        "Create an original, brief improv scene starter in a {tone} tone. Should be no more than 12 words.\n\n"
        "Give both performers distinct, complementary roles with an immediate "
        "relationship or tension. The setup must be playable and readable immediately in a "
        "short two-person scene.\n\n"
        "Do not use real people, copyrighted characters, slurs, sexual content, "
        "graphic violence, illegal instructions, or stereotypes about protected "
        "groups. Do not include a winner, scoring instruction, Switch rule, or "
        "gameplay modifier."
    )
    REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "improv-faceoff")
    USE_IN_MEMORY_REDIS = os.getenv("USE_IN_MEMORY_REDIS", "false").lower() == "true"
