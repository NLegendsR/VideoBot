import os

# ── Bot ───────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID:  int = 1_080_582_144

# ── File sizes ────────────────────────────────────────────────────────────────
# Telegram Bot API hard limit for file uploads (standard API)
TELEGRAM_UPLOAD_LIMIT: int = 50 * 1024 * 1024    # 50 MB

# Regular users: small cap so we never waste disk/time on huge files
USER_MAX_DOWNLOAD: int = 50 * 1024 * 1024         # 50 MB

# Admin: download large high-quality files.
# NOTE: Telegram will still refuse uploads > 50 MB unless you run a
# local Bot API server (see README.md for instructions).
ADMIN_MAX_DOWNLOAD: int = 500 * 1024 * 1024       # 500 MB

# ── Logging ───────────────────────────────────────────────────────────────────
USERS_LOG_FILE: str = os.getenv("USERS_LOG_FILE", "users_log.txt")
