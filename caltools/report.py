"""Render free-time overviews as plain text in German or English."""

from __future__ import annotations

from datetime import date, datetime, time

from .freebusy import DayResult

_WEEKDAYS = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_TEXT = {
    "de": {
        "header": "Freie Zeiten vom {first} bis {last} (Arbeitszeit {start}–{end}):",
        "all_day": "ganztägig frei",
        "none": "keine freien Zeiten",
        "no_days": "Keine Arbeitstage im Zeitraum.",
    },
    "en": {
        "header": "Available times from {first} to {last} (working hours {start}–{end}):",
        "all_day": "free all day",
        "none": "no free times",
        "no_days": "No working days in this period.",
    },
}


def format_date(day: date, lang: str) -> str:
    if lang == "de":
        return f"{day.day:02d}.{day.month:02d}.{day.year}"
    return f"{day.day} {_MONTHS_EN[day.month - 1]} {day.year}"


def format_time(value: time | datetime) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def format_day_line(result: DayResult, lang: str, work_start: time, work_end: time) -> str:
    text = _TEXT[lang]
    label = f"{_WEEKDAYS[lang][result.day.weekday()]}, {format_date(result.day, lang)}"
    if not result.free:
        body = text["none"]
    elif (
        len(result.free) == 1
        and result.free[0][0].time() == work_start
        and result.free[0][1].time() == work_end
    ):
        body = text["all_day"]
    else:
        body = ", ".join(f"{format_time(s)}–{format_time(e)}" for s, e in result.free)
    return f"{label}: {body}"


def render(
    results: list[DayResult],
    lang: str,
    first: date,
    last: date,
    work_start: time,
    work_end: time,
) -> str:
    if lang not in _TEXT:
        raise ValueError(f"unsupported language '{lang}'")
    text = _TEXT[lang]
    lines = [
        text["header"].format(
            first=format_date(first, lang),
            last=format_date(last, lang),
            start=format_time(work_start),
            end=format_time(work_end),
        ),
        "",
    ]
    if not results:
        lines.append(text["no_days"])
    for result in results:
        lines.append(format_day_line(result, lang, work_start, work_end))
    return "\n".join(lines) + "\n"
