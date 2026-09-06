from flask import Flask

from app.services.game_service import GameService
from app.services.judge_service import create_judge_service
from app.services.livekit_service import create_livekit_service
from app.services.leaderboard_service import (
    LeaderboardRepository,
    UnavailableLeaderboardRepository,
)
from app.services.match_integration_service import MatchIntegrationService
from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import InMemoryRedisService, RedisService
from app.services.scenario_service import create_scenario_service
from app.services.scoring_service import create_scoring_service
from app.services.transcript_service import TranscriptService
from app.services.transcription_service import create_transcription_service
from .game_controller import register_game_handlers
from .health_controller import health_blueprint
from .leaderboard_controller import leaderboard_blueprint
from .matchmaking_controller import register_matchmaking_handlers
from .media_controller import register_media_handlers, register_media_routes
from .scoring_controller import scoring_blueprint
from .transcription_controller import register_transcription_handlers


def register_controllers(app: Flask) -> None:
    app.register_blueprint(health_blueprint)
    database_url = app.config["DATABASE_URL"]
    leaderboard_repository = (
        LeaderboardRepository(
            database_url,
            app.config["LEADERBOARD_SCORING_VERSION"],
            app.config["LEADERBOARD_AUTO_CREATE_SCHEMA"],
        )
        if database_url
        else UnavailableLeaderboardRepository()
    )
    storage = (
        InMemoryRedisService()
        if app.config["USE_IN_MEMORY_REDIS"]
        else RedisService(app.config["REDIS_URL"], app.config["REDIS_KEY_PREFIX"])
    )
    service = MatchmakingService(storage, app.config["STARTING_SWITCH_COUNT"])
    game_service = GameService(storage, app.config["ROUND_DURATION_MS"])
    judge_service = create_judge_service(app.config)
    scoring_service = create_scoring_service(app.config)
    transcript_service = TranscriptService(game_service)
    integration_service = MatchIntegrationService(
        game_service,
        create_scenario_service(app.config),
        judge_service,
        scoring_service,
        leaderboard_repository,
    )
    socket_guests: dict[str, str] = {}
    transcription_service = create_transcription_service(app.config)
    livekit_service = create_livekit_service(app.config)
    app.extensions.update(
        matchmaking_service=service,
        game_service=game_service,
        judge_service=judge_service,
        scoring_service=scoring_service,
        transcript_service=transcript_service,
        transcription_service=transcription_service,
        match_integration_service=integration_service,
        livekit_service=livekit_service,
        leaderboard_repository=leaderboard_repository,
        socket_guests=socket_guests,
    )
    register_matchmaking_handlers(service, socket_guests)
    app.register_blueprint(scoring_blueprint)
    app.register_blueprint(leaderboard_blueprint)
    register_game_handlers(
        game_service,
        service,
        socket_guests,
        app.config["COUNTDOWN_DURATION_MS"],
        integration_service,
        transcript_service,
        transcription_service,
        app.config["MATCH_CLEANUP_DELAY_MS"],
        app.config["RESULT_DISCONNECT_GRACE_MS"],
    )
    register_media_routes(app, livekit_service, service)
    register_media_handlers(livekit_service, service, socket_guests)
    register_transcription_handlers(
        transcription_service, transcript_service, game_service, service
    )
