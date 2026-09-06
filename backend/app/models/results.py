from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PlayerSlot = Literal["A", "B"]


class CategoryPoints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adaptability: int = Field(ge=0)
    articulation: int = Field(ge=0)
    speed: int = Field(ge=0)
    coherence: int = Field(ge=0)
    collaboration: int = Field(ge=0)


class PlayerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_points: int = Field(ge=0)
    category_points: CategoryPoints
    highlight: str = Field(min_length=1)
    improvement: str = Field(min_length=1)


class HighlightEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: PlayerSlot
    label: str = Field(min_length=1)
    points: int = Field(ge=0)
    transcript_event_ids: list[str]


class MatchResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: UUID
    winner: Literal["A", "B", "TIE"]
    player_a: PlayerResult
    player_b: PlayerResult
    highlight_events: list[HighlightEvent]
