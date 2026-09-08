# Canvas Calendar Reminder

Canvas Calendar Reminder synchronizes Canvas assignments with Google Calendar and creates a daily 7:45 AM Google Calendar reminder summarizing assignments due that day.

The application currently uses a private Canvas iCalendar feed to process assignments, connects to Google Calendar using OAuth 2.0, manually synchronizes current and upcoming Canvas assignments, creates a daily Google Calendar reminder event for assignments due today, can run those jobs on a local schedule while Python is running, and is configured for a Render Background Worker deployment.

## Planned Technologies

- Python
- Canvas iCalendar feed
- Google Calendar API
- python-dotenv
- APScheduler
- Render Background Worker

## Current Development Status

Phase 10: Always-On Cloud Deployment

Phase 10 code and configuration are complete. Cloud worker deployment is pending manual Render setup.

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
TIMEZONE=America/Phoenix
APP_ENV=development
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
ALLOW_INTERACTIVE_GOOGLE_AUTH=true
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

Preview the due today Google Calendar reminder event:

```bash
python main.py --reminder-preview
```

Manually create or update the due today Google Calendar reminder event:

```bash
python main.py --sync-daily-reminder
```

Show scheduler configuration:

```bash
python main.py --scheduler-info
```

Run one scheduled style assignment sync job:

```bash
python main.py --run-sync-job
```

Run one scheduled style daily reminder job:

```bash
python main.py --run-reminder-job
```

Start the local scheduler:

```bash
python main.py --scheduler
```

Create one notification test event a few minutes in the future:

```bash
python main.py --notification-test
```

Run a read only deployment readiness check:

```bash
python main.py --deployment-check
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

The reminder preview finds Canvas assignments due today and shows the Google Calendar summary event that would be created. The daily reminder sync command creates or updates one duplicate safe Google Calendar event for today when assignments are due.

To inspect a limited sample of Canvas event structure without printing the private feed URL, run:

```bash
python main.py --inspect
```

## Current Scope

This phase retrieves and parses Canvas iCalendar feed data, identifies assignment events, normalizes assignment deadlines, lists assignments due today, manually syncs current and upcoming Canvas assignments with duplicate prevention, previews daily reminder events, and creates duplicate safe Google Calendar reminder events.

The project does not delete stale Google Calendar events, add a database, add a web server, or add a frontend.

When run locally, the scheduler must remain running for automatic jobs to execute. Closing the terminal, stopping Python, putting the computer into a state where the process cannot run, or shutting down the computer will stop local automation. The Render worker deployment moves that long running process off the local computer.

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

Local development uses these default paths:

```env
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
ALLOW_INTERACTIVE_GOOGLE_AUTH=true
```

Production should use secret file paths configured by the host:

```env
GOOGLE_CREDENTIALS_PATH=<secret-file path>
GOOGLE_TOKEN_PATH=<secret-file path>
ALLOW_INTERACTIVE_GOOGLE_AUTH=false
```

Authorize Google OAuth locally first. The workflow is:

```text
credentials.json
run local Google auth
browser authorization
token.json generated
deploy credentials.json and token.json securely as secret files
```

The deployed worker does not attempt an interactive browser OAuth flow. The deployed `token.json` must include the Google refresh token created by local authorization so the worker can refresh expired access tokens after restarts.

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

## Daily Calendar Reminders

The daily reminder event is built from Canvas assignments due today.

The event title is:

```text
Assignments Due Today
```

The event is scheduled from `7:45 AM` to `8:00 AM` in `America/Phoenix`.

The event uses an explicit Google Calendar popup reminder at the event start time.

The description format is:

```text
Assignments due today:

* Assignment One - 4:30 PM
* Assignment Two - Due today
```

Timed assignments use the normalized `America/Phoenix` time in 12 hour format. Date only assignments are shown as `Due today`.

The preview command does not create or modify Google Calendar events:

```bash
python main.py --reminder-preview
```

The manual daily reminder sync command creates or updates one reminder event only when assignments are due today:

```bash
python main.py --sync-daily-reminder
```

If nothing is due today, no reminder event is created.

Daily reminder events use private extended properties:

```text
source=canvas_calendar_reminder
event_kind=daily_due_summary
reminder_date=yyyy-mm-dd
```

The event title is not used as the identity.

For notifications to appear on a phone, Google Calendar must be installed and configured on the phone, the same Google account or calendar must be active, Calendar notifications must be enabled, and operating system notification permissions for Google Calendar must be enabled.

## Local Scheduler

Canvas assignment synchronization:

```text
Every hour at :05 America/Phoenix
```

Daily reminder preparation:

```text
Every day at 7:30 AM America/Phoenix
```

Daily reminder event:

```text
7:45 AM - 8:00 AM America/Phoenix
```

Calendar popup:

```text
At event start
```

The reminder job runs at 7:30 AM so Google Calendar has time to register the event and its popup reminder before the event starts at 7:45 AM.

When the scheduler starts, it runs one immediate assignment synchronization so Google Calendar is current without waiting for the next hourly `:05` run.

If the scheduler starts before 7:45 AM, it performs startup recovery for today's daily reminder. If it starts after 7:45 AM, it skips recovery because the notification window has already passed.

The same scheduler command is used by the Render worker:

```bash
python main.py --scheduler
```

Use exactly one worker instance for this personal automation. Running multiple worker replicas could cause the same scheduled job to execute more than once, although event level duplicate prevention reduces some risk.

## Deployment

The repository includes:

```text
.python-version
render.yaml
```

`.python-version` pins deployment to Python 3.12. Render can choose the current supported Python 3.12 patch release.

`render.yaml` defines one Python background worker with:

```text
type: worker
runtime: python
build command: pip install -r requirements.txt
start command: python main.py --scheduler
```

Do not put secret values in `render.yaml`, README, source code, or Git.

Manual Render setup:

1. Push the repository to GitHub.
2. Create a Render Background Worker.
3. Connect the repository.
4. Use the Python runtime.
5. Use build command `pip install -r requirements.txt`.
6. Use start command `python main.py --scheduler`.
7. Configure `APP_ENV=production`.
8. Configure `TIMEZONE=America/Phoenix`.
9. Configure `CANVAS_ICAL_URL` as a secret environment variable.
10. Add `credentials.json` as a Render secret file.
11. Add the locally authorized `token.json` as a Render secret file.
12. Set `GOOGLE_CREDENTIALS_PATH` to the Render path for the credentials secret file.
13. Set `GOOGLE_TOKEN_PATH` to the Render path for the token secret file.
14. Configure `ALLOW_INTERACTIVE_GOOGLE_AUTH=false`.
15. Deploy exactly one worker instance.
16. Inspect logs and confirm the initial sync succeeds.

Run this before deploying and after configuring production variables:

```bash
python main.py --deployment-check
```

Expected startup logs include:

```text
Starting Canvas Calendar Reminder
Environment: production
Timezone: America/Phoenix
Running initial Canvas synchronization
Sync complete
Scheduler started
```

First production verification:

1. Confirm the worker remains running.
2. Confirm the next scheduled Canvas sync executes at the next `:05`.
3. Confirm the 7:30 AM reminder preparation runs on the next relevant morning.
4. Confirm the 7:45 AM Google Calendar phone notification appears when something is due.

After deployment, the local Mac does not need to remain on. Render runs the scheduler process.
