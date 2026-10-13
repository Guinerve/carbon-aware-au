"""Poll until the grid is clean enough, or give up after a deadline."""

from __future__ import annotations

import re
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx
from nem import NemDataError

from .intensity import Intensity

Reason = Literal["below_threshold", "timeout", "unavailable"]

# Failures to read grid data. These are retried. Programming errors still raise.
DATA_ERRORS = (
    NemDataError,
    OSError,
    ValueError,
    KeyError,
    IndexError,
    StopIteration,
    zipfile.BadZipFile,
    httpx.HTTPError,
)


@dataclass
class WaitResult:
    reason: Reason
    waited_s: float
    last: Intensity | None
    history: list[float] = field(default_factory=list)

    @property
    def ok_to_run(self) -> bool:
        return self.reason == "below_threshold"


def parse_duration(text: str) -> float:
    """'90s', '15m', '6h', '1h30m' or a bare number of seconds -> seconds."""
    text = text.strip().lower()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    parts = re.findall(r"(\d+(?:\.\d+)?)([smhd])", text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise ValueError(f"Cannot parse duration {text!r}; try 30m, 6h or 1h30m")
    unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return sum(float(n) * unit[u] for n, u in parts)


def wait_for_clean(
    get_intensity: Callable[[], Intensity],
    below: float,
    max_wait_s: float,
    poll_s: float = 300,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = lambda _: None,
    max_errors: int = 5,
) -> WaitResult:
    """Return as soon as intensity <= `below`.

    Data errors are retried. After `max_errors` consecutive failures, or at the deadline with no
    reading at all, the result is "unavailable", so callers can fail open or closed.
    """
    start = now()
    history: list[float] = []
    last: Intensity | None = None
    errors = 0
    while True:
        try:
            last = get_intensity()
            if last.g_per_kwh != last.g_per_kwh:  # NaN: no generation data for the region
                raise ValueError("no generation data for the region")
            errors = 0
            history.append(last.g_per_kwh)
            log(
                f"{last.region}: {last.g_per_kwh:.0f} g/kWh (target {below:.0f} or less), "
                f"renewables {last.renewable_share:.0%}"
            )
            if last.g_per_kwh <= below:
                return WaitResult("below_threshold", now() - start, last, history)
        except DATA_ERRORS as exc:
            errors += 1
            log(f"could not read grid data ({exc}); attempt {errors}/{max_errors}")
            if errors >= max_errors:
                return WaitResult("unavailable", now() - start, last, history)
        waited = now() - start
        if waited >= max_wait_s:
            return WaitResult("timeout" if history else "unavailable", waited, last, history)
        sleep(min(poll_s, max(0.0, max_wait_s - waited)))
