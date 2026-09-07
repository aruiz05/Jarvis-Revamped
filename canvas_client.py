"""Canvas iCalendar feed integration."""

from typing import Any

import requests
from icalendar import Calendar

from config import CANVAS_ICAL_URL


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
            }
        )

    return events


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
