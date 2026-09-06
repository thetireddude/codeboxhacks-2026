from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Tone(StrEnum):
    MUNDANE = "mundane"
    RELATABLE = "relatable"
    # Retained solely to parse legacy fixtures and already-created matches;
    # it is not present in the live generation pool.
    WACKY = "wacky"
    FUNNY = "funny"
    SERIOUS = "serious"
    SAD = "sad"
    AWKWARD = "awkward"
    TENSE = "tense"
    EMOTIONAL = "emotional"
    SUSPENSEFUL = "suspenseful"
    WHOLESOME = "wholesome"
    DRAMATIC = "dramatic"


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: Tone
    scenario: str = Field(min_length=1)
    player_a_role: str = Field(min_length=1)
    player_b_role: str = Field(min_length=1)
