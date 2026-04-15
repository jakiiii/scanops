import re


INTERNAL_UNIX_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(\/(?:home|tmp|var|srv|usr|opt|etc|proc|dev|media|mnt|run|root)(?:\/[^\s'\"<>:]+)+)"
)
INTERNAL_WINDOWS_DRIVE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/](?:[^\\/\s'\"<>|:]+[\\/])*[^\\/\s'\"<>|:]*)"
)
INTERNAL_WINDOWS_UNC_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:\\\\[A-Za-z0-9._$-]+\\[^\s'\"<>|:]+(?:\\[^\s'\"<>|:]+)*)"
)


def contains_internal_unix_path(value):
    if not value:
        return False
    return bool(INTERNAL_UNIX_PATH_PATTERN.search(str(value)))


def contains_internal_windows_path(value):
    if not value:
        return False
    value = str(value)
    return bool(
        INTERNAL_WINDOWS_DRIVE_PATH_PATTERN.search(value)
        or INTERNAL_WINDOWS_UNC_PATH_PATTERN.search(value)
    )


def sanitize_user_file_error_message(message, fallback="The uploaded file could not be processed."):
    if contains_internal_unix_path(message) or contains_internal_windows_path(message):
        return fallback
    return str(message)
