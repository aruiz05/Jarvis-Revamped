# Canvas Calendar Reminder

Canvas Calendar Reminder will eventually synchronize Canvas assignments with Google Calendar and send a morning SMS reminder at 7:45 AM on days when assignments are due.

The application currently uses a private Canvas iCalendar feed to download Canvas calendar data, parse ICS data, identify assignment events, normalize assignment deadlines to `America/Phoenix`, and determine which assignments are due today.

## Planned Technologies

- Python
- Canvas iCalendar feed
- Google Calendar API
- Twilio SMS
- python-dotenv

## Current Development Status

Phase 3: Canvas Assignment Filtering and Due Date Processing

## Local Setup

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` with your private Canvas calendar feed URL:

```env
CANVAS_ICAL_URL=
```

The iCal URL should come from your own Canvas Calendar Feed settings. Store it only in `.env` and never commit it.

Run the project:

```bash
python main.py
```

Expected output:

```text
Canvas Calendar Reminder
Loading Canvas calendar...

Canvas calendar loaded successfully.

Canvas calendar items found: 135
Assignments identified: 101

Today: September 6, 2026

Assignments due today: 0

Nothing is due today.
```

The exact assignment counts and due items depend on your Canvas feed.

To inspect a limited sample of Canvas event structure without printing the private feed URL, run:

```bash
python main.py --inspect
```

## Current Scope

This phase retrieves and parses Canvas iCalendar feed data, identifies assignment events, normalizes assignment deadlines, and lists assignments due today.

The project does not yet sync assignments to Google Calendar, create Google Calendar events, send SMS reminders, run automatically at 7:45 AM, add scheduling, add a database, add a web server, or add a frontend.

## Assignment Identification

In the inspected Canvas ICS feed, assignment entries use `UID` values beginning with `event-assignment-` or `event-assignment-override-`. General calendar entries use a different `UID` pattern such as `event-calendar-event-`.

This is a structural Canvas feed pattern, so it is more reliable than matching assignment titles. If Canvas changes its ICS UID format in the future, assignment filtering may need to be updated.
