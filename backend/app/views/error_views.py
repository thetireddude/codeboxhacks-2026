from flask import jsonify


def error_response(code: str, message: str, status: int = 400):
    return jsonify({"error": {"code": code, "message": message}}), status
