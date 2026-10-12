from datetime import time

import pytest

from caltools.config import ConfigError, load_config, parse_config

MINIMAL = {"calendars": {"work": {"url": "https://x/", "calendar": "Work"}}}


def test_defaults():
    cfg = parse_config(MINIMAL)
    d = cfg.defaults
    assert (d.language, d.work_start, d.work_end) == ("de", time(9), time(17))
    assert d.off_days == frozenset({5, 6})
    assert d.min_free_minutes == 30 and d.all_day_events_block is True
    assert d.calendar is None and d.timezone is None
    cal = cfg.calendars["work"]
    assert cal.username is None and cal.resolve_password() is None


def test_full_defaults_section():
    cfg = parse_config({
        "defaults": {
            "language": "en", "work_start": "8:30", "work_end": "16:00",
            "off_days": ["Fri", "sat", "sunday"], "min_free_minutes": 15,
            "all_day_events_block": False, "calendar": "work", "timezone": "Europe/Berlin",
        },
        **MINIMAL,
    })
    d = cfg.defaults
    assert (d.language, d.work_start, d.work_end) == ("en", time(8, 30), time(16))
    assert d.off_days == frozenset({4, 5, 6})
    assert d.min_free_minutes == 15 and d.all_day_events_block is False
    assert d.timezone == "Europe/Berlin"
    assert cfg.get_calendar(None).name == "work"


@pytest.mark.parametrize("defaults", [
    {"language": "fr"},
    {"work_start": "9"},
    {"work_start": "17:00", "work_end": "09:00"},
    {"off_days": ["xyz"]},
    {"off_days": "sat"},
    {"min_free_minutes": -1},
    {"min_free_minutes": True},
    {"all_day_events_block": "yes"},
    {"calendar": "missing"},
    {"timezone": "Mars/Olympus"},
    {"bogus": 1},
])
def test_invalid_defaults(defaults):
    with pytest.raises(ConfigError):
        parse_config({"defaults": defaults, **MINIMAL})


@pytest.mark.parametrize("cal", [
    {"calendar": "Work"},                                  # url missing
    {"url": "https://x/", "calendar": "A", "calendar_url": "https://x/a/"},
    {"url": "https://x/", "calendar": "A", "password": "p", "password_env": "E"},
    {"url": "https://x/", "calendar": "A", "typo": 1},
])
def test_invalid_calendar(cal):
    with pytest.raises(ConfigError):
        parse_config({"calendars": {"work": cal}})


def test_effective_calendar_url():
    cfg = parse_config({"calendars": {
        "a": {"url": "https://x/", "calendar": "A"},
        "b": {"url": "https://x/", "calendar_url": "https://x/b/"},
        "c": {"url": "https://x/c/"},
    }})
    assert cfg.calendars["a"].effective_calendar_url is None
    assert cfg.calendars["b"].effective_calendar_url == "https://x/b/"
    assert cfg.calendars["c"].effective_calendar_url == "https://x/c/"


def test_no_calendars():
    with pytest.raises(ConfigError):
        parse_config({})


def test_get_calendar_errors():
    cfg = parse_config(MINIMAL)
    with pytest.raises(ConfigError, match="no calendar given"):
        cfg.get_calendar(None)
    with pytest.raises(ConfigError, match="unknown calendar 'x'"):
        cfg.get_calendar("x")


def test_password_sources(monkeypatch):
    cfg = parse_config({"calendars": {
        "a": {"url": "u", "calendar": "c", "password": "lit"},
        "b": {"url": "u", "calendar": "c", "password_env": "CALTOOLS_TEST_PW"},
        "c": {"url": "u", "calendar": "c", "password_cmd": "printf 'from cmd\\n'"},
        "d": {"url": "u", "calendar": "c", "password_cmd": "false"},
    }})
    assert cfg.calendars["a"].resolve_password() == "lit"
    monkeypatch.delenv("CALTOOLS_TEST_PW", raising=False)
    with pytest.raises(ConfigError, match="CALTOOLS_TEST_PW"):
        cfg.calendars["b"].resolve_password()
    monkeypatch.setenv("CALTOOLS_TEST_PW", "from env")
    assert cfg.calendars["b"].resolve_password() == "from env"
    assert cfg.calendars["c"].resolve_password() == "from cmd"
    with pytest.raises(ConfigError, match="password_cmd failed"):
        cfg.calendars["d"].resolve_password()


def test_load_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[defaults]\nlanguage = "en"\n[calendars.w]\nurl = "https://x/"\ncalendar = "W"\n')
    assert load_config(path).defaults.language == "en"
    path.write_text("[defaults\n")
    with pytest.raises(ConfigError):
        load_config(path)
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")
