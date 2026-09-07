from datetime import date, datetime
from typing import Any

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config import (
    MY_PHONE_NUMBER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
)


TEST_SMS_MESSAGE = "Canvas Calendar Reminder SMS test successful."


def validate_sms_config() -> None:
    # check required twilio settings before sending
    missing_values = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
            "TWILIO_FROM_NUMBER": TWILIO_FROM_NUMBER,
            "MY_PHONE_NUMBER": MY_PHONE_NUMBER,
        }.items()
        if not value
    ]

    if missing_values:
        missing_list = "\n".join(missing_values)
        raise RuntimeError(
            "Twilio configuration is incomplete.\n\n"
            "Please configure:\n"
            f"{missing_list}\n"
            "in .env."
        )

    _validate_phone_number("TWILIO_FROM_NUMBER", TWILIO_FROM_NUMBER)
    _validate_phone_number("MY_PHONE_NUMBER", MY_PHONE_NUMBER)


def build_due_today_message(assignments: list[dict[str, Any]]) -> str | None:
    # build one reminder message for all due assignments
    if not assignments:
        return None

    lines = ["Canvas reminder due today:", ""]

    for assignment in assignments:
        title = assignment.get("title") or "Untitled Canvas assignment"
        due_text = _format_assignment_due(assignment.get("due_at"))
        lines.append(f"* {title} - {due_text}")

    return "\n".join(lines)


def send_sms(message: str) -> dict[str, str | None]:
    # send exactly one twilio message request
    validate_sms_config()
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    try:
        twilio_message = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=MY_PHONE_NUMBER,
        )
    except TwilioRestException as exc:
        raise RuntimeError(f"Twilio rejected the message with error code {exc.code}.") from exc
    except Exception as exc:
        raise RuntimeError("Unable to send SMS through Twilio.") from exc

    return {
        "sid": twilio_message.sid,
        "status": twilio_message.status,
    }


def _validate_phone_number(name: str, value: str) -> None:
    # validate simple e164 phone number format
    if not value.startswith("+") or not value[1:].isdigit():
        raise RuntimeError(
            f"{name} must use E.164 format like +15551234567."
        )


def _format_assignment_due(value: Any) -> str:
    # format due values for sms output
    if isinstance(value, datetime):
        return value.strftime("%-I:%M %p")

    if isinstance(value, date):
        return "Due today"

    return "Due today"
