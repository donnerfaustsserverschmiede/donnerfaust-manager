"""Ticket feature module.

Ticket panels, categories, transcripts, staff routing and ticket permissions
belong in this package. Store configuration per Discord server (guild).
"""
from discord.ext import commands


class TicketsModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsModule(bot))
