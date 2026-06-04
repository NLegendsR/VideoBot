import logging
from datetime import datetime

from config import USERS_LOG_FILE

logger = logging.getLogger(__name__)


def log_download(user: object, url: str) -> None:
    """Append one line to the log file for every successful download."""
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id   = getattr(user, "id",         "?")
    username  = f"@{user.username}" if getattr(user, "username", None) else "—"
    first     = getattr(user, "first_name", "")
    last      = getattr(user, "last_name",  "")
    full_name = " ".join(filter(None, [first, last])) or "—"

    line = (
        f"[{ts}]  "
        f"ID: {user_id:<12}  "
        f"Username: {username:<20}  "
        f"Name: {full_name:<25}  "
        f"URL: {url}\n"
    )

    try:
        with open(USERS_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        logger.warning("Could not write to %s: %s", USERS_LOG_FILE, exc)
