"""Shared SQLite settings store for bot and dashboard.

SQLite is suitable for local development and a single-process starter deployment.
For multi-instance hosting, move to PostgreSQL before scaling out.
"""
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("DASHBOARD_DB_PATH", "data/donnerfaust_manager.sqlite3"))
ALLOWED_SETTINGS = {
    "log_channel_id",
    "logging_message_create",
    "logging_message_delete",
    "logging_message_edit",
    "logging_member_join",
    "logging_member_leave",
    "logging_channel_events",
    "logging_role_events",
    "logging_voice_events",
    "logging_member_events",
    "logging_moderation_events",
    "logging_server_events",
    "ticket_category_id",
    "ticket_support_role_id",
    "ticket_panel_channel_id",
    "ticket_welcome_message",
    "moderation_log_channel_id",
    "moderation_timeout_enabled",
    "moderation_kick_enabled",
    "moderation_ban_enabled",
    "moderation_clear_enabled",
    "antispam_enabled",
    "autorole_enabled",
    "autorole_role_id",
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, setting_key)
            )"""
        )


def get_guild_setting(guild_id: int, key: str) -> Any:
    if key not in ALLOWED_SETTINGS:
        raise ValueError(f"Unsupported guild setting: {key}")
    initialize_database()
    if key == "log_channel_id":
        with _connect() as connection:
            row = connection.execute(
                "SELECT log_channel_id FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        if row and row["log_channel_id"] is not None:
            return row["log_channel_id"]
    with _connect() as connection:
        row = connection.execute(
            "SELECT setting_value FROM guild_config WHERE guild_id = ? AND setting_key = ?",
            (guild_id, key),
        ).fetchone()
    if not row:
        return None
    value = row["setting_value"]
    if key.endswith("_id") and value:
        try:
            return int(value)
        except ValueError:
            return None
    if value in {"true", "false"}:
        return value == "true"
    return value


def set_guild_setting(guild_id: int, key: str, value: Any) -> None:
    if key not in ALLOWED_SETTINGS:
        raise ValueError(f"Unsupported guild setting: {key}")
    initialize_database()
    if key == "log_channel_id":
        with _connect() as connection:
            connection.execute(
                """INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id""",
                (guild_id, value),
            )
    normalized = "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    with _connect() as connection:
        connection.execute(
            """INSERT INTO guild_config (guild_id, setting_key, setting_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, setting_key) DO UPDATE SET
            setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP""",
            (guild_id, key, normalized),
        )


def get_guild_config(guild_id: int) -> dict[str, Any]:
    initialize_database()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT setting_key, setting_value FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
    config: dict[str, Any] = {}
    for row in rows:
        key, value = row["setting_key"], row["setting_value"]
        if key.endswith("_id") and value:
            try:
                config[key] = int(value)
                continue
            except ValueError:
                pass
        config[key] = value == "true" if value in {"true", "false"} else value
    legacy = get_guild_setting(guild_id, "log_channel_id")
    if legacy is not None:
        config["log_channel_id"] = legacy
    return config
