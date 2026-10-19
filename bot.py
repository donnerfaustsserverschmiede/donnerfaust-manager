"""Entry point for Donnerfaust Manager."""
import asyncio
import logging

import discord
from discord.ext import commands

from app.core.settings import settings
from app.core.extensions import EXTENSIONS

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("donnerfaust_manager")


class DonnerfaustBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # Enable privileged intents only after enabling them in the Discord
        # Developer Portal and confirming the bot's intended use.
        # These intents are enabled in the Discord Developer Portal for this bot.
        # Enable them explicitly here so prefix commands and member event logging work
        # without requiring extra hosting environment variables.
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents)

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                log.info("Loaded extension: %s", extension)
            except Exception:
                log.exception("Could not load extension %s; continuing.", extension)

        # Register slash commands with Discord so /ticket, /ticketpanel,
        # /timeout, /kick, /ban and /clear appear in servers.
        try:
            synced = await self.tree.sync()
            log.info("Synced %d global application command(s)", len(synced))
        except Exception:
            log.exception("Could not sync application commands.")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("Du brauchst die Berechtigung „Server verwalten“, um diesen Befehl zu nutzen.", mention_author=False)
            return
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.reply("Dieser Befehl funktioniert nur auf einem Server.", mention_author=False)
            return
        log.exception("Command failed: %s", getattr(ctx.command, "qualified_name", "unknown"), exc_info=error)
        try:
            await ctx.reply("Der Befehl ist auf einen Fehler gelaufen. Der Fehler wurde protokolliert.", mention_author=False)
        except discord.HTTPException:
            pass

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "?")
        log.info("Connected to %d guild(s)", len(self.guilds))


async def main() -> None:
    if not settings.discord_token:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token."
        )
    bot = DonnerfaustBot()
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
