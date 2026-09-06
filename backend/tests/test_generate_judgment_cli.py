from types import SimpleNamespace

import generate_judgment


class FakeService:
    def judge(self, judge_input):
        assert judge_input.round_duration_ms == 60_000
        return SimpleNamespace(model_dump_json=lambda indent: '{\n  "player_a": {}\n}')


def test_cli_prints_the_generated_judgment(monkeypatch, capsys):
    monkeypatch.setattr(
        generate_judgment, "create_judge_service", lambda _: FakeService()
    )

    assert generate_judgment.main() == 0
    assert capsys.readouterr().out == '{\n  "player_a": {}\n}\n'
