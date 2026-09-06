import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from app.models import JudgeResult, ScoringInput, TranscriptEvent
from app.models.transcript import SpeechEvent, SwitchEvent
from app.services.scoring_service import ScoringService

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "shared" / "fixtures"
MATCH_ID = UUID("3b241101-e2bb-4255-8caf-4136c566a962")

JUDGMENT = {
    "player_a": {
        "category_points": {
            "adaptability": 1900,
            "articulation": 1800,
            "coherence": 1700,
            "collaboration": 1600,
        },
        "highlight": "Turned the upside-down manual into a captain's ritual.",
        "improvement": "Invite the intern into the landing decision earlier.",
        "overview": "Used a confident recovery to keep the scene moving.",
    },
    "player_b": {
        "category_points": {
            "adaptability": 1600,
            "articulation": 1700,
            "coherence": 1600,
            "collaboration": 1600,
        },
        "highlight": "Used the upside-down manual to raise the stakes.",
        "improvement": "Commit to a specific landing plan sooner.",
        "overview": "Raised the stakes while leaving a clear opening for the partner.",
    },
    "highlight_events": [
        {
            "player_id": "A",
            "label": "GREAT RECOVERY",
            "points": 220,
            "transcript_event_ids": ["speech_003", "switch_001", "speech_004"],
        }
    ],
}


def _fixture_events() -> list[TranscriptEvent]:
    with (FIXTURE_DIR / "mock-transcript.json").open(encoding="utf-8") as handle:
        raw_events = json.load(handle)
    adapter = TypeAdapter(TranscriptEvent)
    return [adapter.validate_python(event) for event in raw_events]


def test_merges_semantic_judgment_with_deterministic_speed_and_selects_winner():
    result = ScoringService().score(
        ScoringInput(
            match_id=MATCH_ID,
            judgment=JudgeResult.model_validate(JUDGMENT),
            transcript_events=_fixture_events(),
            round_duration_ms=60_000,
        )
    )

    assert result.winner == "A"
    assert result.player_a.category_points.speed == 455
    assert result.player_a.total_points == 7455
    assert result.player_a.rubric_log.overview == "Used a confident recovery to keep the scene moving."
    assert result.player_a.rubric_log.articulation.rating == "STRONG"
    assert result.player_a.rubric_log.speed.points == 455
    assert result.player_a.rubric_log.speed.rating == "VERY LIMITED"
    assert result.player_b.category_points.speed == 0
    assert result.highlight_events[0].label == "GREAT RECOVERY"


def test_rapid_switches_only_credit_the_latest_switch_before_recovery():
    events = [
        SwitchEvent(
            type="switch",
            id="switch_first",
            from_player_id="B",
            target_player_id="A",
            timestamp_ms=100,
        ),
        SwitchEvent(
            type="switch",
            id="switch_second",
            from_player_id="B",
            target_player_id="A",
            timestamp_ms=200,
        ),
        SpeechEvent(
            type="speech",
            id="speech_recovery",
            player_id="A",
            text="A different choice.",
            start_ms=300,
            end_ms=600,
            is_final=True,
            accepted=True,
            truncated_by_switch=False,
            truncated_by_round_end=False,
        ),
    ]

    assert ScoringService.calculate_switch_response_latencies(events) == {
        "switch_first": None,
        "switch_second": 100,
    }


def test_speed_curve_is_bounded_and_rewards_faster_recovery():
    service = ScoringService(
        speed_base_points=500,
        speed_decay_points_per_second=120,
        speed_max_points=600,
    )

    assert service.speed_points_for_latency(0) == 500
    assert service.speed_points_for_latency(1_000) == 380
    assert service.speed_points_for_latency(5_000) == 0
    assert service.speed_points_for_latency(None) == 0


def test_player_speed_points_are_capped_across_multiple_switches():
    events = [
        SwitchEvent(
            type="switch",
            id="switch_one",
            from_player_id="B",
            target_player_id="A",
            timestamp_ms=100,
        ),
        SpeechEvent(
            type="speech",
            id="speech_one",
            player_id="A",
            text="First recovery.",
            start_ms=100,
            end_ms=120,
            is_final=True,
            accepted=True,
            truncated_by_switch=False,
            truncated_by_round_end=False,
        ),
        SwitchEvent(
            type="switch",
            id="switch_two",
            from_player_id="B",
            target_player_id="A",
            timestamp_ms=200,
        ),
        SpeechEvent(
            type="speech",
            id="speech_two",
            player_id="A",
            text="Second recovery.",
            start_ms=200,
            end_ms=220,
            is_final=True,
            accepted=True,
            truncated_by_switch=False,
            truncated_by_round_end=False,
        ),
    ]
    result = ScoringService(speed_max_points=600).score(
        ScoringInput(
            match_id=MATCH_ID,
            judgment=JudgeResult.model_validate(JUDGMENT),
            transcript_events=events,
            round_duration_ms=60_000,
        )
    )

    assert result.player_a.category_points.speed == 600


def test_equal_final_totals_are_explicitly_a_tie():
    tied_judgment = {
        **JUDGMENT,
        "player_b": {
            **JUDGMENT["player_a"],
            "highlight": "Matched the scene's strongest choice.",
        },
    }
    result = ScoringService().score(
        ScoringInput(
            match_id=MATCH_ID,
            judgment=JudgeResult.model_validate(tied_judgment),
            transcript_events=[],
            round_duration_ms=60_000,
        )
    )

    assert result.winner == "TIE"
    assert result.player_a.total_points == result.player_b.total_points
