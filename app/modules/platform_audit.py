"""Platform-level audit trail for bot guild joins and removals."""
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import discord
from discord.ext import commands

MASTER_USER_ID = "528084214357295114"
CENTRAL_LOG_GUILD_ID = 1512636539174129714
CENTRAL_LOG_CHANNEL_ID = 1561730344749633636
DB_PATH = Path(os.getenv("DASHBOARD_DB_PATH", "data/donnerfaust_manager.sqlite3"))


def record_event(event_type: str, guild_id: int, guild_name: str, actor_id: str = "", actor_name: str = "", details: str = "") -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            guild_name TEXT NOT NULL,
            actor_id TEXT NOT NULL DEFAULT '',
            actor_name TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute(
            "INSERT INTO platform_events(event_type,guild_id,guild_name,actor_id,actor_name,details) VALUES(?,?,?,?,?,?)",
            (event_type, str(guild_id), guild_name, actor_id, actor_name, details[:1500]),
        )


class PlatformAudit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _audit_actor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int) -> tuple[str, str]:
        try:
            async for entry in guild.audit_logs(limit=10, action=action):
                target = getattr(entry, "target", None)
                if getattr(target, "id", None) == target_id:
                    return str(entry.user.id), str(entry.user)
        except (discord.Forbidden, discord.HTTPException):
            pass
        return "", "Nicht ermittelbar"

    async def _send_central_log(self, title: str, description: str, color: discord.Color) -> None:
        channel = self.bot.get_channel(CENTRAL_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(CENTRAL_LOG_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if isinstance(channel, discord.TextChannel) and channel.guild.id == CENTRAL_LOG_GUILD_ID:
            embed = discord.Embed(title=title, description=description[:3500], color=color,
                                  timestamp=datetime.now(timezone.utc))
            try:
                await channel.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        actor_id, actor_name = await self._audit_actor(guild, discord.AuditLogAction.bot_add, self.bot.user.id if self.bot.user else 0)
        record_event("bot_added", guild.id, guild.name, actor_id, actor_name, "Bot wurde einem Discord-Server hinzugefügt.")
        await self._send_central_log("DF-Manager hinzugefügt", f"**Server:** {guild.name}", discord.Color.green())

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # Discord does not reliably expose the remover after the bot has left.
        record_event("bot_removed", guild.id, guild.name, "", "Nicht ermittelbar",
                     "Bot hat den Server verlassen oder wurde entfernt; Discord lieferte keinen zuverlässig prüfbaren Auslöser.")
        await self._send_central_log("DF-Manager hat Server verlassen", f"**Server:** {guild.name}", discord.Color.red())

async def setup(bot: commands.Bot):
    await bot.add_cog(PlatformAudit(bot))
