"""Exercise the B3 Switch flow against a running local Socket.IO backend."""

from __future__ import annotations

from threading import Event
from time import sleep

import socketio


BACKEND_URL = "http://127.0.0.1:5000"


def _client(
    name: str, round_started: Event, round_ended: Event, duration_ms: list[int]
) -> socketio.Client:
    client = socketio.Client()

    @client.on("switch:triggered")
    def switch_triggered(payload: dict) -> None:
        print(
            f"{name} received switch:triggered "
            f"from={payload['event']['from_player_id']} "
            f"target={payload['event']['target_player_id']} "
            f"inventory={payload['switches_remaining']}"
        )

    @client.on("switch:rejected")
    def switch_rejected(payload: dict) -> None:
        print(f"{name} received switch:rejected code={payload['code']}")

    @client.on("round:start")
    def round_start(payload: dict) -> None:
        duration_ms[:] = [payload["duration_ms"]]
        print(f"{name} received round:start duration_ms={payload['duration_ms']}")
        round_started.set()

    @client.on("round:end")
    def round_end(_: dict) -> None:
        print(f"{name} received round:end")
        round_ended.set()

    client.connect(BACKEND_URL)
    return client


def _assert(response: dict, expected: dict) -> None:
    for key, value in expected.items():
        if response.get(key) != value:
            raise AssertionError(f"Expected {key}={value!r}, received {response!r}")


def main() -> None:
    round_started = Event()
    round_ended = Event()
    duration_ms: list[int] = []
    player_a = _client("A", round_started, round_ended, duration_ms)
    player_b = _client("B", round_started, round_ended, duration_ms)

    try:
        guest_a = player_a.call("guest:create", {})["guest"]
        guest_b = player_b.call("guest:create", {})["guest"]
        print("A queue:", player_a.call("queue:join", {"guest_id": guest_a["guest_id"]}))
        paired = player_b.call("queue:join", {"guest_id": guest_b["guest_id"]})
        _assert(paired, {"ok": True, "status": "paired"})
        match_id = paired["match_id"]
        print("B queue:", paired)

        player_a.call(
            "player:ready", {"match_id": match_id, "guest_id": guest_a["guest_id"]}
        )
        player_b.call(
            "player:ready", {"match_id": match_id, "guest_id": guest_b["guest_id"]}
        )
        if not round_started.wait(timeout=3):
            raise AssertionError("Timed out waiting for round:start")

        first_payload = {
            "match_id": match_id,
            "guest_id": guest_b["guest_id"],
            "request_id": "manual-switch-1",
        }
        first = player_b.call("switch:press", first_payload)
        _assert(first, {"ok": True, "replayed": False})
        _assert(first, {"switches_remaining": {"A": 5, "B": 4}})
        print("B first Switch:", first)

        replay = player_b.call("switch:press", first_payload)
        _assert(replay, {"ok": True, "replayed": True})
        _assert(replay, {"switches_remaining": {"A": 5, "B": 4}})
        print("B duplicate Switch:", replay)

        invalid = player_a.call(
            "switch:press",
            {
                "match_id": match_id,
                "guest_id": guest_a["guest_id"],
                "request_id": "a-invalid-switch",
            },
        )
        _assert(invalid, {"ok": False, "code": "NOT_LISTENER"})
        print("A invalid Switch:", invalid)

        for number in range(2, 6):
            response = player_b.call(
                "switch:press",
                {
                    "match_id": match_id,
                    "guest_id": guest_b["guest_id"],
                    "request_id": f"manual-switch-{number}",
                },
            )
            _assert(response, {"ok": True})

        exhausted = player_b.call(
            "switch:press",
            {
                "match_id": match_id,
                "guest_id": guest_b["guest_id"],
                "request_id": "manual-switch-6",
            },
        )
        _assert(exhausted, {"ok": False, "code": "NO_SWITCHES_REMAINING"})
        print("B exhausted Switch:", exhausted)

        if not duration_ms or not round_ended.wait(timeout=(duration_ms[0] / 1000) + 3):
            raise AssertionError("Timed out waiting for round:end")
        after_round = player_b.call(
            "switch:press",
            {
                "match_id": match_id,
                "guest_id": guest_b["guest_id"],
                "request_id": "after-round",
            },
        )
        _assert(after_round, {"ok": False, "code": "ROUND_NOT_ACTIVE"})
        print("B post-round Switch:", after_round)
        print("PASS: B3 Switch flow verified.")
    finally:
        sleep(0.1)
        player_a.disconnect()
        player_b.disconnect()


if __name__ == "__main__":
    main()
