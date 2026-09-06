import os

from dotenv import load_dotenv

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

    REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "improv-faceoff")
    USE_IN_MEMORY_REDIS = os.getenv("USE_IN_MEMORY_REDIS", "false").lower() == "true"
