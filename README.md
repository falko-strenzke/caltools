# caltools

Command line tools for working with a CalDAV calendar. The first command, `free`, lists the
free time slots within your working hours for a date range as plain text in German or English,
ready to paste into an email when arranging appointments.

Requires Python 3.11+ and the packages `caldav` and `icalendar` (installed automatically).

## Installation

```sh
cd calender-tools
python3 -m venv .venv
.venv/bin/pip install .
# optionally make it available on your PATH:
ln -s "$PWD/.venv/bin/caltools" ~/.local/bin/caltools
```

Or run without installing: `.venv/bin/python -m caltools ...` from this directory.

## Configuration

Copy `config.example.toml` to `~/.config/caltools/config.toml` and edit it. The example file
documents every key. In short:

| Section | Key | Meaning |
|---|---|---|
| `[defaults]` | `language` | `de` (default) or `en`. |
| | `work_start`, `work_end` | Working day, default `09:00` to `17:00`. |
| | `off_days` | Weekdays never offered, default `["sat", "sun"]`. Add e.g. `"fri"` for a four-day week. |
| | `min_free_minutes` | Shortest gap worth listing, default 30. |
| | `all_day_events_block` | Whether an all-day event blocks its whole day, default `true`. |
| | `calendar` | Entry used when `--calendar` is omitted. |
| | `timezone` | IANA zone, e.g. `Europe/Berlin`. Default: system time zone. Set it on machines without a configured zone, the tool warns and uses UTC there. |
| `[calendars.<name>]` | `url` | CalDAV server URL. |
| | `username` | Login name. |
| | `password`, `password_env`, `password_cmd` | Exactly one password source: literal, environment variable, or a command printing the password. |
| | `calendar` or `calendar_url` | Display name of the calendar on the server, or its full URL. If both are omitted, `url` itself must be the calendar's URL. |

To find the display names of your calendars:

```sh
caltools calendars --calendar work
```

## Usage

```
caltools [-c CONFIG] free [-C NAME] [-l de|en] [--start HH:MM] [--end HH:MM]
         [--days weekday|all|mon,tue,...] [--min MINUTES] [-v] FROM TO
```

`FROM` and `TO` accept `YYYY-MM-DD` or `DD.MM.YYYY`; `TO` is inclusive. Events marked as
cancelled or shown as free (`TRANSP:TRANSPARENT`) do not count as busy. Recurring events are
expanded.

`--days weekday` uses Monday to Friday regardless of `off_days` in the config, `--days all`
includes weekends, and a list such as `--days mon,wed,fri` restricts the output to those days.
`-v` prints the busy intervals fetched from the server before the overview, which helps to
check the result against your calendar client.

Example:

```
$ caltools free -C work 2026-10-12 2026-10-15
Freie Zeiten vom 12.10.2026 bis 15.10.2026 (Arbeitszeit 09:00–17:00):

Mo, 12.10.2026: 09:00–11:30, 14:00–17:00
Di, 13.10.2026: ganztägig frei
Mi, 14.10.2026: keine freien Zeiten
Do, 15.10.2026: 09:00–10:00
```

The same with `--lang en`:

```
Available times from 12 Oct 2026 to 15 Oct 2026 (working hours 09:00–17:00):

Mon, 12 Oct 2026: 09:00–11:30, 14:00–17:00
Tue, 13 Oct 2026: free all day
Wed, 14 Oct 2026: no free times
Thu, 15 Oct 2026: 09:00–10:00
```

Exit codes: 0 ok, 2 error (configuration, connection, calendar not found).

## Development

```sh
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```
