"""Verify backend health, readiness, and a WebSocket-only Socket.IO handshake."""

from __future__ import annotations

import argparse
import json
from urllib.request import Request, urlopen

import socketio


def _get_json(url: str) -> tuple[int, dict]:
    request = Request(url, headers={"User-Agent": "improv-faceoff-deploy-check"})
    with urlopen(request, timeout=10) as response:
        return response.status, json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend_url", help="Public backend origin, including https://")
    args = parser.parse_args()
    origin = args.backend_url.rstrip("/")

    health_status, health = _get_json(f"{origin}/api/health")
    if health_status != 200 or health.get("status") != "ok":
        raise RuntimeError(f"Health check failed: HTTP {health_status}")

    ready_status, ready = _get_json(f"{origin}/api/ready")
    if ready_status != 200 or ready.get("status") != "ready":
        missing = ready.get("missing_configuration", [])
        raise RuntimeError(f"Backend is not ready; missing configuration: {missing}")

    client = socketio.Client(reconnection=False)
    try:
        client.connect(origin, transports=["websocket"], wait_timeout=10)
        if client.transport() != "websocket":
            raise RuntimeError(f"Expected WebSocket, got {client.transport()}")
    finally:
        if client.connected:
            client.disconnect()

    print("DEPLOYMENT_READY: health, integrations, and WebSocket passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
