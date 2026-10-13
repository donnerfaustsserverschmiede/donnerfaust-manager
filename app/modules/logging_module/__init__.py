"""Logging feature module.

Future logging listeners and per-guild destination settings belong here.
Keep this feature self-contained; do not edit ticket or moderation modules.
"""
from discord.ext import commands


class LoggingModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingModule(bot))
