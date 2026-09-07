from datetime import date, datetime
import sys
from zoneinfo import ZoneInfo

from calendar_client import (
    PRIMARY_CALENDAR_ID,
    TEST_EVENT_TITLE,
    build_assignment_event,
    create_test_event,
    delete_event,
    get_calendar_service,
    get_upcoming_events,
    sync_assignment_event,
    verify_assignment_event_deadline,
    verify_assignment_event_metadata,
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
    sync_test_mode = "--sync-test" in sys.argv[1:]

    if calendar_test_mode:
        run_calendar_test()
        return

    if sync_test_mode:
        run_sync_test()
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


def run_sync_test() -> None:
    print("Canvas Calendar Reminder")
    print("Phase 6 Canvas to Google Calendar Sync Test")
    print()
    print("Loading Canvas assignments...")

    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
        assignments = get_assignments(events)
        selected_assignment = select_sync_test_assignment(assignments)
    except RuntimeError as error:
        print(error)
        return

    print(f"Assignments identified: {len(assignments)}")
    print()

    if selected_assignment is None:
        print("No upcoming Canvas assignment with a usable due date was found.")
        print("No Google Calendar event was created.")
        return

    print("Selected upcoming assignment:")
    print()
    print(f"Title: {selected_assignment.get('title')}")
    print(f"Due: {_format_assignment_due(selected_assignment)}")
    print(f"UID: {_format_value(selected_assignment.get('uid'))}")
    print()
    print("Duplicate prevention is enabled for this single assignment test.")
    print("The Canvas UID will be used to find an existing Google Calendar event.")
    print()
    print("Authenticating with Google...")

    try:
        service = get_calendar_service()
        print("Google Calendar connection successful.")
        print()
        print("Searching for an existing Google Calendar event...")
        print()

        event_body = build_assignment_event(selected_assignment)
        sync_result = sync_assignment_event(service, selected_assignment)
        synced_event = sync_result["event"]
        sync_action = sync_result["action"]

        metadata_verified = verify_assignment_event_metadata(
            service,
            synced_event,
            selected_assignment,
        )
        deadline_verified = verify_assignment_event_deadline(
            synced_event,
            selected_assignment,
        )
    except RuntimeError as error:
        print(error)
        return

    if sync_action == "created":
        print("Google Calendar assignment event created successfully.")
    elif sync_action == "updated":
        print("Existing Google Calendar assignment event updated successfully.")
    else:
        print("Existing Google Calendar assignment event already matches Canvas.")

    print()
    print(f"Title: {synced_event.get('summary')}")
    print(f"Start: {_format_google_start(synced_event)}")
    print(f"Calendar: {PRIMARY_CALENDAR_ID}")
    print(f"Event type: {_event_body_type(event_body)}")
    print(f"Sync action: {sync_action}")
    print()

    if metadata_verified:
        print("Canvas UID metadata stored successfully.")
    else:
        print("Canvas UID metadata verification failed.")

    if deadline_verified:
        print("Deadline verification passed.")
    else:
        print("Deadline verification failed.")

    print()
    print("The assignment event was left on your Google Calendar for manual inspection.")


def select_sync_test_assignment(assignments: list[dict[str, object]]) -> dict[str, object] | None:
    # select one upcoming assignment for the sync test
    timed_assignments = []
    date_only_assignments = []
    now = datetime.now(ZoneInfo(TIMEZONE))
    today = now.date()

    for assignment in assignments:
        due_at = assignment.get("due_at")

        if isinstance(due_at, datetime):
            normalized_due = due_at.astimezone(ZoneInfo(TIMEZONE))
            if normalized_due > now:
                timed_assignments.append(assignment)
            continue

        if isinstance(due_at, date) and due_at >= today:
            date_only_assignments.append(assignment)

    if timed_assignments:
        return min(timed_assignments, key=lambda assignment: assignment["due_at"])

    if date_only_assignments:
        return min(date_only_assignments, key=lambda assignment: assignment["due_at"])

    return None


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


def _format_assignment_due(assignment: dict[str, object]) -> str:
    # format the selected canvas due value
    due_at = assignment.get("due_at")

    if isinstance(due_at, datetime):
        return due_at.astimezone(ZoneInfo(TIMEZONE)).strftime("%B %-d, %Y at %-I:%M %p")

    if isinstance(due_at, date):
        return due_at.strftime("%B %-d, %Y")

    return "Not provided"


def _event_body_type(event_body: dict[str, object]) -> str:
    # report whether google received a timed or all day event
    start = event_body.get("start")

    if isinstance(start, dict) and "dateTime" in start:
        return "timed"

    if isinstance(start, dict) and "date" in start:
        return "all day"

    return "unknown"


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
