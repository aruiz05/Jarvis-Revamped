from datetime import date, datetime
import sys
from zoneinfo import ZoneInfo

from calendar_client import (
    NOTIFICATION_TEST_TITLE,
    PRIMARY_CALENDAR_ID,
    TEST_EVENT_TITLE,
    build_daily_reminder_event,
    build_assignment_event,
    create_notification_test_event,
    create_test_event,
    delete_event,
    get_calendar_service,
    get_upcoming_events,
    sync_daily_reminder_event,
    sync_assignment_event,
    verify_assignment_event_deadline,
    verify_assignment_event_metadata,
)
from config import TIMEZONE
from canvas_client import (
    fetch_calendar_feed,
    get_assignment_skip_counts,
    get_assignments,
    get_assignments_due_today,
    get_event_inspection,
    get_syncable_assignments,
    get_today,
    parse_calendar_feed,
)
from reminder_client import DAILY_REMINDER_TITLE, build_daily_reminder_description
from scheduler import (
    print_scheduler_info,
    run_calendar_sync_job,
    run_daily_reminder_job,
    start_scheduler,
)


def main() -> None:
    # reject unsupported command options
    known_options = {
        "--inspect",
        "--calendar-test",
        "--sync-test",
        "--sync-update-test",
        "--sync-all",
        "--dry-run",
        "--reminder-preview",
        "--sync-daily-reminder",
        "--scheduler",
        "--scheduler-info",
        "--run-sync-job",
        "--run-reminder-job",
        "--notification-test",
    }
    unknown_options = [option for option in sys.argv[1:] if option not in known_options]

    if unknown_options:
        print(f"Unknown command option: {unknown_options[0]}")
        return

    # check for optional inspection mode
    inspect_mode = "--inspect" in sys.argv[1:]
    calendar_test_mode = "--calendar-test" in sys.argv[1:]
    sync_test_mode = "--sync-test" in sys.argv[1:]
    sync_update_test_mode = "--sync-update-test" in sys.argv[1:]
    sync_all_mode = "--sync-all" in sys.argv[1:]
    dry_run_mode = "--dry-run" in sys.argv[1:]
    reminder_preview_mode = "--reminder-preview" in sys.argv[1:]
    sync_daily_reminder_mode = "--sync-daily-reminder" in sys.argv[1:]
    scheduler_mode = "--scheduler" in sys.argv[1:]
    scheduler_info_mode = "--scheduler-info" in sys.argv[1:]
    run_sync_job_mode = "--run-sync-job" in sys.argv[1:]
    run_reminder_job_mode = "--run-reminder-job" in sys.argv[1:]
    notification_test_mode = "--notification-test" in sys.argv[1:]

    if calendar_test_mode:
        run_calendar_test()
        return

    if scheduler_info_mode:
        print_scheduler_info()
        return

    if run_sync_job_mode:
        run_calendar_sync_job()
        return

    if run_reminder_job_mode:
        run_daily_reminder_job()
        return

    if notification_test_mode:
        run_notification_test()
        return

    if scheduler_mode:
        start_scheduler()
        return

    if reminder_preview_mode:
        run_reminder_preview()
        return

    if sync_daily_reminder_mode:
        run_sync_daily_reminder()
        return

    if sync_test_mode or sync_update_test_mode:
        run_sync_test()
        return

    if sync_all_mode:
        run_sync_all(dry_run=dry_run_mode)
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


def run_sync_all(dry_run: bool = False) -> None:
    if dry_run:
        print("Canvas Calendar Reminder")
        print("Phase 7 Full Sync Dry Run")
    else:
        print("Canvas Calendar Reminder")
        print("Phase 7 Full Canvas to Google Calendar Sync")
    print()
    print("Loading Canvas calendar...")
    print()

    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
        assignments = get_assignments(events)
    except RuntimeError as error:
        print(error)
        return

    skip_counts = get_assignment_skip_counts(assignments)
    syncable_assignments = get_syncable_assignments(assignments)

    print(f"Canvas calendar items found: {len(events)}")
    print(f"Assignments identified: {len(assignments)}")
    print()
    print(f"Past assignments skipped: {skip_counts['past_assignments']}")
    print(f"Assignments without usable due dates skipped: {skip_counts['missing_due_dates']}")
    print()
    print(f"Assignments ready to sync: {len(syncable_assignments)}")
    print()

    if not syncable_assignments:
        print("No current or upcoming Canvas assignments with usable due dates were found.")
        return

    _print_sync_preview(syncable_assignments)

    if dry_run:
        print()
        print("DRY RUN ONLY")
        print("No Google Calendar events were created or modified.")
        return

    print()
    print(
        f"This will synchronize {len(syncable_assignments)} Canvas assignments "
        "with your primary Google Calendar."
    )
    answer = input("Continue? [y/N]: ").strip().lower()

    if answer not in ("y", "yes"):
        print("Synchronization cancelled.")
        print("No Google Calendar changes were made.")
        return

    print()
    print("Authenticating with Google...")

    try:
        service = get_calendar_service()
    except RuntimeError as error:
        print(error)
        return

    print("Google Calendar connection successful.")
    print()
    print("Synchronizing assignments...")
    print()

    summary = _sync_assignments(service, syncable_assignments)
    _print_sync_summary(summary)


