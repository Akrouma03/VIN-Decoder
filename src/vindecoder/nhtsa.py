"""Client for the NHTSA vPIC vehicle API.

Two things about this API drive the design here:

* It answers ``200 OK`` even for a VIN it could not decode, reporting the real
  outcome in an ``Error Code`` field inside the payload. Checking the HTTP
  status alone is not enough.
* It is a free public service with no key and no published rate limit, so
  requests carry a timeout and failures are surfaced as a typed error rather
  than an unhandled traceback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"
DEFAULT_TIMEOUT = 15.0

#: Fields worth showing, in the order they make sense to read.
FIELDS_OF_INTEREST = (
    "Make", "Model", "Model Year", "Trim", "Series",
    "Body Class", "Vehicle Type", "Doors", "Seats",
    "Engine Model", "Engine Number of Cylinders", "Displacement (L)",
    "Engine Power (kW)", "Fuel Type - Primary", "Transmission Style",
    "Drive Type", "GVWR", "Curb Weight (lbs)", "Wheelbase (inches)",
    "Manufacturer Name", "Plant City", "Plant State", "Plant Country",
)

#: vPIC error codes that still carry usable data.
_SOFT_ERROR_CODES = {"0", "6", "8"}


class NhtsaError(RuntimeError):
    """The lookup could not be completed."""


class VinNotDecoded(NhtsaError):
    """The service answered but could not decode the VIN."""


@dataclass
class DecodedVehicle:
    """A decoded vehicle, with whatever fields the service returned."""

    vin: str
    fields: dict[str, str] = field(default_factory=dict)
    error_code: str = "0"
    error_text: str = ""

    @property
    def description(self) -> str:
        """A short human label, e.g. ``2003 Honda Accord``."""
        parts = [
            self.fields.get("Model Year"),
            self.fields.get("Make"),
            self.fields.get("Model"),
        ]
        return " ".join(p for p in parts if p) or "Unknown vehicle"

    def __bool__(self) -> bool:
        return bool(self.fields)


def decode_vin(
    vin: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    session: requests.Session | None = None,
) -> DecodedVehicle:
    """Look up ``vin`` with vPIC and return the fields worth showing.

    Raises:
        NhtsaError: the request failed or the response was not usable.
        VinNotDecoded: the service replied but rejected the VIN.
    """
    url = f"{BASE_URL}/decodevin/{vin}"
    getter = session.get if session is not None else requests.get

    try:
        response = getter(url, params={"format": "json"}, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise NhtsaError(f"NHTSA did not respond within {timeout:g}s.") from exc
    except requests.ConnectionError as exc:
        raise NhtsaError("Could not reach NHTSA. Check your connection.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise NhtsaError(f"NHTSA returned HTTP {status}.") from exc
    except requests.RequestException as exc:  # pragma: no cover - defensive
        raise NhtsaError(f"Request to NHTSA failed: {exc}") from exc

    try:
        payload: dict[str, Any] = response.json()
        results = payload["Results"]
    except (ValueError, KeyError, TypeError) as exc:
        raise NhtsaError("NHTSA returned a response in an unexpected format.") from exc

    values = {
        item.get("Variable"): item.get("Value")
        for item in results
        if isinstance(item, dict)
    }

    # The API answers 200 even when it cannot decode; the truth is in here.
    error_code = (values.get("Error Code") or "0").split(",")[0].strip()
    error_text = values.get("Error Text") or ""

    fields = {
        name: values[name]
        for name in FIELDS_OF_INTEREST
        if values.get(name) not in (None, "", "Not Applicable")
    }

    if error_code not in _SOFT_ERROR_CODES and not fields:
        raise VinNotDecoded(error_text or f"NHTSA could not decode {vin}.")

    return DecodedVehicle(
        vin=vin, fields=fields, error_code=error_code, error_text=error_text
    )
