"""Validated semantic result models returned by the A5 Gemini judge."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .scenario import Scenario
from .transcript import TranscriptEvent

PlayerSlot = Literal["A", "B"]


class SemanticCategoryPoints(BaseModel):
    """The qualitative categories Gemini owns; Speed belongs to A6."""

    model_config = ConfigDict(extra="forbid")

    adaptability: int = Field(ge=0, le=2000)
    creativity: int = Field(ge=0, le=2000)
    coherence: int = Field(ge=0, le=2000)
    collaboration: int = Field(ge=0, le=2000)


class JudgedPlayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_points: SemanticCategoryPoints
    highlight: str = Field(min_length=1, max_length=500)
    improvement: str = Field(min_length=1, max_length=500)


class JudgeHighlightEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: PlayerSlot
    label: str = Field(min_length=1, max_length=80)
    points: int = Field(ge=0, le=500)
    transcript_event_ids: list[str] = Field(min_length=1)


class JudgeResult(BaseModel):
    """A5 output, before deterministic Speed and final-score aggregation."""

    model_config = ConfigDict(extra="forbid")

    player_a: JudgedPlayer
    player_b: JudgedPlayer
    highlight_events: list[JudgeHighlightEvent] = Field(default_factory=list)


class JudgeInput(BaseModel):
    """Complete post-round context Gemini needs for a semantic judgment."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    transcript_events: list[TranscriptEvent]
    switch_response_latencies: dict[str, int | None] = Field(default_factory=dict)
    round_duration_ms: int = Field(gt=0)
