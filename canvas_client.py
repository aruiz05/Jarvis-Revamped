"""Canvas iCalendar feed integration."""

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from config import CANVAS_ICAL_URL, TIMEZONE


# uid prefixes that canvas uses for assignments
ASSIGNMENT_UID_PREFIXES = ("event-assignment-", "event-assignment-override-")


def fetch_calendar_feed() -> str:
    """Download the private Canvas iCalendar feed."""
    # check that the private feed url exists
    if not CANVAS_ICAL_URL.strip():
        raise RuntimeError(
            "Canvas calendar configuration is incomplete.\n"
            "Please set CANVAS_ICAL_URL in .env."
        )

    # request the canvas calendar feed
    try:
        response = requests.get(CANVAS_ICAL_URL, timeout=15)
    except requests.Timeout as exc:
        raise RuntimeError("Canvas calendar request timed out.") from exc
    except requests.ConnectionError as exc:
        raise RuntimeError("Unable to connect to the Canvas calendar feed.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Canvas calendar request failed.") from exc

    # handle common access errors without showing the url
    if response.status_code in (401, 403):
        raise RuntimeError(
            "Canvas calendar access was denied. Check that CANVAS_ICAL_URL is still valid."
        )

    if response.status_code == 404:
        raise RuntimeError(
            "Canvas calendar feed was not found. Check that the calendar feed URL is still valid."
        )

    if not response.ok:
        raise RuntimeError(
            f"Canvas calendar request failed with HTTP status {response.status_code}."
        )

    return response.text


def parse_calendar_feed(ics_data: str) -> list[dict[str, Any]]:
    """Parse Canvas iCalendar data into simple event dictionaries."""
    # parse the raw ics text
    try:
        calendar = Calendar.from_ical(ics_data)
    except ValueError as exc:
        raise RuntimeError("Unable to parse the Canvas calendar feed.") from exc

    events = []

    # collect only calendar event entries
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        events.append(
            {
                "summary": _get_text(component, "SUMMARY"),
                "start": _get_decoded(component, "DTSTART"),
                "end": _get_decoded(component, "DTEND"),
                "uid": _get_text(component, "UID"),
                "description": _get_text(component, "DESCRIPTION"),
                "url": _get_text(component, "URL"),
                "properties": sorted(str(key) for key in component.keys()),
            }
        )

    return events


def is_assignment_event(event: dict[str, Any]) -> bool:
    """Return whether a Canvas calendar event looks like an assignment."""
    # use canvas uid structure instead of title words
    uid = event.get("uid") or ""
    return uid.startswith(ASSIGNMENT_UID_PREFIXES)


def get_assignments(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize assignment events for later project phases."""
    # build clean assignment dictionaries
    assignments = []

    for event in events:
        if not is_assignment_event(event):
            continue

        assignments.append(
            {
                "title": event.get("summary") or "Untitled Canvas assignment",
                "due_at": normalize_due_datetime(event.get("start")),
                "uid": event.get("uid"),
                "url": event.get("url"),
                "description": event.get("description"),
                "source_due_field": "DTSTART",
            }
        )

    return assignments


def normalize_due_datetime(value: Any) -> datetime | date | None:
    """Normalize Canvas due values to the project timezone when possible."""
    if value is None:
        return None

    project_timezone = ZoneInfo(TIMEZONE)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            # canvas has not shown naive datetimes in this feed
            return value.replace(tzinfo=project_timezone)
        # convert aware datetimes into the project timezone
        return value.astimezone(project_timezone)

    if isinstance(value, date):
        # keep date only values as dates
        return value

    return None


def get_today() -> date:
    """Return today's date in the project timezone."""
    # today means the current phoenix calendar date
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def get_assignments_due_today(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return assignments due on today's project timezone date."""
    # compare dates instead of formatted strings
    today = get_today()

    due_today = [
        assignment
        for assignment in assignments
        if _due_date(assignment.get("due_at")) == today
    ]

    return sorted(due_today, key=_assignment_sort_key)


def get_syncable_assignments(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return current and future assignments with usable due dates."""
    # keep only assignments ready for calendar sync
    return sorted(
        [
            assignment
            for assignment in assignments
            if _is_syncable_assignment(assignment)
        ],
        key=_assignment_sort_key,
    )


def get_assignment_skip_counts(assignments: list[dict[str, Any]]) -> dict[str, int]:
    """Return simple skip counts for bulk sync reporting."""
    # count skipped assignments without changing the list
    missing_due_dates = 0
    past_assignments = 0

    for assignment in assignments:
        due_at = assignment.get("due_at")

        if due_at is None:
            missing_due_dates += 1
            continue

        if not _is_syncable_assignment(assignment):
            past_assignments += 1

    return {
        "missing_due_dates": missing_due_dates,
        "past_assignments": past_assignments,
    }


def get_event_inspection(events: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Return a small sanitized sample of event structure."""
    # omit event urls from inspection output
    return [
        {
            "summary": event.get("summary"),
            "uid": event.get("uid"),
            "is_assignment": is_assignment_event(event),
            "start": event.get("start"),
            "end": event.get("end"),
            "properties": event.get("properties"),
        }
        for event in events[:limit]
    ]


def _get_text(component: Any, field_name: str) -> str | None:
    # return optional text values safely
    value = component.get(field_name)
    if value is None:
        return None
    return str(value)


def _get_decoded(component: Any, field_name: str) -> Any:
    # return decoded date values safely
    if field_name not in component:
        return None
    return component.decoded(field_name)


def _due_date(value: Any) -> date | None:
    # extract a comparable date value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _assignment_sort_key(assignment: dict[str, Any]) -> tuple[date, int, time, str]:
    # sort by due date and time
    due_at = assignment.get("due_at")

    if isinstance(due_at, datetime):
        project_due = due_at.astimezone(ZoneInfo(TIMEZONE))
        return (project_due.date(), 0, project_due.time(), assignment.get("title") or "")

    if isinstance(due_at, date):
        return (due_at, 1, time.max, assignment.get("title") or "")

    return (date.max, 2, time.max, assignment.get("title") or "")


def _is_syncable_assignment(assignment: dict[str, Any]) -> bool:
    # include only current or future assignments
    due_at = assignment.get("due_at")
    now = datetime.now(ZoneInfo(TIMEZONE))
    today = now.date()

    if isinstance(due_at, datetime):
        return due_at.astimezone(ZoneInfo(TIMEZONE)) >= now

    if isinstance(due_at, date):
        return due_at >= today

    return False
