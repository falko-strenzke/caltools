"""Command line interface: free, calendars."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from . import __version__
from .caldav_client import CalDAVError, fetch_busy, list_calendars
from .config import (
    DEFAULT_CONFIG_PATH,
    LANGUAGES,
    WEEKDAYS,
    Config,
    ConfigError,
    load_config,
    parse_time,
    parse_weekday,
)
from .freebusy import compute_free
from .report import format_date, format_time, render
from .tz import local_timezone

EXIT_OK = 0
EXIT_ERROR = 2


class UsageError(Exception):
    pass


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise UsageError(f"invalid date '{value}', expected YYYY-MM-DD or DD.MM.YYYY")


def parse_days(value: str) -> frozenset[int]:
    """Translate --days into the set of weekday numbers that are OFF."""
    key = value.strip().lower()
    if key == "weekday":
        return frozenset({5, 6})
    if key == "all":
        return frozenset()
    try:
        working = {parse_weekday(part) for part in key.split(",") if part.strip()}
    except ConfigError as exc:
        raise UsageError(f"--days: {exc}") from None
    if not working:
        raise UsageError("--days: expected 'weekday', 'all' or a list such as mon,tue,wed")
    return frozenset(range(7)) - frozenset(working)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caltools",
        description="Tools for working with a CalDAV calendar.",
        epilog="Exit codes: 0 ok, 2 error.",
    )
    parser.add_argument(
        "-c", "--config", type=Path, default=DEFAULT_CONFIG_PATH,
        help=f"config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    free = sub.add_parser(
        "free",
        help="list free time slots within working hours for a date range",
        description="List free time slots within working hours for a date range, "
        "as text suitable for proposing appointments by email.",
    )
    free.add_argument("-C", "--calendar", help="calendar name from the config (default: [defaults].calendar)")
    free.add_argument("-l", "--lang", choices=LANGUAGES, help="output language (default from config, else de)")
    free.add_argument("--start", metavar="HH:MM", help="start of the working day (default from config, else 09:00)")
    free.add_argument("--end", metavar="HH:MM", help="end of the working day (default from config, else 17:00)")
    free.add_argument(
        "--days", metavar="SPEC",
        help="'weekday' for Mon-Fri regardless of the config, 'all' for every day, or a "
        f"comma-separated list of weekdays ({','.join(WEEKDAYS)})",
    )
    free.add_argument("--min", metavar="MINUTES", type=int, help="minimum length of a free slot (default from config, else 30)")
    free.add_argument("-v", "--verbose", action="store_true", help="also print the busy intervals fetched from the server")
    free.add_argument("first", metavar="FROM", help="first day, YYYY-MM-DD or DD.MM.YYYY")
    free.add_argument("last", metavar="TO", help="last day (inclusive), same formats")

    cals = sub.add_parser("calendars", help="list the calendars visible on the server of a configured account")
    cals.add_argument("-C", "--calendar", help="config entry whose account to use (default: [defaults].calendar)")
    return parser


def cmd_free(cfg: Config, args: argparse.Namespace) -> int:
    d = cfg.defaults
    cal_cfg = cfg.get_calendar(args.calendar)
    first, last = parse_date(args.first), parse_date(args.last)
    if last < first:
        raise UsageError("TO must not be before FROM")
    lang = args.lang or d.language
    work_start = parse_time(args.start, "--start") if args.start else d.work_start
    work_end = parse_time(args.end, "--end") if args.end else d.work_end
    if work_start >= work_end:
        raise UsageError("working day start must be before its end")
    off_days = parse_days(args.days) if args.days else d.off_days
    min_minutes = args.min if args.min is not None else d.min_free_minutes
    if min_minutes < 0:
        raise UsageError("--min must not be negative")
    if d.timezone:
        tz = ZoneInfo(d.timezone)
    else:
        tz, guessed = local_timezone()
        if guessed:
            print(
                f"warning: system time zone unknown, using {tz.tzname(None)}; "
                "set [defaults].timezone in the config",
                file=sys.stderr,
            )

    busy = fetch_busy(cal_cfg, first, last, tz, d.all_day_events_block)
    if args.verbose:
        print(f"# {len(busy)} busy interval(s) from calendar '{cal_cfg.name}':")
        for b in busy:
            print(
                f"#   {format_date(b.start.date(), lang)} {format_time(b.start)} - "
                f"{format_date(b.end.date(), lang)} {format_time(b.end)}  {b.summary}"
            )
        print()
    results = compute_free(
        first, last, work_start, work_end, tz,
        [(b.start, b.end) for b in busy], off_days, min_minutes,
    )
    sys.stdout.write(render(results, lang, first, last, work_start, work_end))
    return EXIT_OK


def cmd_calendars(cfg: Config, args: argparse.Namespace) -> int:
    cal_cfg = cfg.get_calendar(args.calendar)
    entries = list_calendars(cal_cfg)
    if not entries:
        print(f"no calendars found for account '{cal_cfg.name}' on {cal_cfg.url}")
        return EXIT_OK
    width = max(len(name) for name, _ in entries)
    for name, url in entries:
        print(f"{name:<{width}}  {url}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.command == "free":
            return cmd_free(cfg, args)
        if args.command == "calendars":
            return cmd_calendars(cfg, args)
        parser.error(f"unknown command {args.command}")
    except (ConfigError, UsageError, CalDAVError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
