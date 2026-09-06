"""Offline VIN parsing and validation (ISO 3779 / ISO 3780).

A VIN carries enough structure to be validated and partly decoded without any
network call: the ninth character is a check digit computed from the other
sixteen, and the manufacturer, model year and assembly plant are encoded in
fixed positions.

Doing this locally means an invalid VIN is rejected before an API request is
made, and the parts of a VIN that are defined by standard are decoded the same
way regardless of which registry (if any) knows the vehicle.

    >>> vin = Vin("1HGCM82633A004352")
    >>> vin.is_valid
    True
    >>> vin.model_year
    2003
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VIN_LENGTH = 17

#: I, O and Q are excluded from VINs to avoid confusion with 1 and 0.
INVALID_LETTERS = frozenset("IOQ")
VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

#: Letter -> numeric value for the check-digit calculation (ISO 3779).
TRANSLITERATION = {
    **{c: i for i, c in enumerate("ABCDEFGH", start=1)},
    **{c: i for i, c in enumerate("JKLMN", start=1)},
    "P": 7,
    "R": 9,
    **{c: i for i, c in enumerate("STUVWXYZ", start=2)},
}

#: Positional weights, index 0 -> first character.
WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

CHECK_DIGIT_INDEX = 8
MODEL_YEAR_INDEX = 9
PLANT_INDEX = 10

#: Model-year codes cycle every 30 years, skipping I, O, Q, U, Z and 0.
YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"

#: Leading WMI characters by manufacturing region (ISO 3780).
REGIONS = (
    ("Africa", set("ABCDEFGH")),
    ("Asia", set("JKLMNPR")),
    ("Europe", set("STUVWXYZ")),
    ("North America", set("12345")),
    ("Oceania", set("67")),
    ("South America", set("89")),
)

#: A small sample of common World Manufacturer Identifiers. The NHTSA lookup is
#: authoritative; this is here so the offline path can still name the obvious ones.
KNOWN_WMI = {
    "1FA": "Ford", "1FT": "Ford", "1G1": "Chevrolet", "1GC": "Chevrolet",
    "1HG": "Honda", "1N4": "Nissan", "2T1": "Toyota", "3VW": "Volkswagen",
    "4T1": "Toyota", "5YJ": "Tesla", "JHM": "Honda", "JN1": "Nissan",
    "JTD": "Toyota", "KMH": "Hyundai", "KNA": "Kia", "SAJ": "Jaguar",
    "SAL": "Land Rover", "SCC": "Lotus", "TRU": "Audi", "VF1": "Renault",
    "WAU": "Audi", "WBA": "BMW", "WDB": "Mercedes-Benz", "WDD": "Mercedes-Benz",
    "WP0": "Porsche", "WVW": "Volkswagen", "YV1": "Volvo", "ZFF": "Ferrari",
}


class InvalidVin(ValueError):
    """Raised when a string cannot be a VIN at all."""


@dataclass(frozen=True)
class Vin:
    """A 17-character VIN, parsed as far as the standard allows offline."""

    raw: str

    def __post_init__(self) -> None:
        normalised = self.raw.strip().upper().replace(" ", "").replace("-", "")
        object.__setattr__(self, "raw", normalised)

        if len(normalised) != VIN_LENGTH:
            raise InvalidVin(
                f"A VIN is {VIN_LENGTH} characters; got {len(normalised)}."
            )
        bad = sorted(set(normalised) & INVALID_LETTERS)
        if bad:
            raise InvalidVin(
                f"A VIN never contains {', '.join(bad)} "
                "(I, O and Q are excluded to avoid confusion with 1 and 0)."
            )
        if not VIN_PATTERN.match(normalised):
            raise InvalidVin("A VIN contains only letters and digits.")

    # -- structural parts -------------------------------------------------

    @property
    def wmi(self) -> str:
        """World Manufacturer Identifier (characters 1-3)."""
        return self.raw[:3]

    @property
    def vds(self) -> str:
        """Vehicle Descriptor Section (characters 4-9)."""
        return self.raw[3:9]

    @property
    def vis(self) -> str:
        """Vehicle Identifier Section (characters 10-17)."""
        return self.raw[9:]

    @property
    def serial(self) -> str:
        """Production serial number (characters 12-17)."""
        return self.raw[11:]

    # -- validation -------------------------------------------------------

    @property
    def check_digit(self) -> str:
        """The check digit actually present in position 9."""
        return self.raw[CHECK_DIGIT_INDEX]

    @property
    def expected_check_digit(self) -> str:
        """The check digit implied by the other sixteen characters."""
        total = sum(
            _char_value(char) * weight
            for char, weight in zip(self.raw, WEIGHTS)
        )
        remainder = total % 11
        return "X" if remainder == 10 else str(remainder)

    @property
    def is_valid(self) -> bool:
        """Whether the check digit matches.

        Note: North American VINs must carry a correct check digit, but it is
        not universally enforced elsewhere, so a mismatch is a strong warning
        rather than proof of a fake.
        """
        return self.check_digit == self.expected_check_digit

    # -- decoded fields ---------------------------------------------------

    @property
    def region(self) -> str:
        first = self.raw[0]
        for name, chars in REGIONS:
            if first in chars:
                return name
        return "Unknown"

    @property
    def manufacturer(self) -> str | None:
        """Manufacturer from the WMI, if it is one of the known prefixes."""
        return KNOWN_WMI.get(self.wmi)

    @property
    def model_year(self) -> int | None:
        """Model year decoded from position 10.

        The code repeats every 30 years, so a single VIN is ambiguous. Position
        7 disambiguates: a digit there means 1980-2009, a letter means 2010+.
        """
        code = self.raw[MODEL_YEAR_INDEX]
        if code not in YEAR_CODES:
            return None
        offset = YEAR_CODES.index(code)
        year = 1980 + offset
        if self.raw[6].isalpha():
            year += 30
        return year

    @property
    def plant_code(self) -> str:
        """Assembly plant code (character 11), manufacturer-specific."""
        return self.raw[PLANT_INDEX]

    def summary(self) -> dict[str, object]:
        """Everything derivable without a network call."""
        return {
            "vin": self.raw,
            "valid_check_digit": self.is_valid,
            "expected_check_digit": self.expected_check_digit,
            "wmi": self.wmi,
            "manufacturer": self.manufacturer,
            "region": self.region,
            "model_year": self.model_year,
            "plant_code": self.plant_code,
            "serial": self.serial,
        }

    def __str__(self) -> str:
        return self.raw


def _char_value(char: str) -> int:
    return int(char) if char.isdigit() else TRANSLITERATION[char]


def is_plausible_vin(candidate: str) -> bool:
    """True when the string could be a VIN, without raising."""
    try:
        Vin(candidate)
    except InvalidVin:
        return False
    return True
