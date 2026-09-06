from flask import Blueprint, current_app

from app.views.api_views import health_response, readiness_response

health_blueprint = Blueprint("health", __name__, url_prefix="/api")


@health_blueprint.get("/health")
def health():
    return health_response()


@health_blueprint.get("/ready")
def ready():
    """Expose safe integration readiness for a deployed backend host."""
    return readiness_response(current_app.config)
