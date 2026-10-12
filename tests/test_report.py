from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from caltools.freebusy import DayResult
from caltools.report import render

TZ = ZoneInfo("Europe/Berlin")


def dt(day, h, m=0):
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


RESULTS = [
    DayResult(date(2026, 10, 12), [(dt(12, 9), dt(12, 11, 30)), (dt(12, 14), dt(12, 17))]),
    DayResult(date(2026, 10, 13), [(dt(13, 9), dt(13, 17))]),
    DayResult(date(2026, 10, 14), []),
    DayResult(date(2026, 10, 15), [(dt(15, 9), dt(15, 10))]),
]


def test_render_de():
    out = render(RESULTS, "de", date(2026, 10, 12), date(2026, 10, 15), time(9), time(17))
    assert out == (
        "Freie Zeiten vom 12.10.2026 bis 15.10.2026 (Arbeitszeit 09:00–17:00):\n"
        "\n"
        "Mo, 12.10.2026: 09:00–11:30, 14:00–17:00\n"
        "Di, 13.10.2026: ganztägig frei\n"
        "Mi, 14.10.2026: keine freien Zeiten\n"
        "Do, 15.10.2026: 09:00–10:00\n"
    )


def test_render_en():
    out = render(RESULTS, "en", date(2026, 10, 12), date(2026, 10, 15), time(9), time(17))
    assert out == (
        "Available times from 12 Oct 2026 to 15 Oct 2026 (working hours 09:00–17:00):\n"
        "\n"
        "Mon, 12 Oct 2026: 09:00–11:30, 14:00–17:00\n"
        "Tue, 13 Oct 2026: free all day\n"
        "Wed, 14 Oct 2026: no free times\n"
        "Thu, 15 Oct 2026: 09:00–10:00\n"
    )


def test_render_no_working_days():
    out = render([], "de", date(2026, 10, 17), date(2026, 10, 18), time(9), time(17))
    assert out.endswith("\n\nKeine Arbeitstage im Zeitraum.\n")
    out = render([], "en", date(2026, 10, 17), date(2026, 10, 18), time(9), time(17))
    assert out.endswith("No working days in this period.\n")


def test_render_unknown_language():
    with pytest.raises(ValueError):
        render([], "fr", date(2026, 10, 17), date(2026, 10, 18), time(9), time(17))
