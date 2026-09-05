from flask import Blueprint

from app.views.api_views import health_response

health_blueprint = Blueprint("health", __name__, url_prefix="/api")


@health_blueprint.get("/health")
def health():
    return health_response()
