from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models import MatchState, MatchStatus, SwitchInventory
from app.services.game_service import GameService, GameStateError
from app.services.redis_service import InMemoryRedisService
from app.services.transcript_service import TranscriptService


def _active_match():
    storage = InMemoryRedisService()
    player_a = uuid4()
    player_b = uuid4()
    match = MatchState(
        match_id=uuid4(),
        player_a_id=player_a,
        player_b_id=player_b,
        state=MatchStatus.ROUND_ACTIVE,
        scenario=None,
        round_started_at=datetime.now(UTC),
        active_player_id="A",
        switches_remaining=SwitchInventory(A=5, B=5),
        transcript_events=[],
    )
    storage.save_match(match)
    return storage, match, player_a, player_b


def test_final_speech_is_authoritative_persisted_and_hands_off_the_turn():
    storage, match, player_a, _ = _active_match()
    game = GameService(storage, round_duration_ms=60_000)
    transcript = TranscriptService(game)

    transcript.speech_started(match.match_id, player_a, "speech_one")
    updated_match, event = transcript.speech_final("speech_one", "  Hello there  ")

    assert event.model_dump() == {
        "type": "speech",
        "id": "speech_one",
        "player_id": "A",
        "text": "Hello there",
        "start_ms": event.start_ms,
        "end_ms": event.end_ms,
        "is_final": True,
        "accepted": True,
        "truncated_by_switch": False,
        "truncated_by_round_end": False,
    }
    assert event.end_ms >= event.start_ms >= 0
    assert updated_match.active_player_id == "B"
    assert storage.get_match(match.match_id).transcript_events == [event]


def test_only_the_active_player_can_start_speech_and_unknown_final_is_rejected():
    storage, match, _, player_b = _active_match()
    transcript = TranscriptService(GameService(storage, round_duration_ms=60_000))

    with pytest.raises(GameStateError, match="active speaker"):
        transcript.speech_started(match.match_id, player_b, "speech_two")
    with pytest.raises(GameStateError, match="authoritative start"):
        transcript.speech_final("speech_missing", "No start")


def test_round_end_finalizes_latest_partial_at_the_authoritative_boundary():
    storage, match, player_a, _ = _active_match()
    game = GameService(storage, round_duration_ms=60_000)
    transcript = TranscriptService(game)

    transcript.speech_started(match.match_id, player_a, "speech_partial")
    transcript.speech_partial("speech_partial", "The latest partial")
    events = transcript.finalize_round(match.match_id)
    ended = game.end_round(match.match_id)

    assert len(events) == 1
    assert events[0].text == "The latest partial"
    assert events[0].end_ms == 60_000
    assert events[0].accepted is True
    assert events[0].truncated_by_round_end is True
    assert ended.transcript_events == events
    assert ended.active_player_id is None


def test_round_end_discards_speech_that_never_produced_text():
    storage, match, player_a, _ = _active_match()
    game = GameService(storage, round_duration_ms=60_000)
    transcript = TranscriptService(game)

    transcript.speech_started(match.match_id, player_a, "speech_silent")

    assert transcript.finalize_round(match.match_id) == []
    assert storage.get_match(match.match_id).transcript_events == []
