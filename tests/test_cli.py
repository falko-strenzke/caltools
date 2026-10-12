from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from caltools import cli
from caltools.caldav_client import Busy, CalDAVError

TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[defaults]\ncalendar = "work"\noff_days = ["fri", "sat", "sun"]\ntimezone = "Europe/Berlin"\n'
        '[calendars.work]\nurl = "https://x/"\ncalendar = "Work"\n'
        '[calendars.other]\nurl = "https://y/"\ncalendar = "Other"\n'
    )
    return path


@pytest.fixture
def fake_fetch(monkeypatch):
    calls = []

    def fetch(cfg, first, last, tz, all_day_blocks=True):
        calls.append((cfg.name, first, last, tz, all_day_blocks))
        return [Busy(datetime(2026, 10, 13, 10, tzinfo=TZ), datetime(2026, 10, 13, 11, tzinfo=TZ), "Call")]

    monkeypatch.setattr(cli, "fetch_busy", fetch)
    return calls


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_free_default_calendar_and_config_off_days(config_path, fake_fetch, capsys):
    code, out, _ = run(capsys, "-c", str(config_path), "free", "2026-10-12", "18.10.2026")
    assert code == 0
    assert fake_fetch == [("work", date(2026, 10, 12), date(2026, 10, 18), TZ, True)]
    assert out.splitlines() == [
        "Freie Zeiten vom 12.10.2026 bis 18.10.2026 (Arbeitszeit 09:00–17:00):",
        "",
        "Mo, 12.10.2026: ganztägig frei",
        "Di, 13.10.2026: 09:00–10:00, 11:00–17:00",
        "Mi, 14.10.2026: ganztägig frei",
        "Do, 15.10.2026: ganztägig frei",
    ]


def test_free_days_weekday_overrides_config(config_path, fake_fetch, capsys):
    code, out, _ = run(capsys, "-c", str(config_path), "free", "--days", "weekday", "-l", "en", "2026-10-12", "2026-10-18")
    assert code == 0
    assert "Fri, 16 Oct 2026: free all day" in out
    assert "Sat" not in out


def test_free_days_all_and_list(config_path, fake_fetch, capsys):
    _, out, _ = run(capsys, "-c", str(config_path), "free", "--days", "all", "2026-10-17", "2026-10-18")
    assert "Sa, 17.10.2026" in out and "So, 18.10.2026" in out
    _, out, _ = run(capsys, "-c", str(config_path), "free", "--days", "mon,wed", "2026-10-12", "2026-10-18")
    assert [line[:2] for line in out.splitlines()[2:]] == ["Mo", "Mi"]


def test_free_options_and_verbose(config_path, fake_fetch, capsys):
    code, out, _ = run(
        capsys, "-c", str(config_path), "free", "-C", "other", "--start", "8:00", "--end", "12:00",
        "--min", "90", "-v", "2026-10-13", "2026-10-13",
    )
    assert code == 0
    assert fake_fetch[0][0] == "other"
    assert "# 1 busy interval(s) from calendar 'other':" in out
    assert "13.10.2026 10:00 - 13.10.2026 11:00  Call" in out
    # 08:00-10:00 (120 min) kept, 11:00-12:00 (60 min) dropped by --min 90
    assert out.splitlines()[-1] == "Di, 13.10.2026: 08:00–10:00"


@pytest.mark.parametrize("argv, message", [
    (["free", "2026-13-01", "2026-10-02"], "invalid date"),
    (["free", "2026-10-05", "2026-10-02"], "TO must not be before FROM"),
    (["free", "--days", "funday", "2026-10-05", "2026-10-06"], "--days"),
    (["free", "--start", "12:00", "--end", "11:00", "2026-10-05", "2026-10-06"], "start must be before"),
    (["free", "--min", "-5", "2026-10-05", "2026-10-06"], "--min"),
    (["free", "-C", "nope", "2026-10-05", "2026-10-06"], "unknown calendar 'nope'"),
])
def test_free_usage_errors(config_path, fake_fetch, capsys, argv, message):
    code, out, err = run(capsys, "-c", str(config_path), *argv)
    assert code == 2 and out == "" and message in err


def test_timezone_warning_when_system_zone_unknown(tmp_path, fake_fetch, monkeypatch, capsys):
    path = tmp_path / "config.toml"
    path.write_text('[calendars.work]\nurl = "https://x/"\ncalendar = "Work"\n')
    monkeypatch.setattr(cli, "local_timezone", lambda: (timezone.utc, True))
    code, out, err = run(capsys, "-c", str(path), "free", "-C", "work", "2026-10-13", "2026-10-13")
    assert code == 0 and "Di, 13.10.2026" in out
    assert "warning: system time zone unknown, using UTC; set [defaults].timezone" in err
    assert fake_fetch[0][3] is timezone.utc

    monkeypatch.setattr(cli, "local_timezone", lambda: (TZ, False))
    code, out, err = run(capsys, "-c", str(path), "free", "-C", "work", "2026-10-13", "2026-10-13")
    assert code == 0 and err == ""


def test_caldav_error_reported(config_path, monkeypatch, capsys):
    def fetch(*a, **k):
        raise CalDAVError("boom")

    monkeypatch.setattr(cli, "fetch_busy", fetch)
    code, _, err = run(capsys, "-c", str(config_path), "free", "2026-10-05", "2026-10-06")
    assert code == 2 and "error: boom" in err


def test_missing_config(tmp_path, capsys):
    code, _, err = run(capsys, "-c", str(tmp_path / "none.toml"), "free", "2026-10-05", "2026-10-06")
    assert code == 2 and "config file not found" in err


def test_calendars_command(config_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_calendars", lambda cfg: [("Work", "https://x/cal/work/"), ("Birthdays", "https://x/cal/bd/")])
    code, out, _ = run(capsys, "-c", str(config_path), "calendars")
    assert code == 0
    assert out.splitlines() == ["Work       https://x/cal/work/", "Birthdays  https://x/cal/bd/"]


def test_parse_days():
    assert cli.parse_days("weekday") == frozenset({5, 6})
    assert cli.parse_days("all") == frozenset()
    assert cli.parse_days("Mon, Tue") == frozenset({2, 3, 4, 5, 6})
    with pytest.raises(cli.UsageError):
        cli.parse_days(",")
