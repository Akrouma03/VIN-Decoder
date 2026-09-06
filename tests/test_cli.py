"""CLI behaviour: exit codes, output modes, and graceful degradation."""
import json

import pytest

from vindecoder import cli
from vindecoder.nhtsa import DecodedVehicle, NhtsaError

VALID_VIN = "1HGCM82633A004352"


@pytest.fixture
def fake_vehicle():
    return DecodedVehicle(
        vin=VALID_VIN,
        fields={"Make": "HONDA", "Model": "Accord", "Model Year": "2003"},
    )


class TestExitCodes:
    def test_valid_vin_offline_succeeds(self, capsys):
        assert cli.main([VALID_VIN, "--offline"]) == cli.EXIT_OK

    def test_invalid_vin_exits_one(self, capsys):
        assert cli.main(["NOTAVIN"]) == cli.EXIT_INVALID_VIN
        assert "Invalid VIN" in capsys.readouterr().err

    def test_lookup_failure_exits_two_but_still_prints(self, monkeypatch, capsys):
        """A network failure must not lose the offline results."""
        monkeypatch.setattr(
            cli, "decode_vin", lambda *a, **k: (_ for _ in ()).throw(NhtsaError("offline"))
        )
        assert cli.main([VALID_VIN]) == cli.EXIT_LOOKUP_FAILED

        captured = capsys.readouterr()
        assert "Model year     2003" in captured.out
        assert "Lookup unavailable" in captured.err


class TestOutput:
    def test_text_output_reports_check_digit(self, capsys):
        cli.main([VALID_VIN, "--offline"])
        out = capsys.readouterr().out
        assert "Check digit    3 (valid)" in out
        assert "Honda" in out

    def test_text_output_flags_a_bad_check_digit(self, capsys):
        cli.main(["5YJ3E1EA7HF000316", "--offline"])
        out = capsys.readouterr().out
        assert "MISMATCH" in out
        assert "expected X" in out

    def test_json_output_is_parseable(self, monkeypatch, capsys, fake_vehicle):
        monkeypatch.setattr(cli, "decode_vin", lambda *a, **k: fake_vehicle)
        cli.main([VALID_VIN, "--json"])

        payload = json.loads(capsys.readouterr().out)
        assert payload["offline"]["valid_check_digit"] is True
        assert payload["vehicle"]["fields"]["Make"] == "HONDA"

    def test_json_offline_has_no_vehicle_key(self, capsys):
        cli.main([VALID_VIN, "--offline", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert "vehicle" not in payload
        assert payload["offline"]["model_year"] == 2003

    def test_offline_flag_makes_no_network_call(self, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("--offline must not hit the network")

        monkeypatch.setattr(cli, "decode_vin", explode)
        assert cli.main([VALID_VIN, "--offline"]) == cli.EXIT_OK


class TestPrompt:
    def test_prompts_when_no_vin_given(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: VALID_VIN)
        assert cli.main(["--offline"]) == cli.EXIT_OK
        assert VALID_VIN in capsys.readouterr().out

    def test_cancelling_the_prompt_exits_cleanly(self, monkeypatch):
        def cancel(_):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", cancel)
        assert cli.main([]) == cli.EXIT_INVALID_VIN
