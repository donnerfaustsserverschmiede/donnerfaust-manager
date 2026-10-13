"""Small shared SQLite layer for per-server bot settings.

This is isolated so the storage backend can later be replaced without rewriting feature modules.
"""
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/donnerfaust_manager.sqlite3")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with _connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS guild_settings (guild_id INTEGER PRIMARY KEY, log_channel_id INTEGER)")


def get_guild_setting(guild_id: int, key: str) -> Any:
    if key != "log_channel_id":
        raise ValueError(f"Unsupported guild setting: {key}")
    initialize_database()
    with _connect() as connection:
        row = connection.execute("SELECT log_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)).fetchone()
    return row["log_channel_id"] if row else None


def set_guild_setting(guild_id: int, key: str, value: Any) -> None:
    if key != "log_channel_id":
        raise ValueError(f"Unsupported guild setting: {key}")
    initialize_database()
    with _connect() as connection:
        connection.execute("INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id", (guild_id, value))
