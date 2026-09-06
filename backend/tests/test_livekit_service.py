from uuid import uuid4

from app.models import Guest, GuestStatus, MatchState, MatchStatus, SwitchInventory
from app.services.livekit_service import LiveKitError, LiveKitService


def _match() -> tuple[MatchState, Guest, Guest]:
    player_a = Guest(
        guest_id=uuid4(),
        display_name="Player 0001",
        socket_id="socket-a",
        status=GuestStatus.MATCHED,
    )
    player_b = Guest(
        guest_id=uuid4(),
        display_name="Player 0002",
        socket_id="socket-b",
        status=GuestStatus.MATCHED,
    )
    match = MatchState(
        match_id=uuid4(),
        player_a_id=player_a.guest_id,
        player_b_id=player_b.guest_id,
        ready_player_ids=[],
        state=MatchStatus.MATCH_FOUND,
        scenario=None,
        round_started_at=None,
        active_player_id=None,
        switches_remaining=SwitchInventory(A=5, B=5),
        transcript_events=[],
    )
    return match, player_a, player_b


def test_players_receive_distinct_tokens_for_the_same_deterministic_room():
    calls = []

    def fake_token(room, identity, name, slot, ttl):
        calls.append((room, identity, name, slot, ttl))
        return f"token-for-{identity}"

    service = LiveKitService(
        url="wss://example.livekit.cloud/",
        api_key="key",
        api_secret="secret",
        token_ttl_seconds=900,
        token_factory=fake_token,
    )
    match, player_a, player_b = _match()

    a_credentials = service.credentials_for(match, player_a)
    b_credentials = service.credentials_for(match, player_b)

    assert a_credentials.url == "wss://example.livekit.cloud"
    assert a_credentials.room_name == b_credentials.room_name
    assert a_credentials.room_name == service.room_name(match.match_id)
    assert a_credentials.participant_identity != b_credentials.participant_identity
    assert a_credentials.token != b_credentials.token
    assert calls[0][3] == "A"
    assert calls[1][3] == "B"


def test_credentials_require_configuration_and_an_active_match():
    match, player_a, _ = _match()
    unconfigured = LiveKitService(
        url="", api_key="", api_secret="", token_ttl_seconds=900
    )

    try:
        unconfigured.credentials_for(match, player_a)
    except LiveKitError as error:
        assert str(error) == "LiveKit is not configured"
    else:
        raise AssertionError("Expected LiveKitError")

    configured = LiveKitService(
        url="wss://example.livekit.cloud",
        api_key="key",
        api_secret="secret",
        token_ttl_seconds=900,
        token_factory=lambda *_: "token",
    )
    finished_match = match.model_copy(update={"state": MatchStatus.RESULTS})

    try:
        configured.credentials_for(finished_match, player_a)
    except LiveKitError as error:
        assert "after the round" in str(error)
    else:
        raise AssertionError("Expected LiveKitError")
