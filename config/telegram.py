from . import c

_SECTION = 'telegram'

API_ID = c.getint(_SECTION, "api_id")
API_HASH = c.get(_SECTION, "api_hash")
SESSION_NAME = c.get(_SECTION, "session_name")
INTERVAL = c.getint(_SECTION, "interval")
PHONE_NUMBER = c.get(_SECTION, "phone_number")
PASSWORD = c.get(_SECTION, "password")

UB_ARGS = [API_ID, API_HASH, SESSION_NAME, INTERVAL, PHONE_NUMBER, PASSWORD]
