"""Issue scoped LiveKit credentials for an authoritative match participant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from app.models import Guest, MatchState, MatchStatus


class LiveKitError(RuntimeError):
    """LiveKit credentials could not be safely created."""


@dataclass(frozen=True)
class LiveKitCredentials:
    url: str
    room_name: str
    token: str
    participant_identity: str

    def to_payload(self) -> dict[str, str]:
        return {
            "url": self.url,
            "room_name": self.room_name,
            "token": self.token,
            "participant_identity": self.participant_identity,
        }


class LiveKitService:
    """Create a narrowly scoped, short-lived room-join token per player."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        api_secret: str,
        token_ttl_seconds: int,
        token_factory: Callable[[str, str, str, str, int], str] | None = None,
    ) -> None:
        if token_ttl_seconds < 1:
            raise ValueError("token_ttl_seconds must be positive")
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._token_ttl_seconds = token_ttl_seconds
        self._token_factory = token_factory or self._create_token

    @staticmethod
    def room_name(match_id: UUID) -> str:
        """Use an opaque, deterministic name so both players join one room."""
        return f"improv-faceoff-{match_id.hex}"

    def credentials_for(self, match: MatchState, guest: Guest) -> LiveKitCredentials:
        if not self.is_configured:
            raise LiveKitError("LiveKit is not configured")
        if guest.guest_id not in (match.player_a_id, match.player_b_id):
            raise LiveKitError("Guest is not a participant in this match")
        if match.state in (
            MatchStatus.ROUND_END,
            MatchStatus.SCORING,
            MatchStatus.RESULTS,
        ):
            raise LiveKitError("Media credentials are unavailable after the round")

        slot = "A" if guest.guest_id == match.player_a_id else "B"
        room_name = self.room_name(match.match_id)
        participant_identity = f"improv-faceoff-{slot.lower()}-{guest.guest_id.hex}"
        return LiveKitCredentials(
            url=self._url,
            room_name=room_name,
            token=self._token_factory(
                room_name,
                participant_identity,
                guest.display_name,
                slot,
                self._token_ttl_seconds,
            ),
            participant_identity=participant_identity,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._url and self._api_key and self._api_secret)

    def _create_token(
        self,
        room_name: str,
        identity: str,
        display_name: str,
        _slot: str,
        ttl_seconds: int,
    ) -> str:
        try:
            from livekit import api
        except ImportError as error:
            raise LiveKitError("LiveKit server SDK is not installed") from error

        try:
            return (
                api.AccessToken(self._api_key, self._api_secret)
                .with_identity(identity)
                .with_name(display_name)
                .with_ttl(timedelta(seconds=ttl_seconds))
                .with_grants(
                    api.VideoGrants(
                        room_join=True,
                        room=room_name,
                        can_publish=True,
                        can_subscribe=True,
                        can_publish_data=True,
                    )
                )
                .to_jwt()
            )
        except Exception as error:
            raise LiveKitError("Could not create LiveKit access token") from error


def create_livekit_service(config: Any) -> LiveKitService:
    return LiveKitService(
        url=config["LIVEKIT_URL"],
        api_key=config["LIVEKIT_API_KEY"],
        api_secret=config["LIVEKIT_API_SECRET"],
        token_ttl_seconds=config["LIVEKIT_TOKEN_TTL_SECONDS"],
    )
