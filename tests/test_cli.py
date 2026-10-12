import pandas as pd

from carbon_aware_au import cli
from carbon_aware_au.intensity import Intensity


def fake(g):
    return lambda region, client=None: Intensity(region, g, 0.5, pd.Timestamp("2026-10-12 21:30", tz="Etc/GMT-10"))


def test_wait_runs_command_when_clean(monkeypatch):
    monkeypatch.setattr(cli, "current_intensity", fake(100))
    assert cli.main(["wait", "--region", "SA", "--below", "200", "--", "python", "-c", "raise SystemExit(7)"]) == 7


def test_wait_fails_on_timeout_when_asked(monkeypatch):
    monkeypatch.setattr(cli, "current_intensity", fake(900))
    code = cli.main(["wait", "--region", "NSW1", "--below", "200", "--max-wait", "0s", "--on-timeout", "fail",
                     "--", "python", "-c", "print('should not run')"])
    assert code == 1


def test_wait_runs_anyway_on_timeout_by_default(monkeypatch):
    monkeypatch.setattr(cli, "current_intensity", fake(900))
    assert cli.main(["wait", "--region", "NSW1", "--below", "200", "--max-wait", "0s", "--", "python", "-c", "pass"]) == 0


def test_double_dash_inside_the_command_is_preserved(monkeypatch):
    monkeypatch.setattr(cli, "current_intensity", fake(100))
    code = cli.main(["wait", "--region", "SA", "--below", "200", "--", "python", "-c",
                     "import sys; raise SystemExit(0 if sys.argv[1:] == ['--', 'x'] else 9)", "--", "x"])
    assert code == 0
