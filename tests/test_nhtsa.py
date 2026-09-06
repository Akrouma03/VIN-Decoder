"""NHTSA client behaviour, with the network stubbed out.

The headline case is ``test_raises_when_api_reports_an_undecodable_vin``: vPIC
answers 200 OK even when it cannot decode a VIN, so trusting the HTTP status
alone silently yields an empty result.
"""
import json

import pytest
import requests

from vindecoder.nhtsa import NhtsaError, VinNotDecoded, decode_vin

VIN = "1HGCM82633A004352"


def make_response(variables: dict, status: int = 200, body: str | None = None):
    """Build a stand-in for a requests.Response carrying vPIC-shaped JSON."""

    class FakeResponse:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                raise requests.HTTPError(response=self)

        def json(self):
            if body is not None:
                return json.loads(body)
            return {
                "Count": len(variables),
                "Results": [{"Variable": k, "Value": v} for k, v in variables.items()],
            }

    return FakeResponse()


class FakeSession:
    """Session stub whose .get returns a queued response or raises."""

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self._error is not None:
            raise self._error
        return self._response


class TestSuccessfulDecode:
    def test_extracts_fields_of_interest(self):
        session = FakeSession(make_response({
            "Error Code": "0",
            "Error Text": "0 - VIN decoded clean.",
            "Make": "HONDA",
            "Model": "Accord",
            "Model Year": "2003",
            "Body Class": "Coupe",
            "Some Field We Ignore": "noise",
        }))
        vehicle = decode_vin(VIN, session=session)

        assert vehicle.fields["Make"] == "HONDA"
        assert vehicle.description == "2003 HONDA Accord"
        assert "Some Field We Ignore" not in vehicle.fields

    def test_drops_empty_and_not_applicable_values(self):
        session = FakeSession(make_response({
            "Error Code": "0",
            "Make": "HONDA",
            "Trim": "",
            "Series": None,
            "Doors": "Not Applicable",
        }))
        vehicle = decode_vin(VIN, session=session)

        assert set(vehicle.fields) == {"Make"}

    def test_sends_a_timeout(self):
        session = FakeSession(make_response({"Error Code": "0", "Make": "HONDA"}))
        decode_vin(VIN, timeout=3.0, session=session)

        assert session.calls[0]["timeout"] == 3.0
        assert VIN in session.calls[0]["url"]


class TestErrorHandling:
    def test_raises_when_api_reports_an_undecodable_vin(self):
        """200 OK with an error code and no data must not look like success."""
        session = FakeSession(make_response({
            "Error Code": "11",
            "Error Text": "11 - Incorrect Model Year",
        }))
        with pytest.raises(VinNotDecoded, match="Incorrect Model Year"):
            decode_vin(VIN, session=session)

    def test_timeout_becomes_a_typed_error(self):
        session = FakeSession(error=requests.Timeout())
        with pytest.raises(NhtsaError, match="did not respond"):
            decode_vin(VIN, timeout=5, session=session)

    def test_connection_failure_becomes_a_typed_error(self):
        session = FakeSession(error=requests.ConnectionError())
        with pytest.raises(NhtsaError, match="Could not reach"):
            decode_vin(VIN, session=session)

    def test_http_error_becomes_a_typed_error(self):
        session = FakeSession(make_response({}, status=503))
        with pytest.raises(NhtsaError, match="HTTP 503"):
            decode_vin(VIN, session=session)

    def test_malformed_json_becomes_a_typed_error(self):
        session = FakeSession(make_response({}, body="not json at all"))
        with pytest.raises(NhtsaError, match="unexpected format"):
            decode_vin(VIN, session=session)

    def test_missing_results_key_becomes_a_typed_error(self):
        session = FakeSession(make_response({}, body='{"Count": 0}'))
        with pytest.raises(NhtsaError, match="unexpected format"):
            decode_vin(VIN, session=session)
