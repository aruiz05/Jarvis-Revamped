from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import TIMEZONE


DAILY_REMINDER_TITLE = "Assignments Due Today"


def build_daily_reminder_description(assignments: list[dict[str, Any]]) -> str:
    # build one description for the daily reminder event
    lines = ["Assignments due today:", ""]

    for assignment in assignments:
        title = assignment.get("title") or "Untitled Canvas assignment"
        due_text = _format_assignment_due(assignment.get("due_at"))
        lines.append(f"* {title} - {due_text}")

    return "\n".join(lines)


def _format_assignment_due(value: Any) -> str:
    # format assignment due values for reminder text
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo(TIMEZONE)).strftime("%-I:%M %p")

    if isinstance(value, date):
        return "Due today"

    return "Due today"
