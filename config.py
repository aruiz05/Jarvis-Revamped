import os

from dotenv import load_dotenv


load_dotenv()

# canvas feed secret from local env
CANVAS_ICAL_URL = os.getenv("CANVAS_ICAL_URL", "")

# default local timezone
TIMEZONE = os.getenv("TIMEZONE", "America/Phoenix")
