"""Central settings loaded from environment variables."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    discord_token: str = os.getenv("DISCORD_TOKEN", "").strip()
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip()
    enable_members_intent: bool = _as_bool(os.getenv("ENABLE_MEMBERS_INTENT"))
    enable_message_content_intent: bool = _as_bool(
        os.getenv("ENABLE_MESSAGE_CONTENT_INTENT")
    )


settings = Settings()
