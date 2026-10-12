"""CalDAV access and conversion of VEVENTs into busy intervals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Iterable

from .config import CalendarConfig


class CalDAVError(Exception):
    pass


@dataclass(frozen=True)
class Busy:
    start: datetime
    end: datetime
    summary: str


def _event_end(vevent, start):
    dtend = vevent.get("DTEND")
    if dtend is not None:
        return dtend.dt
    duration = vevent.get("DURATION")
    if duration is not None:
        return start + duration.dt
    # RFC 5545 defaults: a date value spans one day, a date-time has no duration.
    if isinstance(start, datetime):
        return start
    return start + timedelta(days=1)


def _to_aware(value: datetime, tz: tzinfo) -> datetime:
    if value.tzinfo is None:  # floating time: interpret in the target zone
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def events_to_busy(vevents: Iterable, tz: tzinfo, all_day_blocks: bool = True) -> list[Busy]:
    """Convert icalendar VEVENT components into busy intervals in time zone `tz`.

    Cancelled events and events shown as free (TRANSP:TRANSPARENT) are ignored.
    All-day events block their whole days when `all_day_blocks` is set, else they are ignored.
    """
    busy: list[Busy] = []
    for vevent in vevents:
        if str(vevent.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if str(vevent.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue
        dtstart = vevent.get("DTSTART")
        if dtstart is None:
            continue
        start = dtstart.dt
        end = _event_end(vevent, start)
        summary = str(vevent.get("SUMMARY", ""))
        if isinstance(start, datetime):
            start_aware = _to_aware(start, tz)
            if isinstance(end, datetime):
                end_aware = _to_aware(end, tz)
            else:  # mixed value types are invalid; be lenient
                end_aware = datetime.combine(end, time.min, tz)
        else:
            if not all_day_blocks:
                continue
            end_date = end if isinstance(end, date) and not isinstance(end, datetime) else end.date()
            start_aware = datetime.combine(start, time.min, tz)
            end_aware = datetime.combine(end_date, time.min, tz)
        if start_aware < end_aware:
            busy.append(Busy(start_aware, end_aware, summary))
    return sorted(busy, key=lambda b: (b.start, b.end))


def _connect(cfg: CalendarConfig):
    import caldav

    try:
        return caldav.DAVClient(url=cfg.url, username=cfg.username, password=cfg.resolve_password())
    except Exception as exc:  # caldav raises a variety of exception types
        raise CalDAVError(f"cannot connect to {cfg.url}: {exc}") from exc


def _open_calendar(client, cfg: CalendarConfig):
    from caldav.lib import error

    direct = cfg.effective_calendar_url
    try:
        if direct:
            return client.calendar(url=direct)
        return client.principal().calendar(name=cfg.calendar)
    except error.NotFoundError:
        what = f"calendar at {direct}" if direct else f"calendar '{cfg.calendar}' on {cfg.url}"
        raise CalDAVError(f"{what} not found; run 'caltools calendars' to list names") from None
    except error.AuthorizationError as exc:
        raise CalDAVError(f"authentication failed for {cfg.url}: {exc}") from exc
    except error.DAVError as exc:
        raise CalDAVError(f"CalDAV error on {cfg.url}: {exc}") from exc


def list_calendars(cfg: CalendarConfig) -> list[tuple[str, str]]:
    """Return (name, url) of every calendar visible for the configured account."""
    from caldav.lib import error

    client = _connect(cfg)
    try:
        calendars = client.principal().calendars()
    except error.AuthorizationError as exc:
        raise CalDAVError(f"authentication failed for {cfg.url}: {exc}") from exc
    except error.DAVError as exc:
        raise CalDAVError(f"CalDAV error on {cfg.url}: {exc}") from exc
    return [(_display_name(cal), str(cal.url)) for cal in calendars]


def _display_name(cal) -> str:
    getter = getattr(cal, "get_display_name", None)
    name = getter() if getter else getattr(cal, "name", None)
    return str(name or "")


def fetch_busy(
    cfg: CalendarConfig, first: date, last: date, tz: tzinfo, all_day_blocks: bool = True
) -> list[Busy]:
    """Fetch all events between `first` and `last` (inclusive) and return busy intervals."""
    from caldav.lib import error

    client = _connect(cfg)
    calendar = _open_calendar(client, cfg)
    start = datetime.combine(first, time.min, tz)
    end = datetime.combine(last + timedelta(days=1), time.min, tz)
    try:
        objects = calendar.search(start=start, end=end, event=True, expand=True)
    except error.DAVError as exc:
        raise CalDAVError(f"search failed on {cfg.url}: {exc}") from exc
    vevents = []
    for obj in objects:
        vevents.extend(obj.icalendar_instance.walk("VEVENT"))
    return events_to_busy(vevents, tz, all_day_blocks)
