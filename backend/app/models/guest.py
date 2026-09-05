from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GuestStatus(StrEnum):
    LOBBY = "lobby"
    QUEUEING = "queueing"
    MATCHED = "matched"
    DISCONNECTED = "disconnected"


class Guest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_id: UUID
    display_name: str
    socket_id: str | None = None
    status: GuestStatus
