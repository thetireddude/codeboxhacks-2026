"""Anonymous guest creation and public two-player matchmaking."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.models import Guest, GuestStatus, MatchState, MatchStatus, SwitchInventory

from .redis_service import RedisService


class MatchmakingError(ValueError):
    """A client requested a matchmaking operation that is not valid."""


class MatchmakingService:
    def __init__(self, storage: RedisService, starting_switch_count: int) -> None:
        self._storage = storage
        self._starting_switch_count = starting_switch_count

    def create_guest(self, socket_id: str, guest_id: UUID | None = None) -> Guest:
        guest_id = guest_id or uuid4()
        existing = self._storage.get_guest(guest_id)
        if existing and existing.socket_id not in (None, socket_id):
            raise MatchmakingError("Guest identity is already connected elsewhere")
        guest = Guest(
            guest_id=guest_id,
            display_name=f"Player {guest_id.int % 10_000:04d}",
            socket_id=socket_id,
            status=GuestStatus.LOBBY,
        )
        self._storage.save_guest(guest)
        return guest

    def join_queue(
        self, guest_id: UUID, socket_id: str
    ) -> tuple[str, MatchState | None]:
        guest = self._require_owned_guest(guest_id, socket_id)
        proposed_match_id = uuid4()
        status, opponent_id = self._storage.claim_queue_slot(
            guest_id, proposed_match_id
        )
        if status == "matched":
            raise MatchmakingError("Guest is already matched")
        if status == "queued":
            return "queued", None
        if status == "waiting":
            self._save_guest(guest, GuestStatus.QUEUEING)
            return "waiting", None

        if opponent_id is None:
            raise RuntimeError("Paired queue operation did not return an opponent")
        opponent = self._storage.get_guest(opponent_id)
        if opponent is None:
            raise RuntimeError("Matched opponent was not found")
        match = self._new_match(proposed_match_id, guest, opponent)
        self._storage.save_match(match)
        self._save_guest(guest, GuestStatus.MATCHED)
        self._save_guest(opponent, GuestStatus.MATCHED)
        return "paired", match

    def leave_queue(self, guest_id: UUID, socket_id: str) -> bool:
        guest = self._require_owned_guest(guest_id, socket_id)
        removed = self._storage.leave_queue(guest_id)
        if removed:
            self._save_guest(guest, GuestStatus.LOBBY)
        return removed

    def get_guest(self, guest_id: UUID) -> Guest | None:
        return self._storage.get_guest(guest_id)

    def disconnect_guest(self, guest_id: UUID, socket_id: str) -> None:
        """Release a socket-bound guest identity so the same guest can reconnect."""
        guest = self._storage.get_guest(guest_id)
        if guest is not None and guest.socket_id == socket_id:
            self._storage.save_guest(
                guest.model_copy(
                    update={"socket_id": None, "status": GuestStatus.DISCONNECTED}
                )
            )

    def _require_owned_guest(self, guest_id: UUID, socket_id: str) -> Guest:
        guest = self._storage.get_guest(guest_id)
        if guest is None or guest.socket_id != socket_id:
            raise MatchmakingError("Guest is not connected from this socket")
        return guest

    def _save_guest(self, guest: Guest, status: GuestStatus) -> None:
        self._storage.save_guest(guest.model_copy(update={"status": status}))

    def _new_match(
        self,
        match_id: UUID,
        joining_guest: Guest,
        waiting_guest: Guest,
    ) -> MatchState:
        return MatchState(
            match_id=match_id,
            player_a_id=waiting_guest.guest_id,
            player_b_id=joining_guest.guest_id,
            ready_player_ids=[],
            state=MatchStatus.MATCH_FOUND,
            scenario=None,
            round_started_at=None,
            active_player_id=None,
            switches_remaining=SwitchInventory(
                A=self._starting_switch_count,
                B=self._starting_switch_count,
            ),
            transcript_events=[],
        )

    def get_match_for_guest(self, guest_id: UUID) -> MatchState | None:
        return self._storage.get_match_for_guest(guest_id)
