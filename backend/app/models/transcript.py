from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PlayerSlot = Literal["A", "B"]


class SpeechEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["speech"]
    id: str = Field(pattern=r"^speech_[A-Za-z0-9_-]+$")
    player_id: PlayerSlot
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    is_final: bool
    accepted: bool
    truncated_by_switch: bool
    truncated_by_round_end: bool


class SwitchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["switch"]
    id: str = Field(pattern=r"^switch_[A-Za-z0-9_-]+$")
    from_player_id: PlayerSlot
    target_player_id: PlayerSlot
    timestamp_ms: int = Field(ge=0)


TranscriptEvent = Annotated[
    SpeechEvent | SwitchEvent,
    Field(discriminator="type"),
]
