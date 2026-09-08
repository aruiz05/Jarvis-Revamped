from google.oauth2.credentials import Credentials

from calendar_client import SCOPES, TOKEN_FILE, get_calendar_service, get_upcoming_events
from canvas_client import fetch_calendar_feed
from config import (
    APP_ENV,
    CANVAS_ICAL_URL,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    TIMEZONE,
    validate_timezone,
)
from scheduler import (
    HOURLY_SYNC_MINUTE,
    REMINDER_EVENT_HOUR,
    REMINDER_EVENT_MINUTE,
    REMINDER_PREP_HOUR,
    REMINDER_PREP_MINUTE,
    create_scheduler,
)


def run_deployment_check() -> bool:
    # verify deployment readiness without calendar writes
    print("Canvas Calendar Reminder")
    print("Deployment Check")
    print()
    print(f"Environment: {APP_ENV}")
    print(f"Timezone: {TIMEZONE}")
    print()

    checks = [
        ("Environment", _check_environment),
        ("Timezone", _check_timezone),
        ("Canvas configuration", _check_canvas_configuration),
        ("Canvas feed retrieval", _check_canvas_feed),
        ("Google credentials file", _check_google_credentials_file),
        ("Google token file", _check_google_token_file),
        ("Google token load", _check_google_token_load),
        ("Google Calendar authentication", _check_google_authentication),
        ("Scheduler configuration", _check_scheduler_configuration),
    ]

    passed = True

    for label, check in checks:
        try:
            check()
        except RuntimeError as error:
            print(f"{label}: FAILED")
            print(str(error))
            passed = False
            break

        print(f"{label}: OK")

    if not passed:
        print()
        print("Deployment check failed.")
        return False

    print()
    print(f"Hourly sync: :{HOURLY_SYNC_MINUTE:02d}")
    print(f"Daily reminder preparation: {_format_time(REMINDER_PREP_HOUR, REMINDER_PREP_MINUTE)}")
    print(f"Reminder event: {_format_time(REMINDER_EVENT_HOUR, REMINDER_EVENT_MINUTE)}")
    print()
    print("Deployment check passed.")
    return True


def _check_environment() -> None:
    # verify the app environment name
    if APP_ENV not in ("development", "production"):
        raise RuntimeError("APP_ENV must be development or production.")


def _check_timezone() -> None:
    # verify the timezone database can resolve the setting
    validate_timezone()


def _check_canvas_configuration() -> None:
    # verify the canvas feed setting exists
    if not CANVAS_ICAL_URL.strip():
        raise RuntimeError("CANVAS_ICAL_URL is not configured.")


def _check_canvas_feed() -> None:
    # verify canvas can be reached without printing the feed url
    fetch_calendar_feed()


def _check_google_credentials_file() -> None:
    # verify google oauth client file exists
    if not GOOGLE_CREDENTIALS_PATH.exists():
        raise RuntimeError("Google OAuth credentials file was not found.")


def _check_google_token_file() -> None:
    # verify google oauth token file exists
    if not GOOGLE_TOKEN_PATH.exists():
        raise RuntimeError(
            "Google OAuth token is unavailable.\n"
            "Authorize locally and configure the deployed token file."
        )


def _check_google_token_load() -> None:
    # verify token json can be loaded without printing it
    try:
        Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    except ValueError as exc:
        raise RuntimeError("Google OAuth token could not be loaded.") from exc


def _check_google_authentication() -> None:
    # verify google calendar can authenticate without browser auth
    service = get_calendar_service(allow_interactive=False)
    get_upcoming_events(service, limit=1)


def _check_scheduler_configuration() -> None:
    # verify scheduled jobs can be registered
    scheduler = create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}

    if "canvas_assignment_sync" not in jobs:
        raise RuntimeError("Hourly sync job is missing.")

    if "daily_due_reminder" not in jobs:
        raise RuntimeError("Daily reminder job is missing.")

    for job in jobs.values():
        if job.max_instances != 1:
            raise RuntimeError("A scheduled job allows overlapping runs.")

        if not job.coalesce:
            raise RuntimeError("A scheduled job is not configured to coalesce missed runs.")


def _format_time(hour: int, minute: int) -> str:
    # format scheduler times for deployment output
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix}"
