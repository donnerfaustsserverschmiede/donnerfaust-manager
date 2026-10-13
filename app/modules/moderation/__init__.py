"""Moderation feature module.

Warnings, timeouts, kicks, bans and anti-spam protections belong here.
"""
from discord.ext import commands


class ModerationModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationModule(bot))
