import pandas as pd
import pytest
from nem import NemClient, NemDataError

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


@pytest.mark.parametrize(
    "argv",
    [
        ["wait", "--region", "WA", "--below", "200"],
        ["wait", "--region", "SA", "--below", "200", "--max-wait", "soon"],
        ["wait", "--region", "SA", "--below", "200", "--poll", "0"],
        ["now", "--region", "WA"],
    ],
)
def test_bad_input_is_a_usage_error_not_a_traceback(argv, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_intensity", fake(100))
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_missing_command_exits_127_with_a_message(monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_intensity", fake(100))
    code = cli.main(["wait", "--region", "SA", "--below", "200", "--", "no-such-command-xyz"])
    assert code == 127
    assert "no-such-command-xyz" in capsys.readouterr().err


def test_now_reports_unreadable_grid_data_without_a_traceback(monkeypatch, capsys):
    def broken(self):
        raise NemDataError("no report files listed")

    monkeypatch.setattr(NemClient, "generation_by_unit", broken)
    assert cli.main(["now"]) == 1
    assert "could not read grid data" in capsys.readouterr().err
