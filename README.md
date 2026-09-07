# Canvas Calendar Reminder

Canvas Calendar Reminder will eventually synchronize Canvas assignments with Google Calendar and send a morning SMS reminder at 7:45 AM on days when assignments are due.

The application currently uses a private Canvas iCalendar feed to process assignments, connects to Google Calendar using OAuth 2.0, manually synchronizes current and upcoming Canvas assignments, and can send manual SMS reminders through Twilio.

## Planned Technologies

- Python
- Canvas iCalendar feed
- Google Calendar API
- Twilio SMS
- python-dotenv

## Current Development Status

Phase 8: SMS Reminder Integration

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

Run the Google Calendar connection test:

```bash
python main.py --calendar-test
```

Run the controlled Canvas to Google Calendar sync test:

```bash
python main.py --sync-test
```

Preview a full manual synchronization without changing Google Calendar:

```bash
python main.py --sync-all --dry-run
```

Run a full manual synchronization:

```bash
python main.py --sync-all
```

Preview the due today SMS reminder without sending:

```bash
python main.py --reminder-preview
```

Send a controlled Twilio test message:

```bash
python main.py --sms-test
```

Manually send the real due today reminder:

```bash
python main.py --send-reminder
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

The calendar test authenticates with Google Calendar, creates or reuses `token.json`, reads a small number of upcoming events from the primary calendar, creates one temporary Phase 4 test event, and deletes that exact event.

The sync test retrieves Canvas assignments, selects one upcoming assignment, searches Google Calendar for an event with the same Canvas UID, and then creates updates or leaves that one event unchanged.

The full sync command retrieves Canvas assignments, filters to current and upcoming assignments, uses Canvas UID metadata to avoid duplicates, creates missing Google Calendar events, updates changed events, leaves matching events unchanged, reports duplicate conflicts, and prints synchronization statistics.

The reminder preview finds Canvas assignments due today and prints the SMS message without contacting Twilio. The SMS test sends exactly one controlled message. The send reminder command sends one message only when at least one assignment is due today.

To inspect a limited sample of Canvas event structure without printing the private feed URL, run:

```bash
python main.py --inspect
```

## Current Scope

This phase retrieves and parses Canvas iCalendar feed data, identifies assignment events, normalizes assignment deadlines, lists assignments due today, manually syncs current and upcoming Canvas assignments with duplicate prevention, previews reminder messages, and sends manual Twilio SMS reminders.

The project does not yet delete stale Google Calendar events, run automatically at 7:45 AM, add scheduling, add a database, add a web server, or add a frontend.

Automatic 7:45 AM scheduling is NOT implemented yet. Stale Google Calendar event deletion is not implemented yet.

Running `--send-reminder` manually more than once may send the reminder more than once.

## Assignment Identification

In the inspected Canvas ICS feed, assignment entries use `UID` values beginning with `event-assignment-` or `event-assignment-override-`. General calendar entries use a different `UID` pattern such as `event-calendar-event-`.

This is a structural Canvas feed pattern, so it is more reliable than matching assignment titles. If Canvas changes its ICS UID format in the future, assignment filtering may need to be updated.

## Google Calendar Credentials

Google Calendar uses OAuth 2.0 desktop application credentials.

Place `credentials.json` in the project root before running:

```bash
python main.py --calendar-test
```

After successful authorization, the application creates `token.json` automatically and reuses it on later runs.

Never commit `credentials.json` or `token.json`. Both files are ignored by Git.

## Google Event Representation

Timed Canvas assignments are represented as timed Google Calendar events:

```text
Google event start = Canvas deadline
Google event duration = 15 minutes
Timezone = America/Phoenix
```

Date only Canvas assignments are represented as all day Google Calendar events on the Canvas assignment date.

The Canvas assignment UID is stored in Google Calendar private extended properties as `canvas_uid`, with `source` set to `canvas_calendar_reminder`.

## Duplicate Prevention

The sync test searches Google Calendar using private extended properties:

```text
canvas_uid=<canvas assignment uid>
source=canvas_calendar_reminder
```

If no matching Google Calendar event exists, the test creates one event.

If exactly one matching event exists, the test compares the title, description, start, end, and private metadata. If anything differs, it updates the existing event. If everything already matches, it does nothing.

If multiple matching events exist, the test stops and reports that manual cleanup may be required. It does not delete duplicates automatically.

## Full Synchronization

Use dry run mode first:

```bash
python main.py --sync-all --dry-run
```

Dry run downloads Canvas data, identifies assignments, filters out past assignments and assignments without usable due dates, sorts the remaining assignments chronologically, and previews what would be synchronized. It does not authenticate with Google and does not create update or delete any Google Calendar events.

Run full manual sync only after reviewing the dry run:

```bash
python main.py --sync-all
```

The command asks for confirmation before making Google Calendar changes. It processes assignments sequentially and reports counts for created, updated, unchanged, conflict, and failed assignments.

Canvas UID metadata remains the identity for synchronized events. Event titles are never used to decide whether an assignment already exists.

## SMS Reminders

The reminder message is built from Canvas assignments due today.

Example format:

```text
Canvas reminder due today:

* Assignment One - 4:30 PM
* Assignment Two - Due today
```

Timed assignments use the normalized `America/Phoenix` time in 12 hour format. Date only assignments are shown as `Due today`.

The preview command never contacts Twilio:

```bash
python main.py --reminder-preview
```

The transport test sends exactly one controlled SMS:

```bash
python main.py --sms-test
```

The manual reminder command sends exactly one SMS only if at least one assignment is due today:

```bash
python main.py --send-reminder
```
