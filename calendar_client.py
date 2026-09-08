from datetime import date, datetime, timedelta
import logging
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    ALLOW_INTERACTIVE_GOOGLE_AUTH,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    TIMEZONE,
)


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = GOOGLE_CREDENTIALS_PATH
TOKEN_FILE = GOOGLE_TOKEN_PATH
TEST_EVENT_TITLE = "Canvas Calendar Reminder - Phase 4 Test"
NOTIFICATION_TEST_TITLE = "Canvas Calendar Reminder Notification Test"
PRIMARY_CALENDAR_ID = "primary"
SYNC_SOURCE = "canvas_calendar_reminder"
DAILY_REMINDER_EVENT_KIND = "daily_due_summary"
NOTIFICATION_TEST_EVENT_KIND = "notification_test"


def get_google_credentials(allow_interactive: bool | None = None) -> Credentials:
    # load saved google credentials when available
    if allow_interactive is None:
        allow_interactive = ALLOW_INTERACTIVE_GOOGLE_AUTH

    credentials = None

    if TOKEN_FILE.exists():
        try:
            credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except ValueError as exc:
            raise RuntimeError(
                "Existing Google token could not be loaded.\n"
                "Delete token.json and authorize the application again."
            ) from exc

        if not credentials.has_scopes(SCOPES):
            raise RuntimeError(
                "Existing Google token does not include the required Calendar scope.\n"
                "Delete token.json and authorize the application again."
            )

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        # refresh expired credentials when google allows it
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise RuntimeError(
                "Google credentials could not be refreshed.\n"
                "Delete token.json and authorize the application again."
            ) from exc
        _save_credentials(credentials)
        return credentials

    if not allow_interactive:
        raise RuntimeError(
            "Google OAuth token is unavailable.\n"
            "Authorize locally and configure the deployed token file."
        )

    if not CREDENTIALS_FILE.exists():
        raise RuntimeError(
            "Google OAuth credentials were not found.\n"
            "Place credentials.json in the project root."
        )

    print("Google authentication required.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        credentials = flow.run_local_server(
            port=0,
            authorization_prompt_message="Google authorization page opened in your browser.\n",
        )
    except Exception as exc:
        raise RuntimeError("Google authorization did not complete successfully.") from exc

    _save_credentials(credentials)
    return credentials


def get_calendar_service(allow_interactive: bool | None = None) -> Any:
    # create the google calendar api client
    credentials = get_google_credentials(allow_interactive=allow_interactive)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_upcoming_events(service: Any, limit: int = 5) -> list[dict[str, Any]]:
    # read a small number of upcoming events
    now = datetime.now(tz=ZoneInfo(TIMEZONE)).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId=PRIMARY_CALENDAR_ID,
                timeMin=now,
                maxResults=limit,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to connect to Google Calendar.") from exc

    return result.get("items", [])


