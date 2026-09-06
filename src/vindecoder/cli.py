"""Command-line interface for the VIN decoder.

    vin-decode 1HGCM82633A004352
    vin-decode 1HGCM82633A004352 --offline
    vin-decode 1HGCM82633A004352 --json
    vin-decode                       # prompts for a VIN
"""
from __future__ import annotations

import argparse
import json
import sys

from .nhtsa import DecodedVehicle, NhtsaError, decode_vin
from .vin import InvalidVin, Vin

EXIT_OK = 0
EXIT_INVALID_VIN = 1
EXIT_LOOKUP_FAILED = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vin-decode",
        description="Validate and decode a Vehicle Identification Number.",
        epilog="Offline checks need no network; the NHTSA lookup adds full specs.",
    )
    parser.add_argument("vin", nargs="?", help="17-character VIN")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the NHTSA lookup and report only what the VIN itself encodes",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument(
        "--timeout", type=float, default=15.0, help="NHTSA timeout in seconds"
    )
    return parser


def render_text(vin: Vin, vehicle: DecodedVehicle | None) -> str:
    lines = [""]
    if vehicle is not None:
        lines.append(f"  {vehicle.description}")
        lines.append("")

    tick = "valid" if vin.is_valid else "MISMATCH"
    lines.append(f"  VIN            {vin}")
    lines.append(f"  Check digit    {vin.check_digit} ({tick})")
    if not vin.is_valid:
        lines.append(f"                 expected {vin.expected_check_digit}")
    lines.append(f"  Manufacturer   {vin.manufacturer or vin.wmi + ' (unrecognised WMI)'}")
    lines.append(f"  Region         {vin.region}")
    lines.append(f"  Model year     {vin.model_year or 'unknown'}")
    lines.append(f"  Serial         {vin.serial}")

    if vehicle is not None and vehicle.fields:
        lines.append("")
        width = max(len(k) for k in vehicle.fields)
        for key, value in vehicle.fields.items():
            lines.append(f"  {key.ljust(width)}   {value}")

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    raw = args.vin
    if not raw:
        try:
            raw = input("Enter a 17-character VIN: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return EXIT_INVALID_VIN

    try:
        vin = Vin(raw)
    except InvalidVin as exc:
        print(f"Invalid VIN: {exc}", file=sys.stderr)
        return EXIT_INVALID_VIN

    vehicle: DecodedVehicle | None = None
    lookup_error: str | None = None
    if not args.offline:
        try:
            vehicle = decode_vin(str(vin), timeout=args.timeout)
        except NhtsaError as exc:
            lookup_error = str(exc)

    if args.json:
        payload: dict[str, object] = {"offline": vin.summary()}
        if vehicle is not None:
            payload["vehicle"] = {
                "description": vehicle.description,
                "fields": vehicle.fields,
            }
        if lookup_error:
            payload["lookup_error"] = lookup_error
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(vin, vehicle))
        if lookup_error:
            print(f"  Lookup unavailable: {lookup_error}", file=sys.stderr)
            print("  Offline results shown above.\n", file=sys.stderr)

    if lookup_error:
        return EXIT_LOOKUP_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
