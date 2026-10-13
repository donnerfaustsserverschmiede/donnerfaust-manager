"""Basic isolation tests for per-guild settings."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.path_patch = patch.object(database, "DB_PATH", self.db_path)
        self.path_patch.start()
        database.initialize_database()

    def tearDown(self) -> None:
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_settings_are_isolated_per_guild(self) -> None:
        database.set_guild_setting(100, "log_channel_id", 501)
        database.set_guild_setting(200, "log_channel_id", 601)
        self.assertEqual(database.get_guild_setting(100, "log_channel_id"), 501)
        self.assertEqual(database.get_guild_setting(200, "log_channel_id"), 601)

    def test_setting_can_be_updated(self) -> None:
        database.set_guild_setting(100, "log_channel_id", 501)
        database.set_guild_setting(100, "log_channel_id", 502)
        self.assertEqual(database.get_guild_setting(100, "log_channel_id"), 502)


if __name__ == "__main__":
    unittest.main()
