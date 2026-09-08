import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from calendar_client import get_calendar_service, sync_assignment_event, sync_daily_reminder_event
from canvas_client import (
    fetch_calendar_feed,
    get_assignments,
    get_assignments_due_today,
    get_syncable_assignments,
    parse_calendar_feed,
)
from config import APP_ENV, TIMEZONE, validate_required_configuration
from reminder_client import build_daily_reminder_description


REMINDER_PREP_HOUR = 7
REMINDER_PREP_MINUTE = 30
REMINDER_EVENT_HOUR = 7
REMINDER_EVENT_MINUTE = 45
HOURLY_SYNC_MINUTE = 5
JOB_MISFIRE_GRACE_SECONDS = 900


def configure_logging() -> None:
    # configure simple scheduler logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def print_sync_summary(summary: dict[str, int]) -> None:
    # print sync counts for cloud logs
    logging.info("Sync complete:")
    logging.info("Created: %s", summary["created"])
    logging.info("Updated: %s", summary["updated"])
    logging.info("Unchanged: %s", summary["unchanged"])
    logging.info("Conflicts: %s", summary["conflicts"])
    logging.info("Failed: %s", summary["failed"])


def print_scheduler_info() -> None:
    print("Canvas Calendar Reminder")
    print("Scheduler Information")
    print()
    print("Timezone:")
    print(TIMEZONE)
    print()
    print("Canvas assignment synchronization:")
    print("Every hour at :05")
    print()
    print("Daily reminder preparation:")
    print("Every day at 7:30 AM")
    print()
    print("Daily reminder event:")
    print("7:45 AM - 8:00 AM")
    print()
    print("Popup:")
    print("At event start")


def run_calendar_sync_job() -> dict[str, int]:
    # run one automatic assignment sync
    configure_logging()
    logging.info("Starting Canvas synchronization")

    summary = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "conflicts": 0,
        "failed": 0,
    }

    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
        assignments = get_assignments(events)
        syncable_assignments = get_syncable_assignments(assignments)
        service = get_calendar_service()

        for assignment in syncable_assignments:
            summary["processed"] += 1
            try:
                result = sync_assignment_event(service, assignment)
            except RuntimeError as error:
                if "Multiple Google Calendar events" in str(error):
                    summary["conflicts"] += 1
                    logging.warning(
                        "Conflict for %s",
                        assignment.get("title") or "Untitled Canvas assignment",
                    )
                else:
                    summary["failed"] += 1
                    logging.error(
                        "Failed to sync %s: %s",
                        assignment.get("title") or "Untitled Canvas assignment",
                        error,
                    )
                continue

            action = result.get("action")

            if action == "created":
                summary["created"] += 1
            elif action == "updated":
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1

        print_sync_summary(summary)
    except RuntimeError as error:
        summary["failed"] += 1
        logging.error("Canvas synchronization failed: %s", error)

    return summary


def run_daily_reminder_job() -> dict[str, object]:
    # prepare one daily reminder event when needed
    configure_logging()
    logging.info("Preparing daily assignment reminder")

    try:
        ics_data = fetch_calendar_feed()
        events = parse_calendar_feed(ics_data)
        assignments = get_assignments(events)
        due_today = get_assignments_due_today(assignments)
    except RuntimeError as error:
        logging.error("Daily reminder preparation failed: %s", error)
        return {"action": "failed", "assignments_due_today": 0}

    logging.info("Assignments due today: %s", len(due_today))

    if not due_today:
        logging.info("Nothing is due today")
        logging.info("No daily reminder event was created")
        return {"action": "none", "assignments_due_today": 0}

    try:
        service = get_calendar_service()
        description = build_daily_reminder_description(due_today)
        result = sync_daily_reminder_event(
            service,
            datetime.now(ZoneInfo(TIMEZONE)).date(),
            description,
        )
    except RuntimeError as error:
        logging.error("Daily reminder sync failed: %s", error)
        return {"action": "failed", "assignments_due_today": len(due_today)}

    logging.info("Daily reminder event %s for 7:45 AM", result.get("action"))
    return {
        "action": result.get("action"),
        "assignments_due_today": len(due_today),
    }


def run_startup_recovery() -> None:
    # prepare the reminder before the notification window closes
    now = datetime.now(ZoneInfo(TIMEZONE))
    reminder_time = time(REMINDER_EVENT_HOUR, REMINDER_EVENT_MINUTE)

    if now.time() < reminder_time:
        logging.info("Running startup reminder recovery")
        run_daily_reminder_job()
        return

    logging.info("Today's 7:45 AM reminder window has already passed")
    logging.info("Startup reminder recovery skipped")


def create_scheduler() -> BlockingScheduler:
    # register local scheduler jobs
    timezone = ZoneInfo(TIMEZONE)
    scheduler = BlockingScheduler(timezone=timezone)

    scheduler.add_job(
        run_calendar_sync_job,
        CronTrigger(minute=HOURLY_SYNC_MINUTE, timezone=timezone),
        id="canvas_assignment_sync",
        name="Canvas assignment sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=JOB_MISFIRE_GRACE_SECONDS,
    )
    scheduler.add_job(
        run_daily_reminder_job,
        CronTrigger(
            hour=REMINDER_PREP_HOUR,
            minute=REMINDER_PREP_MINUTE,
            timezone=timezone,
        ),
        id="daily_due_reminder",
        name="Daily reminder preparation",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=JOB_MISFIRE_GRACE_SECONDS,
    )

    return scheduler


def start_scheduler() -> None:
    # start the local blocking scheduler
    configure_logging()
    logging.info("Starting Canvas Calendar Reminder")
    logging.info("Environment: %s", APP_ENV)
    logging.info("Timezone: %s", TIMEZONE)

    try:
        validate_required_configuration()
    except RuntimeError as error:
        logging.error("Configuration error: %s", error)
        return

    print("Canvas Calendar Reminder")
    print("Automatic Scheduler")
    print()
    print(f"Environment: {APP_ENV}")
    print()
    print(f"Timezone: {TIMEZONE}")
    print()
    print("Assignment synchronization:")
    print("Every hour at :05")
    print()
    print("Daily reminder preparation:")
    print("Every day at 7:30 AM")
    print()
    print("Daily reminder notification:")
    print("Google Calendar event at 7:45 AM")
    print()
    print("Running initial Canvas synchronization...")

    run_calendar_sync_job()
    run_startup_recovery()

    scheduler = create_scheduler()

    print()
    print("Scheduler started.")
    print("Press Ctrl+C to stop.")

    for job in scheduler.get_jobs():
        print(f"{job.name}: registered")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
