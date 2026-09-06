from flask import jsonify


def health_response():
    return jsonify({"service": "improv-faceoff-backend", "status": "ok"}), 200


def readiness_response(config):
    """Report whether a deployed host has every required integration configured.

    This deliberately reports names only: browser clients and status probes never
    receive credential values.
    """
    requirements = {
        "GEMINI_API_KEY": bool(config["GEMINI_API_KEY"]),
        "DEEPGRAM_API_KEY": bool(config["DEEPGRAM_API_KEY"]),
        "LIVEKIT_URL": bool(config["LIVEKIT_URL"]),
        "LIVEKIT_API_KEY": bool(config["LIVEKIT_API_KEY"]),
        "LIVEKIT_API_SECRET": bool(config["LIVEKIT_API_SECRET"]),
    }
    missing = [name for name, configured in requirements.items() if not configured]
    status = "ready" if not missing else "configuration_required"
    return (
        jsonify(
            {
                "service": "improv-faceoff-backend",
                "status": status,
                "missing_configuration": missing,
            }
        ),
        200 if not missing else 503,
    )
