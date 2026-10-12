"""Pure free/busy computation: no I/O, no calendar protocol knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Iterable

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class DayResult:
    day: date
    free: list[Interval]


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Sort and merge overlapping or touching intervals; drop empty ones."""
    merged: list[Interval] = []
    for start, end in sorted(i for i in intervals if i[0] < i[1]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def subtract(window: Interval, busy: list[Interval]) -> list[Interval]:
    """Return the parts of `window` not covered by the (merged, sorted) `busy` intervals."""
    free: list[Interval] = []
    cursor, end = window
    for b_start, b_end in busy:
        if b_end <= cursor:
            continue
        if b_start >= end:
            break
        if b_start > cursor:
            free.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < end:
        free.append((cursor, end))
    return free


def days_in_range(first: date, last: date) -> Iterable[date]:
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def compute_free(
    first: date,
    last: date,
    work_start: time,
    work_end: time,
    tz: tzinfo,
    busy: Iterable[Interval],
    off_days: frozenset[int] = frozenset(),
    min_minutes: int = 0,
) -> list[DayResult]:
    """Free slots per working day between `first` and `last` (inclusive).

    `busy` intervals must be timezone-aware. Days whose weekday number is in `off_days`
    are skipped entirely. Gaps shorter than `min_minutes` are dropped.
    """
    merged = merge_intervals(busy)
    min_len = timedelta(minutes=min_minutes)
    results: list[DayResult] = []
    for day in days_in_range(first, last):
        if day.weekday() in off_days:
            continue
        window = (datetime.combine(day, work_start, tz), datetime.combine(day, work_end, tz))
        free = [slot for slot in subtract(window, merged) if slot[1] - slot[0] >= min_len]
        results.append(DayResult(day, free))
    return results
