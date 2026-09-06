from flask import Flask

from app.services.matchmaking_service import MatchmakingService
from app.services.redis_service import InMemoryRedisService, RedisService

from .health_controller import health_blueprint
from .matchmaking_controller import register_matchmaking_handlers


def register_controllers(app: Flask) -> None:
    app.register_blueprint(health_blueprint)
    storage = (
        InMemoryRedisService()
        if app.config["USE_IN_MEMORY_REDIS"]
        else RedisService(app.config["REDIS_URL"], app.config["REDIS_KEY_PREFIX"])
    )
    service = MatchmakingService(storage, app.config["STARTING_SWITCH_COUNT"])
    app.extensions["matchmaking_service"] = service
    register_matchmaking_handlers(service)
