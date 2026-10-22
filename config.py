"""Environment-backed configuration. Never put live credentials in source control."""
import os
from dotenv import load_dotenv

load_dotenv()

def _int_env(name: str, default: int = 0) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc

# Telegram API credentials (obtain from https://my.telegram.org)
API_ID = _int_env("API_ID")
API_HASH = os.getenv("API_HASH", "").strip()

# Bot token / optional user session
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
STRING1 = os.getenv("STRING_SESSION") or None

# Database. Intentionally no fallback URI or embedded credentials.
MONGO_URL = os.getenv("MONGO_URL", "").strip()

# Owner / admin
OWNER_ID = _int_env("OWNER_ID")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "").strip()

# Support / updates
SUPPORT_GRP = os.getenv("SUPPORT_GRP", "ShrutiBotSupport").strip()
UPDATE_CHNL = os.getenv("UPDATE_CHNL", "ShrutiBots").strip()
