from flask import jsonify


def health_response():
    return jsonify({"service": "improv-faceoff-backend", "status": "ok"}), 200
