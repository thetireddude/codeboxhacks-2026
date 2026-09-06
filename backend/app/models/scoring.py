"""Validated input boundary for deterministic A6 arcade aggregation."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .judgment import JudgeResult
from .transcript import TranscriptEvent


class ScoringInput(BaseModel):
    """A completed A5 judgment and its authoritative event timeline."""

    model_config = ConfigDict(extra="forbid")

    match_id: UUID
    judgment: JudgeResult
    transcript_events: list[TranscriptEvent]
    round_duration_ms: int = Field(gt=0)
