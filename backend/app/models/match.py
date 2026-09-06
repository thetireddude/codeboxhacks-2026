from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .scenario import Scenario
from .results import MatchResults
from .transcript import TranscriptEvent

PlayerSlot = Literal["A", "B"]


class MatchStatus(StrEnum):
    LOBBY = "LOBBY"
    QUEUEING = "QUEUEING"
    MATCH_FOUND = "MATCH_FOUND"
    CONNECTING_MEDIA = "CONNECTING_MEDIA"
    READY = "READY"
    COUNTDOWN = "COUNTDOWN"
    ROUND_ACTIVE = "ROUND_ACTIVE"
    ROUND_END = "ROUND_END"
    SCORING = "SCORING"
    RESULTS = "RESULTS"


class SwitchInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    A: int = Field(ge=0, le=5)
    B: int = Field(ge=0, le=5)


class MatchState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: UUID
    player_a_id: UUID
    player_b_id: UUID
    ready_player_ids: list[UUID] = Field(default_factory=list, max_length=2)
    state: MatchStatus
    scenario: Scenario | None
    round_started_at: datetime | None
    active_player_id: PlayerSlot | None
    switches_remaining: SwitchInventory
    # None means a newer Switch superseded this one before speech restarted.
    switch_response_latencies: dict[str, int | None] = Field(default_factory=dict)
    transcript_events: list[TranscriptEvent]
    # Retained for the short post-round cleanup window so a reconnecting player
    # receives the identical authoritative result.
    results: MatchResults | None = None
