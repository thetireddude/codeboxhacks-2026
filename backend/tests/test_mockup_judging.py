from app import create_app
from app.config import AppConfig
from app.models import JudgeResult
from app.services.scoring_service import ScoringService


class TestConfig(AppConfig):
    TESTING = True
    USE_IN_MEMORY_REDIS = True


class FakeJudge:
    def __init__(self):
        self.inputs = []

    def judge(self, judge_input):
        self.inputs.append(judge_input)
        return JudgeResult.model_validate(
            {
                "player_a": {
                    "category_points": {
                        "adaptability": 1000,
                        "articulation": 1100,
                        "coherence": 1200,
                        "collaboration": 1300,
                    },
                    "highlight": "Made a clear choice.",
                    "improvement": "Build with a partner sooner.",
                },
                "player_b": {
                    "category_points": {
                        "adaptability": 0,
                        "articulation": 0,
                        "coherence": 0,
                        "collaboration": 0,
                    },
                    "highlight": "Stayed available.",
                    "improvement": "Add dialogue to the scene.",
                },
                "highlight_events": [],
            }
        )


def test_mockup_submit_judges_the_final_transcript_and_returns_arcade_result():
    app = create_app(TestConfig)
    fake_judge = FakeJudge()
    app.extensions["judge_service"] = fake_judge
    app.extensions["scoring_service"] = ScoringService()
    client = app.test_client()

    response = client.post(
        "/api/mockup/judge",
        json={
            "transcript_events": [
                {
                    "type": "speech",
                    "id": "speech_mock_0",
                    "player_id": "A",
                    "text": "I will land this spaceship with a dance.",
                    "start_ms": 100,
                    "end_ms": 700,
                    "is_final": True,
                    "accepted": True,
                    "truncated_by_switch": False,
                    "truncated_by_round_end": False,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json["results"]["winner"] == "A"
    assert response.json["results"]["player_a"]["total_points"] == 4600
    assert fake_judge.inputs[0].scenario.player_a_role == "Overconfident captain"


def test_mockup_submit_rejects_a_transcript_without_final_accepted_speech():
    app = create_app(TestConfig)
    client = app.test_client()

    response = client.post("/api/mockup/judge", json={"transcript_events": []})

    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_TRANSCRIPT"