def create_test_event(service: Any) -> dict[str, Any]:
    # create one temporary calendar event
    start_time = datetime.now(tz=ZoneInfo(TIMEZONE)) + timedelta(hours=1)
    end_time = start_time + timedelta(minutes=15)

    event_body = {
        "summary": TEST_EVENT_TITLE,
        "description": "Temporary event created by Canvas Calendar Reminder Phase 4 test",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    try:
        event = (
            service.events()
            .insert(calendarId=PRIMARY_CALENDAR_ID, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to create the Google Calendar test event.") from exc

    if not event.get("id"):
        raise RuntimeError("Google Calendar did not return a test event id.")

    return event


def create_notification_test_event(service: Any) -> dict[str, Any]:
    # create one notification test event
    start_time = datetime.now(tz=ZoneInfo(TIMEZONE)) + timedelta(minutes=3)
    end_time = start_time + timedelta(minutes=15)

    event_body = {
        "summary": NOTIFICATION_TEST_TITLE,
        "description": "Temporary event for testing Google Calendar phone notifications.",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "popup",
                    "minutes": 0,
                }
            ],
        },
        "extendedProperties": {
            "private": {
                "source": SYNC_SOURCE,
                "event_kind": NOTIFICATION_TEST_EVENT_KIND,
            }
        },
    }

    try:
        event = (
            service.events()
            .insert(calendarId=PRIMARY_CALENDAR_ID, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to create the notification test event.") from exc

    if not event.get("id"):
        raise RuntimeError("Google Calendar did not return a notification test event id.")

    return event


def build_assignment_event(assignment: dict[str, Any]) -> dict[str, Any]:
    # convert one canvas assignment into a google event body
    due_at = assignment.get("due_at")

    if due_at is None:
        raise RuntimeError("Selected Canvas assignment does not have a usable due date.")

    event_body = {
        "summary": assignment.get("title") or "Untitled Canvas assignment",
        "description": _build_assignment_description(assignment),
        "extendedProperties": {
            "private": {
                "canvas_uid": assignment.get("uid") or "",
                "source": SYNC_SOURCE,
            }
        },
    }

    if isinstance(due_at, datetime):
        start_time = _as_project_datetime(due_at)
        end_time = start_time + timedelta(minutes=15)
        event_body["start"] = {
            "dateTime": start_time.isoformat(),
            "timeZone": TIMEZONE,
        }
        event_body["end"] = {
            "dateTime": end_time.isoformat(),
            "timeZone": TIMEZONE,
        }
        return event_body

    if isinstance(due_at, date):
        event_body["start"] = {"date": due_at.isoformat()}
        event_body["end"] = {"date": (due_at + timedelta(days=1)).isoformat()}
        return event_body

    raise RuntimeError("Selected Canvas assignment does not have a usable due date.")


def create_assignment_event(service: Any, assignment: dict[str, Any]) -> dict[str, Any]:
    # insert exactly one canvas assignment event
    event_body = build_assignment_event(assignment)

    try:
        event = (
            service.events()
            .insert(calendarId=PRIMARY_CALENDAR_ID, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to create the Google Calendar assignment event.") from exc

    if not event.get("id"):
        raise RuntimeError("Google Calendar did not return an assignment event id.")

    return event


def find_event_by_canvas_uid(service: Any, canvas_uid: str) -> dict[str, Any] | None:
    # search google using private canvas metadata
    try:
        result = (
            service.events()
            .list(
                calendarId=PRIMARY_CALENDAR_ID,
                privateExtendedProperty=[
                    f"canvas_uid={canvas_uid}",
                    f"source={SYNC_SOURCE}",
                ],
                maxResults=10,
                singleEvents=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to search Google Calendar for the Canvas assignment event.") from exc

    matches = result.get("items", [])

    if not matches:
        return None

    if len(matches) > 1:
        raise RuntimeError(
            "Multiple Google Calendar events were found for the same Canvas UID.\n"
            "Manual cleanup may be required.\n"
            "No event was created or updated."
        )

    return matches[0]


def update_assignment_event(
    service: Any,
    event_id: str,
    assignment: dict[str, Any],
) -> dict[str, Any]:
    # update one existing canvas assignment event
    event_body = build_assignment_event(assignment)

    try:
        return (
            service.events()
            .patch(calendarId=PRIMARY_CALENDAR_ID, eventId=event_id, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to update the Google Calendar assignment event.") from exc


def sync_assignment_event(service: Any, assignment: dict[str, Any]) -> dict[str, Any]:
    # create update or keep one assignment event
    canvas_uid = assignment.get("uid")

    if not canvas_uid:
        raise RuntimeError("Selected Canvas assignment does not have a usable UID.")

    existing_event = find_event_by_canvas_uid(service, str(canvas_uid))

    if existing_event is None:
        created_event = create_assignment_event(service, assignment)
        return {"action": "created", "event": created_event}

    if assignment_event_needs_update(existing_event, assignment):
        updated_event = update_assignment_event(service, existing_event["id"], assignment)
        return {"action": "updated", "event": updated_event}

    return {"action": "unchanged", "event": existing_event}


def build_daily_reminder_event(reminder_date: date, description: str) -> dict[str, Any]:
    # build the daily google reminder event body
    start_time = datetime.combine(reminder_date, datetime.min.time()).replace(
        hour=7,
        minute=45,
        tzinfo=ZoneInfo(TIMEZONE),
    )
    end_time = start_time + timedelta(minutes=15)

    return {
        "summary": "Assignments Due Today",
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": TIMEZONE,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "popup",
                    "minutes": 0,
                }
            ],
        },
        "extendedProperties": {
            "private": {
                "source": SYNC_SOURCE,
                "event_kind": DAILY_REMINDER_EVENT_KIND,
                "reminder_date": reminder_date.isoformat(),
            }
        },
    }


def find_daily_reminder_event(
    service: Any,
    reminder_date: date,
) -> dict[str, Any] | None:
    # search google using daily reminder metadata
    try:
        result = (
            service.events()
            .list(
                calendarId=PRIMARY_CALENDAR_ID,
                privateExtendedProperty=[
                    f"source={SYNC_SOURCE}",
                    f"event_kind={DAILY_REMINDER_EVENT_KIND}",
                    f"reminder_date={reminder_date.isoformat()}",
                ],
                maxResults=10,
                singleEvents=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to search Google Calendar for the daily reminder event.") from exc

    matches = result.get("items", [])

    if not matches:
        return None

    if len(matches) > 1:
        raise RuntimeError(
            "Multiple daily reminder events were found for this date.\n"
            "Manual cleanup may be required.\n"
            "No reminder event was created or updated."
        )

    return matches[0]


def sync_daily_reminder_event(
    service: Any,
    reminder_date: date,
    description: str,
) -> dict[str, Any]:
    # create update or keep one daily reminder event
    expected_event = build_daily_reminder_event(reminder_date, description)
    existing_event = find_daily_reminder_event(service, reminder_date)

    if existing_event is None:
        created_event = _create_daily_reminder_event(service, expected_event)
        return {"action": "created", "event": created_event}

    if daily_reminder_event_needs_update(existing_event, expected_event):
        updated_event = _update_daily_reminder_event(
            service,
            existing_event["id"],
            expected_event,
        )
        return {"action": "updated", "event": updated_event}

    return {"action": "unchanged", "event": existing_event}


def daily_reminder_event_needs_update(
    event: dict[str, Any],
    expected_event: dict[str, Any],
) -> bool:
    # compare daily reminder event fields
    return any(
        [
            event.get("summary") != expected_event.get("summary"),
            event.get("description") != expected_event.get("description"),
            not _event_start_matches(event, expected_event),
            not _event_end_matches(event, expected_event),
            not _metadata_matches(event, expected_event),
            not _reminders_match(event, expected_event),
        ]
    )


def assignment_event_needs_update(
    event: dict[str, Any],
    assignment: dict[str, Any],
) -> bool:
    # compare google event fields with canvas assignment fields
    event_body = build_assignment_event(assignment)

    return any(
        [
            event.get("summary") != event_body.get("summary"),
            event.get("description") != event_body.get("description"),
            not _event_start_matches(event, event_body),
            not _event_end_matches(event, event_body),
            not _metadata_matches(event, event_body),
        ]
    )


def get_event(service: Any, event_id: str) -> dict[str, Any]:
    # fetch one google calendar event by id
    try:
        return (
            service.events()
            .get(calendarId=PRIMARY_CALENDAR_ID, eventId=event_id)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to retrieve the Google Calendar event.") from exc


def verify_assignment_event_metadata(
    service: Any,
    event: dict[str, Any],
    assignment: dict[str, Any],
) -> bool:
    # verify private metadata on the created event
    event_with_metadata = event
    private_metadata = _private_metadata(event_with_metadata)

    if not private_metadata:
        event_with_metadata = get_event(service, event["id"])
        private_metadata = _private_metadata(event_with_metadata)

    return (
        private_metadata.get("canvas_uid") == assignment.get("uid")
        and private_metadata.get("source") == SYNC_SOURCE
    )


def verify_assignment_event_deadline(
    event: dict[str, Any],
    assignment: dict[str, Any],
) -> bool:
    # compare the google start value to the canvas due value
    due_at = assignment.get("due_at")
    start = event.get("start")

    if not isinstance(start, dict):
        return False

    if isinstance(due_at, datetime):
        google_start = start.get("dateTime")
        if not google_start:
            return False
        try:
            google_datetime = datetime.fromisoformat(str(google_start))
        except ValueError:
            return False
        return google_datetime.astimezone(ZoneInfo(TIMEZONE)) == _as_project_datetime(due_at)

    if isinstance(due_at, date):
        return start.get("date") == due_at.isoformat()

    return False


def delete_event(service: Any, event_id: str) -> None:
    # delete only the event id returned by google
    try:
        service.events().delete(
            calendarId=PRIMARY_CALENDAR_ID,
            eventId=event_id,
        ).execute()
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to delete the Google Calendar test event.") from exc


def _save_credentials(credentials: Credentials) -> None:
    # save tokens locally without printing them
    try:
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    except OSError:
        logging.warning("Google token refresh succeeded but the token file could not be updated")


def _http_status(error: HttpError) -> int | str:
    # get a concise google http status
    return getattr(error.resp, "status", "unknown")


def _as_project_datetime(value: datetime) -> datetime:
    # normalize a datetime to the project timezone
    project_timezone = ZoneInfo(TIMEZONE)
    if value.tzinfo is None:
        return value.replace(tzinfo=project_timezone)
    return value.astimezone(project_timezone)


def _build_assignment_description(assignment: dict[str, Any]) -> str:
    # keep the google event description concise
    description = "Canvas assignment synced by Canvas Calendar Reminder."
    assignment_url = _safe_assignment_url(assignment.get("url"))

    if assignment_url:
        description = f"{description}\n\nCanvas:\n{assignment_url}"

    return description


def _safe_assignment_url(value: Any) -> str | None:
    # only include clear canvas assignment page urls
    if not value:
        return None

    parsed_url = urlparse(str(value))

    if parsed_url.query or parsed_url.fragment:
        return None

    if "/assignments/" not in parsed_url.path:
        return None

    return str(value)


def _private_metadata(event: dict[str, Any]) -> dict[str, str]:
    # read private extended properties safely
    extended_properties = event.get("extendedProperties")
    if not isinstance(extended_properties, dict):
        return {}

    private_properties = extended_properties.get("private")
    if not isinstance(private_properties, dict):
        return {}

    return private_properties


def _metadata_matches(event: dict[str, Any], event_body: dict[str, Any]) -> bool:
    # compare private extended properties
    return _private_metadata(event) == _private_metadata(event_body)


def _event_start_matches(event: dict[str, Any], event_body: dict[str, Any]) -> bool:
    # compare google event start values
    return _event_time_matches(event.get("start"), event_body.get("start"))


def _event_end_matches(event: dict[str, Any], event_body: dict[str, Any]) -> bool:
    # compare google event end values
    return _event_time_matches(event.get("end"), event_body.get("end"))


def _event_time_matches(actual: Any, expected: Any) -> bool:
    # compare timed and all day values safely
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False

    if "date" in expected:
        return actual.get("date") == expected.get("date")

    if "dateTime" not in expected:
        return False

    actual_datetime = _parse_google_datetime(actual.get("dateTime"))
    expected_datetime = _parse_google_datetime(expected.get("dateTime"))

    if actual_datetime is None or expected_datetime is None:
        return False

    return actual_datetime == expected_datetime


def _parse_google_datetime(value: Any) -> datetime | None:
    # parse google datetimes into the project timezone
    if not value:
        return None

    try:
        parsed_datetime = datetime.fromisoformat(str(value))
    except ValueError:
        return None

    return _as_project_datetime(parsed_datetime)


def _create_daily_reminder_event(
    service: Any,
    event_body: dict[str, Any],
) -> dict[str, Any]:
    # insert one daily reminder event
    try:
        event = (
            service.events()
            .insert(calendarId=PRIMARY_CALENDAR_ID, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to create the daily reminder event.") from exc

    if not event.get("id"):
        raise RuntimeError("Google Calendar did not return a daily reminder event id.")

    return event


def _update_daily_reminder_event(
    service: Any,
    event_id: str,
    event_body: dict[str, Any],
) -> dict[str, Any]:
    # update one daily reminder event
    try:
        return (
            service.events()
            .patch(calendarId=PRIMARY_CALENDAR_ID, eventId=event_id, body=event_body)
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar request failed with HTTP status {_http_status(exc)}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to update the daily reminder event.") from exc


def _reminders_match(event: dict[str, Any], expected_event: dict[str, Any]) -> bool:
    # compare explicit reminder settings
    return event.get("reminders") == expected_event.get("reminders")
