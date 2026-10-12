import httpx
import pandas as pd
import pytest

from carbon_aware_au.intensity import Intensity, intensity_from_units, normalise_region
from carbon_aware_au.waiter import parse_duration, wait_for_clean


def reading(g: float) -> Intensity:
    return Intensity("NSW1", g, 0.3, pd.Timestamp("2026-10-12 21:30", tz="Etc/GMT-10"))


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(readings, **kw):
    clock = FakeClock()
    it = iter(readings)

    def get():
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return reading(v)

    return wait_for_clean(get, sleep=clock.sleep, now=clock.now, **kw), clock


def test_runs_immediately_when_already_clean():
    r, clock = run([300], below=400, max_wait_s=3600)
    assert r.reason == "below_threshold" and r.waited_s == 0 and clock.t == 0


def test_waits_until_below_threshold():
    r, clock = run([600, 520, 450, 390], below=400, max_wait_s=7200, poll_s=300)
    assert r.ok_to_run and r.waited_s == 900 and r.history == [600, 520, 450, 390]


def test_times_out_at_deadline_without_overshooting():
    r, clock = run([600] * 50, below=400, max_wait_s=1000, poll_s=300)
    assert r.reason == "timeout" and r.waited_s == pytest.approx(1000) and not r.ok_to_run


def test_retries_transient_errors_then_succeeds():
    r, _ = run([httpx.ConnectError("boom"), httpx.ConnectError("boom"), 350], below=400, max_wait_s=3600)
    assert r.ok_to_run


def test_gives_up_after_repeated_errors():
    r, _ = run([httpx.ConnectError("down")] * 10, below=400, max_wait_s=3600, max_errors=3)
    assert r.reason == "unavailable"


@pytest.mark.parametrize("text,secs", [("90s", 90), ("15m", 900), ("6h", 21600), ("1h30m", 5400), ("45", 45)])
def test_parse_duration(text, secs):
    assert parse_duration(text) == secs


def test_parse_duration_rejects_nonsense():
    with pytest.raises(ValueError):
        parse_duration("soon")


def test_region_aliases():
    assert normalise_region("nsw") == "NSW1" and normalise_region("SA1") == "SA1"
    with pytest.raises(ValueError):
        normalise_region("WA")


def test_intensity_is_generation_weighted_and_in_g_per_kwh():
    units = pd.DataFrame(
        {
            "interval_end": [pd.Timestamp("2026-10-12 21:30", tz="Etc/GMT-10")] * 3,
            "duid": ["C", "W", "G"],
            "mw": [100.0, 100.0, 100.0],
            "region": ["NSW1"] * 3,
            "ef_t_per_mwh": [0.9, 0.0, 0.5],
            "fuel": ["Black coal", "Wind", "Gas"],
        }
    )
    i = intensity_from_units(units, "NSW1")
    assert i.g_per_kwh == pytest.approx((0.9 + 0 + 0.5) / 3 * 1000)
    assert i.renewable_share == pytest.approx(1 / 3)


def test_nan_intensity_is_unavailable_not_dirty():
    r, _ = run([float("nan")] * 10, below=400, max_wait_s=3600, max_errors=3)
    assert r.reason == "unavailable"


def test_programming_errors_are_not_swallowed():
    with pytest.raises(AttributeError):
        run([AttributeError("bug")], below=400, max_wait_s=60)
