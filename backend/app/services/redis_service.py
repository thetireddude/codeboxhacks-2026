"""Redis-backed temporary storage for anonymous guests and active matches."""

from __future__ import annotations

import json
from threading import Lock
from typing import Any
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError

from app.models import Guest, MatchState


class StorageUnavailableError(RuntimeError):
    """Raised when temporary multiplayer state cannot be reached."""


class RedisService:
    """Temporary match storage with an atomic public-queue operation."""

    _CLAIM_QUEUE_SLOT = """
local match_key = KEYS[1] .. ARGV[1]
local members_key = KEYS[2]
local waiting_key = KEYS[3]
local match_prefix = KEYS[4]
local guest_id = ARGV[1]
local match_id = ARGV[2]

if redis.call('GET', match_key) then
  return { 'matched' }
end
if redis.call('SISMEMBER', members_key, guest_id) == 1 then
  return { 'queued' }
end

while true do
  local opponent_id = redis.call('LPOP', waiting_key)
  if not opponent_id then break end
  if redis.call('SISMEMBER', members_key, opponent_id) == 1 then
    redis.call('SREM', members_key, opponent_id)
    redis.call('SET', match_prefix .. opponent_id, match_id)
    redis.call('SET', match_key, match_id)
    return { 'paired', opponent_id }
  end
end

redis.call('RPUSH', waiting_key, guest_id)
redis.call('SADD', members_key, guest_id)
return { 'waiting' }
"""

    def __init__(self, redis_url: str, key_prefix: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    def connect(self) -> None:
        try:
            self._client.ping()
        except RedisError as error:
            raise StorageUnavailableError("Redis is unavailable") from error

    def save_guest(self, guest: Guest) -> None:
        self._set_json(self._guest_key(guest.guest_id), guest.model_dump(mode="json"))

    def get_guest(self, guest_id: UUID) -> Guest | None:
        payload = self._get_json(self._guest_key(guest_id))
        return Guest.model_validate(payload) if payload else None

    def save_match(self, match: MatchState) -> None:
        self._set_json(self._match_key(match.match_id), match.model_dump(mode="json"))

    def get_match(self, match_id: UUID) -> MatchState | None:
        payload = self._get_json(self._match_key(match_id))
        return MatchState.model_validate(payload) if payload else None

    def claim_queue_slot(
        self, guest_id: UUID, match_id: UUID
    ) -> tuple[str, UUID | None]:
        try:
            result = self._client.eval(
                self._CLAIM_QUEUE_SLOT,
                4,
                self._guest_match_prefix(),
                self._queue_members_key(),
                self._waiting_queue_key(),
                self._guest_match_prefix(),
                str(guest_id),
                str(match_id),
            )
        except RedisError as error:
            raise StorageUnavailableError("Redis is unavailable") from error

        status = result[0]
        opponent_id = UUID(result[1]) if status == "paired" else None
        return status, opponent_id

    def leave_queue(self, guest_id: UUID) -> bool:
        try:
            return bool(self._client.srem(self._queue_members_key(), str(guest_id)))
        except RedisError as error:
            raise StorageUnavailableError("Redis is unavailable") from error

    def _set_json(self, key: str, value: dict[str, Any]) -> None:
        try:
            self._client.set(key, json.dumps(value))
        except RedisError as error:
            raise StorageUnavailableError("Redis is unavailable") from error

    def _get_json(self, key: str) -> dict[str, Any] | None:
        try:
            value = self._client.get(key)
        except RedisError as error:
            raise StorageUnavailableError("Redis is unavailable") from error
        return json.loads(value) if value else None

    def _guest_key(self, guest_id: UUID) -> str:
        return f"{self._prefix}:guest:{guest_id}"

    def _match_key(self, match_id: UUID) -> str:
        return f"{self._prefix}:match:{match_id}"

    def _guest_match_prefix(self) -> str:
        return f"{self._prefix}:guest-match:"

    def _waiting_queue_key(self) -> str:
        return f"{self._prefix}:queue:waiting"

    def _queue_members_key(self) -> str:
        return f"{self._prefix}:queue:members"


class InMemoryRedisService:
    """Test-only implementation of the Redis service contract."""

    def __init__(self) -> None:
        self._guests: dict[UUID, Guest] = {}
        self._matches: dict[UUID, MatchState] = {}
        self._waiting: list[UUID] = []
        self._queued: set[UUID] = set()
        self._guest_matches: dict[UUID, UUID] = {}
        self._lock = Lock()

    def connect(self) -> None:
        return None

    def save_guest(self, guest: Guest) -> None:
        self._guests[guest.guest_id] = guest

    def get_guest(self, guest_id: UUID) -> Guest | None:
        return self._guests.get(guest_id)

    def save_match(self, match: MatchState) -> None:
        self._matches[match.match_id] = match

    def get_match(self, match_id: UUID) -> MatchState | None:
        return self._matches.get(match_id)

    def claim_queue_slot(
        self, guest_id: UUID, match_id: UUID
    ) -> tuple[str, UUID | None]:
        with self._lock:
            if guest_id in self._guest_matches:
                return "matched", None
            if guest_id in self._queued:
                return "queued", None
            while self._waiting:
                opponent_id = self._waiting.pop(0)
                if opponent_id in self._queued:
                    self._queued.remove(opponent_id)
                    self._guest_matches[opponent_id] = match_id
                    self._guest_matches[guest_id] = match_id
                    return "paired", opponent_id
            self._waiting.append(guest_id)
            self._queued.add(guest_id)
            return "waiting", None

    def leave_queue(self, guest_id: UUID) -> bool:
        with self._lock:
            if guest_id not in self._queued:
                return False
            self._queued.remove(guest_id)
            return True