def run_reminder_preview() -> None:
    print("Canvas Calendar Reminder")
    print("Daily Reminder Preview")
    print()

    due_today = _load_due_today_assignments()

    if due_today is None:
        return

    print(f"Today: {_format_date(get_today())}")
    print()
    print(f"Assignments due today: {len(due_today)}")
    print()

    if not due_today:
        print("Nothing is due today.")
        print("No reminder event is needed.")
        return

    reminder_date = get_today()
    description = build_daily_reminder_description(due_today)
    event_body = build_daily_reminder_event(reminder_date, description)

    print(f"Date: {_format_date(reminder_date)}")
    print(f"Event time: 7:45 AM {TIMEZONE}")
    print()
    print("Title:")
    print(DAILY_REMINDER_TITLE)
    print()
    print("Description:")
    print()
    print(description)
    print("PREVIEW ONLY")
    print("No Google Calendar event was created or modified.")
    _ = event_body


def run_sync_daily_reminder() -> None:
    print("Canvas Calendar Reminder")
    print("Daily Reminder Sync")
    print()

    due_today = _load_due_today_assignments()

    if due_today is None:
        return

    print(f"Today: {_format_date(get_today())}")
    print()
    print(f"Assignments due today: {len(due_today)}")
    print()

    if not due_today:
        print("Nothing is due today.")
        print("No reminder event was created.")
        return

    reminder_date = get_today()
    description = build_daily_reminder_description(due_today)

    try:
        print("Authenticating with Google...")
        service = get_calendar_service()
        print("Google Calendar connection successful.")
        print()
        result = sync_daily_reminder_event(service, reminder_date, description)
    except RuntimeError as error:
        print(error)
        return

    action = result.get("action")

    if action == "created":
        print("Daily reminder event created.")
    elif action == "updated":
        print("Existing daily reminder event found.")
        print("Assignment list changed.")
        print("Daily reminder event updated.")
    else:
        print("Existing daily reminder event found.")
        print("No changes detected.")
        print("No update required.")

    print(f"Title: {result['event'].get('summary')}")
    print(f"Start: {_format_google_start(result['event'])}")
    print(f"Calendar: {PRIMARY_CALENDAR_ID}")


def run_notification_test() -> None:
    print("Canvas Calendar Reminder")
    print("Notification Test")
    print()
    print("Authenticating with Google...")

    try:
        service = get_calendar_service()
        print("Google Calendar connection successful.")
        print()
        print("Creating notification test event...")
        event = create_notification_test_event(service)
    except RuntimeError as error:
        print(error)
        return

    print("Notification test event created.")
    print(f"Title: {event.get('summary') or NOTIFICATION_TEST_TITLE}")
    print(f"Start: {_format_google_start(event)}")
    print("Popup reminder: at event start")
    print()
    print("The event was left on your calendar so the notification can fire.")
    print("Check your phone for the Google Calendar notification.")


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


def _load_due_today_assignments() -> list[dict[str, object]] | None:
    # load canvas assignments due today
    print("Loading Canvas assignments...")

    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
        assignments = get_assignments(events)
    except RuntimeError as error:
        print(error)
        return None

    return get_assignments_due_today(assignments)


def _sync_assignments(
    service: object,
    assignments: list[dict[str, object]],
) -> dict[str, int]:
    # process assignments one at a time
    summary = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "conflicts": 0,
        "failed": 0,
    }
    total = len(assignments)

    for index, assignment in enumerate(assignments, start=1):
        summary["processed"] += 1
        title = assignment.get("title") or "Untitled Canvas assignment"

        print(f"[{index}/{total}] {title}")

        try:
            result = sync_assignment_event(service, assignment)
        except RuntimeError as error:
            if "Multiple Google Calendar events" in str(error):
                summary["conflicts"] += 1
                print("       CONFLICT: multiple Google events found")
                print(f"       UID: {_format_value(assignment.get('uid'))}")
            else:
                summary["failed"] += 1
                print(f"       FAILED: {error}")
            print()
            continue

        action = result.get("action")

        if action == "created":
            summary["created"] += 1
            print("       Created")
        elif action == "updated":
            summary["updated"] += 1
            print("       Updated")
        else:
            summary["unchanged"] += 1
            print("       Unchanged")

        print()

    return summary


def _print_sync_preview(assignments: list[dict[str, object]], limit: int = 10) -> None:
    # show a small sync preview
    print("Upcoming assignments:")
    print()

    for index, assignment in enumerate(assignments[:limit], start=1):
        print(f"{index}. {assignment.get('title')}")
        print(f"   Due: {_format_assignment_due(assignment)}")
        print()

    if len(assignments) > limit:
        print(f"...and {len(assignments) - limit} more")


def _print_sync_summary(summary: dict[str, int]) -> None:
    # print final bulk sync counts
    print("Synchronization complete.")
    print()
    print(f"Assignments processed: {summary['processed']}")
    print()
    print(f"Created:   {summary['created']}")
    print(f"Updated:   {summary['updated']}")
    print(f"Unchanged: {summary['unchanged']}")
    print(f"Conflicts: {summary['conflicts']}")
    print(f"Failed:    {summary['failed']}")


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
