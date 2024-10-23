from . import c


_SECTION = "vk"

TOKEN = c.get(_SECTION, "token")
RETRY_SECONDS = c.getint(_SECTION, "retry_seconds")
JSON_DECODE_RS = c.getint(_SECTION, "json_decode_retry_seconds")
UPLOAD_FAIL_RS = c.getint(_SECTION, "upload_fail_retry_seconds")
PACK_FAIL_RS = c.getint(_SECTION, "pack_fail_retry_seconds")
ACCESS_DENIED_RS = c.getint(_SECTION, "access_denied_retry_seconds")
ANTI_FLOOD_RS = c.getint(_SECTION, "anti_flood_retry_seconds")
PHOTO_UPLOAD_MAX_TRIES = c.getint(_SECTION, "photo_upload_max_tries")
PACK_UPLOAD_MAX_TRIES = c.getint(_SECTION, "pack_upload_max_tries")

ALBUM_ARGS = [
    TOKEN,
    RETRY_SECONDS,
    JSON_DECODE_RS,
    UPLOAD_FAIL_RS,
    PACK_FAIL_RS,
    ACCESS_DENIED_RS,
    ANTI_FLOOD_RS,
    PHOTO_UPLOAD_MAX_TRIES,
    PACK_UPLOAD_MAX_TRIES,
]
