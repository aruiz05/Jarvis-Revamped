import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


load_dotenv()

# app environment name
APP_ENV = os.getenv("APP_ENV", "development").strip().lower() or "development"

# canvas feed secret from local env
CANVAS_ICAL_URL = os.getenv("CANVAS_ICAL_URL", "")

# default local timezone
TIMEZONE = os.getenv("TIMEZONE", "America/Phoenix")

# google oauth file paths
GOOGLE_CREDENTIALS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
GOOGLE_TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

# interactive google auth is for local setup only
ALLOW_INTERACTIVE_GOOGLE_AUTH = (
    os.getenv("ALLOW_INTERACTIVE_GOOGLE_AUTH", "true").strip().lower()
    in ("1", "true", "yes", "on")
)


def is_production() -> bool:
    # check whether the app is running as a deployed worker
    return APP_ENV == "production"


def validate_timezone() -> None:
    # verify the configured timezone can be loaded
    try:
        ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Timezone configuration is invalid.") from exc


def validate_required_configuration() -> None:
    # validate core configuration before starting production jobs
    validate_timezone()

    if not CANVAS_ICAL_URL.strip():
        raise RuntimeError("Canvas calendar configuration is missing.")

    if is_production() and not GOOGLE_CREDENTIALS_PATH.exists():
        raise RuntimeError("Google OAuth credentials file is missing.")

    if is_production() and not GOOGLE_TOKEN_PATH.exists():
        raise RuntimeError(
            "Google OAuth token is unavailable.\n"
            "Authorize locally and configure the deployed token file."
        )
