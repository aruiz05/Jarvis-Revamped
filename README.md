# Canvas Calendar Reminder

Canvas Calendar Reminder will automatically synchronize Canvas assignments with Google Calendar and send a morning SMS reminder at 7:45 AM on days when assignments are due.

## Planned Technologies

- Python
- Canvas REST API
- Google Calendar API
- Twilio SMS
- python-dotenv

## Current Development Status

Phase 1: Project Foundation

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

Edit `.env` with your own values when later phases require them. Never commit secrets.

Run the project:

```bash
python main.py
```

Expected output:

```text
Canvas Calendar Reminder
Configuration loaded successfully.
Timezone: America/Phoenix
```

## Phase 1 Scope

This phase only creates the project foundation. It does not connect to Canvas, configure Google OAuth, create calendar events, send SMS messages, add scheduling, add a database, add a web server, or add a frontend.
