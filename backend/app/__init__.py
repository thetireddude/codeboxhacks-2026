from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from .config import AppConfig
from .controllers import register_controllers

socketio = SocketIO(async_mode="threading")


def create_app(config: type[AppConfig] = AppConfig) -> Flask:
    """Create the Flask application without connecting to external services."""
    app = Flask(__name__)
    app.config.from_object(config)

    CORS(app, origins=app.config["CORS_ORIGINS"])
    socketio.init_app(app, cors_allowed_origins=app.config["CORS_ORIGINS"])
    register_controllers(app)

    return app
