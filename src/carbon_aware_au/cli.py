from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from .intensity import current_intensity, normalise_region
from .waiter import parse_duration, wait_for_clean


def _log(msg: str) -> None:
    print(f"[carbon-aware-au] {msg}", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="carbon-aware-au", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    now = sub.add_parser("now", help="Show current average emissions intensity")
    now.add_argument("--region", default=None, help="NSW1, QLD1, VIC1, SA1, TAS1 (default: all)")

    w = sub.add_parser("wait", help="Wait for a clean grid, then run a command (after --)")
    w.add_argument("--region", required=True)
    w.add_argument("--below", type=float, required=True, help="Threshold in g CO2e/kWh")
    w.add_argument("--max-wait", default="6h", help="Give up waiting after this long (e.g. 90m, 6h)")
    w.add_argument("--poll", default="5m", help="How often to check (data updates every 5 minutes)")
    w.add_argument("--on-timeout", choices=["run", "fail"], default="run",
                   help="Run the command anyway when the deadline passes (default), or exit 1")
    w.add_argument("--on-unavailable", choices=["run", "fail"], default="run",
                   help="What to do if grid data can't be read")
    w.add_argument("command", nargs=argparse.REMAINDER, help="-- command to run")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = build_parser().parse_args(argv)

    if args.cmd == "now":
        from nem import NemClient
        from nem.client import REGIONS

        from .intensity import intensity_from_units

        units = NemClient().generation_by_unit()
        for r in [normalise_region(args.region)] if args.region else REGIONS:
            i = intensity_from_units(units, r)
            print(f"{r:5s} {i.g_per_kwh:6.0f} g/kWh   renewables {i.renewable_share:4.0%}   {i.interval_end:%Y-%m-%d %H:%M} NEM time")
        return 0

    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command  # only the separator, never "--" inside the command
    region = normalise_region(args.region)
    result = wait_for_clean(
        lambda: current_intensity(region),
        below=args.below,
        max_wait_s=parse_duration(args.max_wait),
        poll_s=parse_duration(args.poll),
        log=_log,
    )
    _log(f"{result.reason} after {result.waited_s / 60:.1f} min")
    if not result.ok_to_run:
        policy = args.on_timeout if result.reason == "timeout" else args.on_unavailable
        if policy == "fail":
            return 1
    if not cmd:
        return 0
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
