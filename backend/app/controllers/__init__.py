from flask import Flask

from app.services.game_service import GameService
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import InMemoryRedisService, RedisService
from app.services.transcript_service import TranscriptService
from app.services.transcription_service import create_transcription_service

from .game_controller import register_game_handlers
from .health_controller import health_blueprint
from .matchmaking_controller import register_matchmaking_handlers
from .transcription_controller import register_transcription_handlers


def register_controllers(app: Flask) -> None:
    app.register_blueprint(health_blueprint)
    storage = (
        InMemoryRedisService()
        if app.config["USE_IN_MEMORY_REDIS"]
        else RedisService(app.config["REDIS_URL"], app.config["REDIS_KEY_PREFIX"])
    )
    service = MatchmakingService(storage, app.config["STARTING_SWITCH_COUNT"])
    game_service = GameService(storage, app.config["ROUND_DURATION_MS"])
    socket_guests: dict[str, str] = {}
    app.extensions["matchmaking_service"] = service
    app.extensions["game_service"] = game_service
    app.extensions["socket_guests"] = socket_guests
    register_matchmaking_handlers(service, socket_guests)
    transcript_service = TranscriptService(game_service)
    transcription_service = create_transcription_service(app.config)
    register_game_handlers(
        game_service,
        service,
        socket_guests,
        app.config["COUNTDOWN_DURATION_MS"],
        transcript_service,
        transcription_service,
    )
    app.extensions["transcription_service"] = transcription_service
    app.extensions["transcript_service"] = transcript_service
    register_transcription_handlers(
        transcription_service,
        transcript_service,
        game_service,
        service,
    )
