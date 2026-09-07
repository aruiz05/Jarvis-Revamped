from datetime import datetime
import sys
from zoneinfo import ZoneInfo

from calendar_client import (
    TEST_EVENT_TITLE,
    create_test_event,
    delete_event,
    get_calendar_service,
    get_upcoming_events,
)
from config import TIMEZONE
from canvas_client import (
    fetch_calendar_feed,
    get_assignments,
    get_assignments_due_today,
    get_event_inspection,
    get_today,
    parse_calendar_feed,
)


def main() -> None:
    # check for optional inspection mode
    inspect_mode = "--inspect" in sys.argv[1:]
    calendar_test_mode = "--calendar-test" in sys.argv[1:]

    if calendar_test_mode:
        run_calendar_test()
        return

    print("Canvas Calendar Reminder")
    print("Loading Canvas calendar...")
    print()

    # fetch and parse the canvas feed
    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
    except RuntimeError as error:
        print(error)
        return

    print("Canvas calendar loaded successfully.")
    print()

    # stop cleanly when the feed has no events
    if not events:
        print("No Canvas calendar items found.")
        return

    if inspect_mode:
        _print_event_inspection(events)
        return

    # separate assignments from other canvas events
    assignments = get_assignments(events)
    due_today = get_assignments_due_today(assignments)

    print(f"Canvas calendar items found: {len(events)}")
    print(f"Assignments identified: {len(assignments)}")
    print()
    print(f"Today: {_format_date(get_today())}")
    print()
    print(f"Assignments due today: {len(due_today)}")

    if not due_today:
        print()
        print("Nothing is due today.")
        return

    print()

    # show a readable summary for each assignment
    for index, assignment in enumerate(due_today, start=1):
        print(f"{index}. {assignment.get('title')}")
        print(f"   Due: {_format_due(assignment.get('due_at'))}")
        print(f"   UID: {_format_value(assignment.get('uid'))}")
        print()


def run_calendar_test() -> None:
    print("Canvas Calendar Reminder")
    print("Google Calendar Phase 4 Test")
    print()
    print("Authenticating with Google...")

    created_event_id = None

    try:
        service = get_calendar_service()
        print("Google Calendar connection successful.")
        print()

        events = get_upcoming_events(service)
        _print_upcoming_events(events)

        print()
        print("Creating temporary test event...")
        created_event = create_test_event(service)
        created_event_id = created_event["id"]
        print("Google Calendar test event created successfully.")
        print(f"Title: {created_event.get('summary')}")
        print(f"Start: {_format_google_start(created_event)}")

        print()
        print("Deleting temporary test event...")
        delete_event(service, created_event_id)
        created_event_id = None
        print("Google Calendar test event deleted successfully.")
        print()
        print("Phase 4 Google Calendar test passed.")
    except RuntimeError as error:
        print(error)
        if created_event_id:
            print()
            print("A temporary Google Calendar test event may remain.")
            print(f"Title: {TEST_EVENT_TITLE}")


def _format_value(value: object) -> str:
    # show missing fields clearly
    if value is None:
        return "Not provided"
    return str(value)


def _print_upcoming_events(events: list[dict[str, object]]) -> None:
    # print a small safe event summary
    print("Upcoming Google Calendar events:")
    print()

    if not events:
        print("No upcoming Google Calendar events found.")
        return

    for index, event in enumerate(events, start=1):
        print(f"{index}. {_format_value(event.get('summary'))}")
        print(f"   Start: {_format_google_start(event)}")
        print()


def _format_google_start(event: dict[str, object]) -> str:
    # format google event start values
    start = event.get("start")

    if not isinstance(start, dict):
        return "Not provided"

    raw_value = start.get("dateTime") or start.get("date")
    if not raw_value:
        return "Not provided"

    if "T" not in str(raw_value):
        return str(raw_value)

    try:
        start_time = datetime.fromisoformat(str(raw_value))
    except ValueError:
        return str(raw_value)

    return start_time.astimezone(ZoneInfo(TIMEZONE)).strftime("%B %-d, %Y at %-I:%M %p")


def _format_date(value: object) -> str:
    # format dates for normal output
    if hasattr(value, "strftime"):
        return value.strftime("%B %-d, %Y")
    return str(value)


def _format_due(value: object) -> str:
    # format due values for assignment output
    if value is None:
        return "Not provided"

    if hasattr(value, "strftime") and hasattr(value, "hour"):
        return value.strftime("%-I:%M %p")

    if hasattr(value, "strftime"):
        return value.strftime("%B %-d, %Y")

    return str(value)


def _print_event_inspection(events: list[dict[str, object]]) -> None:
    # print a small safe sample for debugging
    print(f"Canvas calendar items found: {len(events)}")
    print()
    print("Inspecting sample Canvas calendar items:")
    print()

    for index, event in enumerate(get_event_inspection(events), start=1):
        print(f"{index}. {_format_value(event.get('summary'))}")
        print(f"   UID: {_format_value(event.get('uid'))}")
        print(f"   Assignment: {_format_value(event.get('is_assignment'))}")
        print(f"   Start: {_format_value(event.get('start'))}")
        print(f"   End: {_format_value(event.get('end'))}")
        print(f"   Properties: {', '.join(event.get('properties') or [])}")
        print()


if __name__ == "__main__":
    main()
