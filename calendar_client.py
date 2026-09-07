from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import TIMEZONE


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")
TEST_EVENT_TITLE = "Canvas Calendar Reminder - Phase 4 Test"
PRIMARY_CALENDAR_ID = "primary"
SYNC_SOURCE = "canvas_calendar_reminder"


def get_google_credentials() -> Credentials:
    # load saved google credentials when available
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


def get_calendar_service() -> Any:
    # create the google calendar api client
    credentials = get_google_credentials()
    return build("calendar", "v3", credentials=credentials)


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
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")


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
