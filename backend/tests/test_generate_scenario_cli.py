from types import SimpleNamespace

import generate_scenario


class FakeService:
    def generate_scenario(self):
        return SimpleNamespace(model_dump_json=lambda indent: '{\n  "tone": "wacky"\n}')


def test_cli_prints_the_generated_scenario(monkeypatch, capsys):
    monkeypatch.setattr(
        generate_scenario, "create_scenario_service", lambda _: FakeService()
    )

    assert generate_scenario.main() == 0
    assert capsys.readouterr().out == '{\n  "tone": "wacky"\n}\n'
