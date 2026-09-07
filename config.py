import os

from dotenv import load_dotenv


load_dotenv()

CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL", "")
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER", "")

TIMEZONE = os.getenv("TIMEZONE", "America/Phoenix")
