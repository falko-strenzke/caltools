from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from caltools.freebusy import DayResult, compute_free, merge_intervals, subtract

TZ = ZoneInfo("Europe/Berlin")


def dt(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


def test_merge_sorts_and_merges_overlapping_and_touching():
    out = merge_intervals([
        (dt(13, "14:00"), dt(13, "15:00")),
        (dt(13, "10:00"), dt(13, "11:00")),
        (dt(13, "10:30"), dt(13, "12:00")),
        (dt(13, "12:00"), dt(13, "12:30")),
        (dt(13, "16:00"), dt(13, "16:00")),  # empty, dropped
    ])
    assert out == [(dt(13, "10:00"), dt(13, "12:30")), (dt(13, "14:00"), dt(13, "15:00"))]


def test_subtract_basic():
    window = (dt(13, "09:00"), dt(13, "17:00"))
    busy = [(dt(13, "08:00"), dt(13, "09:00")), (dt(13, "11:30"), dt(13, "14:00")), (dt(13, "17:00"), dt(13, "18:00"))]
    assert subtract(window, busy) == [(dt(13, "09:00"), dt(13, "11:30")), (dt(13, "14:00"), dt(13, "17:00"))]


def test_subtract_busy_covering_window_edges():
    window = (dt(13, "09:00"), dt(13, "17:00"))
    busy = [(dt(13, "08:00"), dt(13, "10:00")), (dt(13, "16:00"), dt(13, "19:00"))]
    assert subtract(window, busy) == [(dt(13, "10:00"), dt(13, "16:00"))]


def test_subtract_fully_busy():
    window = (dt(13, "09:00"), dt(13, "17:00"))
    assert subtract(window, [(dt(12, "00:00"), dt(14, "00:00"))]) == []


def test_compute_free_skips_off_days_and_applies_min_length():
    # 2026-10-12 is a Monday; 17/18 are Sat/Sun.
    busy = [
        (dt(12, "09:00"), dt(12, "09:20")),   # leaves 20 min? no: busy, then free from 9:20
        (dt(12, "09:40"), dt(12, "17:00")),   # gap 09:20-09:40 is 20 min -> dropped
        (dt(13, "10:00"), dt(13, "11:00")),
    ]
    results = compute_free(date(2026, 10, 12), date(2026, 10, 18), time(9), time(17), TZ,
                           busy, off_days=frozenset({5, 6}), min_minutes=30)
    assert [r.day for r in results] == [date(2026, 10, d) for d in range(12, 17)]
    assert results[0] == DayResult(date(2026, 10, 12), [])
    assert results[1].free == [(dt(13, "09:00"), dt(13, "10:00")), (dt(13, "11:00"), dt(13, "17:00"))]
    assert results[2].free == [(dt(14, "09:00"), dt(14, "17:00"))]


def test_compute_free_multi_day_event_and_weekend_included():
    busy = [(dt(16, "15:00"), dt(19, "10:00"))]  # Fri afternoon to Mon morning
    results = compute_free(date(2026, 10, 16), date(2026, 10, 19), time(9), time(17), TZ,
                           busy, off_days=frozenset(), min_minutes=0)
    assert [r.free for r in results] == [
        [(dt(16, "09:00"), dt(16, "15:00"))],
        [],
        [],
        [(dt(19, "10:00"), dt(19, "17:00"))],
    ]


def test_compute_free_busy_in_other_timezone():
    busy = [(datetime(2026, 10, 13, 8, 0, tzinfo=ZoneInfo("UTC")), datetime(2026, 10, 13, 9, 0, tzinfo=ZoneInfo("UTC")))]
    results = compute_free(date(2026, 10, 13), date(2026, 10, 13), time(9), time(17), TZ, busy)
    # 08:00-09:00 UTC is 10:00-11:00 CEST
    assert results[0].free == [(dt(13, "09:00"), dt(13, "10:00")), (dt(13, "11:00"), dt(13, "17:00"))]
