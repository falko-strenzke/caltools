from datetime import datetime
from zoneinfo import ZoneInfo

import icalendar

from caltools.caldav_client import Busy, events_to_busy

TZ = ZoneInfo("Europe/Berlin")

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:1
SUMMARY:UTC meeting
DTSTART:20261013T080000Z
DTEND:20261013T090000Z
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Holiday
DTSTART;VALUE=DATE:20261014
DTEND;VALUE=DATE:20261016
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Shown as free
TRANSP:TRANSPARENT
DTSTART;TZID=Europe/Berlin:20261013T130000
DTEND;TZID=Europe/Berlin:20261013T140000
END:VEVENT
BEGIN:VEVENT
UID:4
SUMMARY:Cancelled
STATUS:CANCELLED
DTSTART;TZID=Europe/Berlin:20261013T150000
DTEND;TZID=Europe/Berlin:20261013T160000
END:VEVENT
BEGIN:VEVENT
UID:5
SUMMARY:With duration
DTSTART;TZID=Europe/Berlin:20261013T160000
DURATION:PT45M
END:VEVENT
BEGIN:VEVENT
UID:6
SUMMARY:Floating, no end
DTSTART:20261013T120000
END:VEVENT
BEGIN:VEVENT
UID:7
SUMMARY:Single all-day without end
DTSTART;VALUE=DATE:20261019
END:VEVENT
END:VCALENDAR
"""


def vevents():
    return icalendar.Calendar.from_ical(ICS).walk("VEVENT")


def b(y, mo, d, h, m):
    return datetime(y, mo, d, h, m, tzinfo=TZ)


def test_events_to_busy_all_day_blocks():
    out = events_to_busy(vevents(), TZ, all_day_blocks=True)
    assert out == [
        Busy(b(2026, 10, 13, 10, 0), b(2026, 10, 13, 11, 0), "UTC meeting"),
        Busy(b(2026, 10, 13, 16, 0), b(2026, 10, 13, 16, 45), "With duration"),
        Busy(b(2026, 10, 14, 0, 0), b(2026, 10, 16, 0, 0), "Holiday"),
        Busy(b(2026, 10, 19, 0, 0), b(2026, 10, 20, 0, 0), "Single all-day without end"),
    ]


def test_events_to_busy_all_day_ignored():
    out = events_to_busy(vevents(), TZ, all_day_blocks=False)
    assert [x.summary for x in out] == ["UTC meeting", "With duration"]


def test_expanded_recurrence_instances_are_separate_busy_entries():
    ics = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:r
RECURRENCE-ID;TZID=Europe/Berlin:20261013T090000
SUMMARY:Standup
DTSTART;TZID=Europe/Berlin:20261013T090000
DTEND;TZID=Europe/Berlin:20261013T091500
END:VEVENT
BEGIN:VEVENT
UID:r
RECURRENCE-ID;TZID=Europe/Berlin:20261014T090000
SUMMARY:Standup
DTSTART;TZID=Europe/Berlin:20261014T090000
DTEND;TZID=Europe/Berlin:20261014T091500
END:VEVENT
END:VCALENDAR
"""
    out = events_to_busy(icalendar.Calendar.from_ical(ics).walk("VEVENT"), TZ)
    assert [(x.start, x.end) for x in out] == [
        (b(2026, 10, 13, 9, 0), b(2026, 10, 13, 9, 15)),
        (b(2026, 10, 14, 9, 0), b(2026, 10, 14, 9, 15)),
    ]
