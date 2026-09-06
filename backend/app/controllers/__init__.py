from flask import Flask

from app.services.game_service import GameService
from app.services.judge_service import create_judge_service
from app.services.livekit_service import create_livekit_service
from app.services.match_integration_service import MatchIntegrationService
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import InMemoryRedisService, RedisService
from app.services.scenario_service import create_scenario_service
from app.services.transcription_service import create_transcription_service

from .game_controller import register_game_handlers
from .health_controller import health_blueprint
from .matchmaking_controller import register_matchmaking_handlers
from .media_controller import register_media_handlers, register_media_routes
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
    scenario_service = create_scenario_service(app.config)
    judge_service = create_judge_service(app.config)
    integration_service = MatchIntegrationService(
        game_service, scenario_service, judge_service
    )
    socket_guests: dict[str, str] = {}
    app.extensions["matchmaking_service"] = service
    app.extensions["game_service"] = game_service
    app.extensions["match_integration_service"] = integration_service
    app.extensions["socket_guests"] = socket_guests
    register_matchmaking_handlers(service, socket_guests)
    transcription_service = create_transcription_service(app.config)
    app.extensions["transcription_service"] = transcription_service
    register_game_handlers(
        game_service,
        service,
        socket_guests,
        app.config["COUNTDOWN_DURATION_MS"],
        integration_service,
        transcription_service.handle_switch,
        app.config["MATCH_CLEANUP_DELAY_MS"],
    )
    livekit_service = create_livekit_service(app.config)
    app.extensions["livekit_service"] = livekit_service
    register_media_routes(app, livekit_service, service)
    register_media_handlers(livekit_service, service, socket_guests)
    register_transcription_handlers(
        transcription_service, game_service, service, socket_guests
    )
