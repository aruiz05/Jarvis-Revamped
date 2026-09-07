from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
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
