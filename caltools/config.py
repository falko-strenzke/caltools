"""Configuration file handling (TOML)."""

from __future__ import annotations

import os
import shlex
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_CONFIG_PATH = Path("~/.config/caltools/config.toml").expanduser()

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
LANGUAGES = ("de", "en")


class ConfigError(Exception):
    pass


@dataclass
class Defaults:
    language: str = "de"
    work_start: time = time(9, 0)
    work_end: time = time(17, 0)
    off_days: frozenset[int] = frozenset({5, 6})  # Python weekday numbers, Mon = 0
    min_free_minutes: int = 30
    all_day_events_block: bool = True
    calendar: str | None = None
    timezone: str | None = None


@dataclass
class CalendarConfig:
    name: str
    url: str
    username: str | None
    password: str | None
    password_env: str | None
    password_cmd: str | None
    calendar: str | None
    calendar_url: str | None

    @property
    def effective_calendar_url(self) -> str | None:
        """Calendar URL to open directly: `calendar_url`, or `url` when no name is given."""
        if self.calendar_url:
            return self.calendar_url
        if self.calendar is None:
            return self.url
        return None

    def resolve_password(self) -> str | None:
        """Return the password from whichever source is configured."""
        if self.password is not None:
            return self.password
        if self.password_env is not None:
            value = os.environ.get(self.password_env)
            if value is None:
                raise ConfigError(
                    f"calendar '{self.name}': environment variable {self.password_env} is not set"
                )
            return value
        if self.password_cmd is not None:
            try:
                proc = subprocess.run(
                    shlex.split(self.password_cmd), capture_output=True, text=True, check=True
                )
            except (OSError, subprocess.CalledProcessError) as exc:
                raise ConfigError(f"calendar '{self.name}': password_cmd failed: {exc}") from exc
            return proc.stdout.strip()
        return None


@dataclass
class Config:
    defaults: Defaults = field(default_factory=Defaults)
    calendars: dict[str, CalendarConfig] = field(default_factory=dict)

    def get_calendar(self, name: str | None) -> CalendarConfig:
        name = name or self.defaults.calendar
        if not name:
            raise ConfigError(
                "no calendar given and no default calendar configured ([defaults].calendar)"
            )
        try:
            return self.calendars[name]
        except KeyError:
            known = ", ".join(sorted(self.calendars)) or "none"
            raise ConfigError(f"unknown calendar '{name}' (configured: {known})") from None


def parse_time(value: str, what: str = "time") -> time:
    """Parse 'H:MM' or 'HH:MM' into a time object."""
    try:
        hours, minutes = value.strip().split(":")
        result = time(int(hours), int(minutes))
    except (ValueError, AttributeError):
        raise ConfigError(f"invalid {what} '{value}', expected HH:MM") from None
    return result


def parse_weekday(value: str) -> int:
    key = value.strip().lower()[:3]
    if key not in WEEKDAYS:
        raise ConfigError(f"invalid weekday '{value}', expected one of {', '.join(WEEKDAYS)}")
    return WEEKDAYS.index(key)


def parse_weekdays(values: list, what: str) -> frozenset[int]:
    if not isinstance(values, list):
        raise ConfigError(f"{what} must be a list of weekday names")
    return frozenset(parse_weekday(str(v)) for v in values)


def _check_keys(section: dict, allowed: set[str], where: str) -> None:
    unknown = set(section) - allowed
    if unknown:
        raise ConfigError(f"unknown key(s) in {where}: {', '.join(sorted(unknown))}")


def _parse_defaults(section: dict) -> Defaults:
    _check_keys(
        section,
        {
            "language", "work_start", "work_end", "off_days", "min_free_minutes",
            "all_day_events_block", "calendar", "timezone",
        },
        "[defaults]",
    )
    d = Defaults()
    if "language" in section:
        if section["language"] not in LANGUAGES:
            raise ConfigError(f"[defaults].language must be one of {', '.join(LANGUAGES)}")
        d.language = section["language"]
    if "work_start" in section:
        d.work_start = parse_time(str(section["work_start"]), "[defaults].work_start")
    if "work_end" in section:
        d.work_end = parse_time(str(section["work_end"]), "[defaults].work_end")
    if d.work_start >= d.work_end:
        raise ConfigError("[defaults].work_start must be before work_end")
    if "off_days" in section:
        d.off_days = parse_weekdays(section["off_days"], "[defaults].off_days")
    if "min_free_minutes" in section:
        value = section["min_free_minutes"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ConfigError("[defaults].min_free_minutes must be a non-negative integer")
        d.min_free_minutes = value
    if "all_day_events_block" in section:
        if not isinstance(section["all_day_events_block"], bool):
            raise ConfigError("[defaults].all_day_events_block must be true or false")
        d.all_day_events_block = section["all_day_events_block"]
    if "calendar" in section:
        d.calendar = str(section["calendar"])
    if "timezone" in section:
        try:
            ZoneInfo(str(section["timezone"]))
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigError(f"[defaults].timezone: unknown time zone '{section['timezone']}'") from None
        d.timezone = str(section["timezone"])
    return d


def _parse_calendar(name: str, section: dict) -> CalendarConfig:
    where = f"[calendars.{name}]"
    if not isinstance(section, dict):
        raise ConfigError(f"{where} must be a table")
    _check_keys(
        section,
        {"url", "username", "password", "password_env", "password_cmd", "calendar", "calendar_url"},
        where,
    )
    if "url" not in section:
        raise ConfigError(f"{where}: 'url' is required")
    sources = [k for k in ("password", "password_env", "password_cmd") if k in section]
    if len(sources) > 1:
        raise ConfigError(f"{where}: use only one of password, password_env, password_cmd")
    if "calendar" in section and "calendar_url" in section:
        raise ConfigError(f"{where}: give either 'calendar' or 'calendar_url', not both")
    return CalendarConfig(
        name=name,
        url=str(section["url"]),
        username=_opt_str(section, "username"),
        password=_opt_str(section, "password"),
        password_env=_opt_str(section, "password_env"),
        password_cmd=_opt_str(section, "password_cmd"),
        calendar=_opt_str(section, "calendar"),
        calendar_url=_opt_str(section, "calendar_url"),
    )


def _opt_str(section: dict, key: str) -> str | None:
    return str(section[key]) if key in section else None


def parse_config(data: dict) -> Config:
    _check_keys(data, {"defaults", "calendars"}, "top level")
    defaults = _parse_defaults(data.get("defaults", {}))
    calendars_section = data.get("calendars", {})
    if not isinstance(calendars_section, dict):
        raise ConfigError("[calendars] must contain one table per calendar")
    calendars = {name: _parse_calendar(name, sec) for name, sec in calendars_section.items()}
    if not calendars:
        raise ConfigError("no calendars configured ([calendars.<name>] sections)")
    if defaults.calendar is not None and defaults.calendar not in calendars:
        raise ConfigError(f"[defaults].calendar '{defaults.calendar}' is not a configured calendar")
    return Config(defaults=defaults, calendars=calendars)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None
    return parse_config(data)
