"""Offline VIN parsing and validation.

The check-digit cases use real VINs whose validity was cross-checked against
NHTSA's own verdict, but the tests themselves make no network calls.
"""
import pytest

from vindecoder.vin import Vin, InvalidVin, is_plausible_vin

# VINs NHTSA reports as "Check Digit (9th position) is correct".
VALID_VINS = [
    "1HGCM82633A004352",  # 2003 Honda Accord
    "JH4KA7561PC008269",  # 1993 Acura Legend
]

# Structurally legal VINs whose check digit does not compute.
BAD_CHECK_DIGIT_VINS = [
    "5YJ3E1EA7HF000316",
    "1FTFW1ET5DFC10312",
    "WVWZZZ1JZ3W386752",
]


class TestConstruction:
    def test_normalises_case_and_separators(self):
        assert str(Vin(" 1hgcm826-33a004352 ")) == "1HGCM82633A004352"

    @pytest.mark.parametrize("bad", ["", "SHORT", "1HGCM82633A00435", "1HGCM82633A0043521"])
    def test_rejects_wrong_length(self, bad):
        with pytest.raises(InvalidVin, match="17 characters"):
            Vin(bad)

    @pytest.mark.parametrize("letter", ["I", "O", "Q"])
    def test_rejects_forbidden_letters(self, letter):
        # I, O and Q are excluded from the VIN alphabet by standard.
        candidate = "1HGCM8263" + letter + "A00435 2".replace(" ", "")
        with pytest.raises(InvalidVin, match="never contains"):
            Vin(candidate[:17])

    def test_rejects_punctuation(self):
        with pytest.raises(InvalidVin):
            Vin("1HGCM8263*A004352")

    def test_is_plausible_vin_does_not_raise(self):
        assert is_plausible_vin("1HGCM82633A004352")
        assert not is_plausible_vin("nonsense")


class TestCheckDigit:
    @pytest.mark.parametrize("vin", VALID_VINS)
    def test_accepts_correct_check_digits(self, vin):
        assert Vin(vin).is_valid

    @pytest.mark.parametrize("vin", BAD_CHECK_DIGIT_VINS)
    def test_detects_incorrect_check_digits(self, vin):
        parsed = Vin(vin)
        assert not parsed.is_valid
        assert parsed.check_digit != parsed.expected_check_digit

    def test_expected_check_digit_is_a_single_character(self):
        for vin in VALID_VINS + BAD_CHECK_DIGIT_VINS:
            expected = Vin(vin).expected_check_digit
            assert expected in "0123456789X"

    def test_altering_a_character_breaks_validity(self):
        """The point of a check digit: a typo should be detectable."""
        original = Vin("1HGCM82633A004352")
        assert original.is_valid
        typo = "1HGCM82633A004353"  # last character changed
        assert not Vin(typo).is_valid


class TestDecodedFields:
    def test_sections_partition_the_vin(self):
        vin = Vin("1HGCM82633A004352")
        assert vin.wmi == "1HG"
        assert vin.vds == "CM8263"
        assert vin.vis == "3A004352"
        assert vin.wmi + vin.vds + vin.vis == str(vin)

    def test_identifies_manufacturer_from_wmi(self):
        assert Vin("1HGCM82633A004352").manufacturer == "Honda"
        assert Vin("5YJ3E1EA7HF000316").manufacturer == "Tesla"

    def test_unknown_wmi_returns_none(self):
        assert Vin("JH4KA7561PC008269").manufacturer is None

    @pytest.mark.parametrize(
        "vin,region",
        [
            ("1HGCM82633A004352", "North America"),
            ("JH4KA7561PC008269", "Asia"),
            ("WVWZZZ1JZ3W386752", "Europe"),
        ],
    )
    def test_region_from_first_character(self, vin, region):
        assert Vin(vin).region == region

    def test_model_year(self):
        assert Vin("1HGCM82633A004352").model_year == 2003
        assert Vin("JH4KA7561PC008269").model_year == 1993

    def test_summary_is_json_safe(self):
        import json

        summary = Vin("1HGCM82633A004352").summary()
        json.dumps(summary)  # must not raise
        assert summary["vin"] == "1HGCM82633A004352"
        assert summary["valid_check_digit"] is True
