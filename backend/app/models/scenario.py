from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Tone(StrEnum):
    RELATABLE = "relatable"
    WACKY = "wacky"
    FUNNY = "funny"
    STUPID = "stupid"
    SERIOUS = "serious"
    SAD = "sad"
    AWKWARD = "awkward"
    TENSE = "tense"
    EMOTIONAL = "emotional"
    CHAOTIC = "chaotic"
    WHOLESOME = "wholesome"
    DRAMATIC = "dramatic"


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: Tone
    scenario: str = Field(min_length=1)
    player_a_role: str = Field(min_length=1)
    player_b_role: str = Field(min_length=1)
