import os

from dotenv import load_dotenv


load_dotenv()

# canvas feed secret from local env
CANVAS_ICAL_URL = os.getenv("CANVAS_ICAL_URL", "")

# saved for later sms work
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER", "")

# default local timezone
TIMEZONE = os.getenv("TIMEZONE", "America/Phoenix")
