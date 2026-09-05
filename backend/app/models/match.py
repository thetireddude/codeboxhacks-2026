from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .scenario import Scenario
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

    A: int = Field(ge=0)
    B: int = Field(ge=0)


class MatchState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: UUID
    player_a_id: UUID
    player_b_id: UUID
    state: MatchStatus
    scenario: Scenario | None
    round_started_at: datetime | None
    active_player_id: PlayerSlot | None
    switches_remaining: SwitchInventory
    transcript_events: list[TranscriptEvent]
