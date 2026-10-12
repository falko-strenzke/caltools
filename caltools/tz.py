"""Determine the local time zone as a DST-aware tzinfo."""

from __future__ import annotations

import os
from datetime import datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _zone_from_name(name: str | None) -> tzinfo | None:
    if not name:
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None


def local_timezone() -> tuple[tzinfo, bool]:
    """Return the system time zone and whether it is only a guess.

    The zone is DST-aware when its IANA name can be determined from TZ, /etc/localtime or
    /etc/timezone. Otherwise the fixed offset of the current moment is returned together
    with True, so callers can warn the user.
    """
    zone = _zone_from_name(os.environ.get("TZ"))
    if zone is not None:
        return zone, False
    try:
        target = Path("/etc/localtime").resolve()
        parts = target.parts
        if "zoneinfo" in parts:
            zone = _zone_from_name("/".join(parts[parts.index("zoneinfo") + 1:]))
            if zone is not None:
                return zone, False
    except OSError:
        pass
    try:
        zone = _zone_from_name(Path("/etc/timezone").read_text())
        if zone is not None:
            return zone, False
    except OSError:
        pass
    # Fallback: fixed offset of the current moment (not DST-aware).
    return datetime.now().astimezone().tzinfo, True  # type: ignore[return-value]
