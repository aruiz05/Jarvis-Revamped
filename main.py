import sys

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


def _format_value(value: object) -> str:
    # show missing fields clearly
    if value is None:
        return "Not provided"
    return str(value)


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
