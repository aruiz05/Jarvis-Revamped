# Canvas Calendar Reminder

Canvas Calendar Reminder will eventually synchronize Canvas assignments with Google Calendar and send a morning SMS reminder at 7:45 AM on days when assignments are due.

The application currently uses a private Canvas iCalendar feed to download Canvas calendar data, parse ICS data, read `VEVENT` entries, and display basic calendar information.

## Planned Technologies

- Python
- Canvas iCalendar feed
- Google Calendar API
- Twilio SMS
- python-dotenv

## Current Development Status

Phase 2: Canvas iCalendar Feed Integration

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

Canvas calendar items: 14
```

The exact calendar items shown depend on your Canvas feed.

## Current Scope

This phase only retrieves and parses Canvas iCalendar feed data.

The project does not yet sync with Google Calendar, send SMS reminders, determine what is due today, normalize timezones, run automatically at 7:45 AM, add scheduling, add a database, add a web server, or add a frontend.
