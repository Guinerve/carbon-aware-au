"""Run a command when the grid in your NEM region is cleaner.

carbon-aware-au reads the latest 5-minute generation data from AEMO NEMWeb. It calculates the
average emissions intensity of generation in a region, in g CO2e/kWh.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from .intensity import current_intensity, normalise_region
from .waiter import DATA_ERRORS, parse_duration, wait_for_clean

REASON_TEXT = {
    "below_threshold": "Grid is at or below the threshold",
    "timeout": "Deadline reached",
    "unavailable": "Grid data is not available",
}


def _log(msg: str) -> None:
    print(f"[carbon-aware-au] {msg}", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="carbon-aware-au",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    now = sub.add_parser("now", help="Show the current emissions intensity")
    now.add_argument(
        "--region", default=None, help="NSW1, QLD1, VIC1, SA1 or TAS1 (default: all regions)"
    )

    w = sub.add_parser(
        "wait",
        help="Wait until the grid is clean enough, then run a command",
        description="Wait until the grid is clean enough, then run the command after --.",
    )
    w.add_argument("--region", required=True, help="NSW1, QLD1, VIC1, SA1 or TAS1")
    w.add_argument(
        "--below", type=float, required=True, help="Threshold in g CO2e/kWh (400 = 0.4 t/MWh)"
    )
    w.add_argument("--max-wait", default="6h", help="Longest time to wait, for example 90m or 6h")
    w.add_argument(
        "--poll", default="5m", help="Time between checks (AEMO data changes every 5 minutes)"
    )
    w.add_argument(
        "--on-timeout",
        choices=["run", "fail"],
        default="run",
        help="At the deadline: run the command (default) or exit with code 1",
    )
    w.add_argument(
        "--on-unavailable",
        choices=["run", "fail"],
        default="run",
        help="If grid data cannot be read: run the command (default) or exit with code 1",
    )
    w.add_argument("command", nargs=argparse.REMAINDER, help="The command to run, after --")
    return p


def _now(parser: argparse.ArgumentParser, region: str | None) -> int:
    from nem import NemClient
    from nem.client import REGIONS

    from .intensity import intensity_from_units

    try:
        regions = [normalise_region(region)] if region else REGIONS
    except ValueError as exc:
        parser.error(str(exc))
    try:
        units = NemClient().generation_by_unit()
        readings = [intensity_from_units(units, r) for r in regions]
    except DATA_ERRORS as exc:
        _log(f"could not read grid data: {exc}")
        return 1
    for i in readings:
        print(
            f"{i.region:5s} {i.g_per_kwh:6.0f} g/kWh   renewables {i.renewable_share:4.0%}   "
            f"{i.interval_end:%Y-%m-%d %H:%M} NEM time"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "now":
        return _now(parser, args.region)

    # Remove only the separator. A "--" inside the command stays.
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        region = normalise_region(args.region)
        max_wait_s = parse_duration(args.max_wait)
        poll_s = parse_duration(args.poll)
    except ValueError as exc:
        parser.error(str(exc))
    if poll_s <= 0:
        parser.error("--poll must be more than zero")

    result = wait_for_clean(
        lambda: current_intensity(region),
        below=args.below,
        max_wait_s=max_wait_s,
        poll_s=poll_s,
        log=_log,
    )
    _log(f"{REASON_TEXT[result.reason]} after {result.waited_s / 60:.1f} min")
    if not result.ok_to_run:
        policy = args.on_timeout if result.reason == "timeout" else args.on_unavailable
        if policy == "fail":
            _log("Stopping without running the command (exit code 1)")
            return 1
        if cmd:
            _log("Running the command anyway")
    if not cmd:
        return 0
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        _log(f"command not found: {cmd[0]}")
        return 127
    except PermissionError:
        _log(f"command is not executable: {cmd[0]}")
        return 126


if __name__ == "__main__":
    raise SystemExit(main())
