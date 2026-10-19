"""Configurable event logging, isolated from other features."""
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from app.core.database import get_guild_setting, set_guild_setting

log = logging.getLogger(__name__)


class LoggingModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def send_log(self, guild: discord.Guild, embed: discord.Embed, setting_key: str | None = None) -> None:
        if setting_key and get_guild_setting(guild.id, setting_key) is False:
            return
        channel_id = get_guild_setting(guild.id, "log_channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.warning("Logging channel %s is unavailable for guild %s", channel_id, guild.id)
                return
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild.id:
            log.warning("Configured logging channel %s is not a text channel in guild %s", channel_id, guild.id)
            return
        me = guild.me
        if me is None:
            log.warning("Could not resolve bot member in guild %s", guild.id)
            return
        permissions = channel.permissions_for(me)
        if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
            log.warning("Missing View Channel / Send Messages / Embed Links permission in logging channel %s (guild %s)", channel.id, guild.id)
            return
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Could not send a log message in channel %s (guild %s)", channel.id, guild.id)

    @staticmethod
    def make_embed(title: str, description: str, color: discord.Color) -> discord.Embed:
        return discord.Embed(title=title, description=description[:4000], color=color, timestamp=datetime.now(timezone.utc))

    @commands.command(name="setlogchannel")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the destination for this server's event logs."""
        if ctx.guild is None:
            return
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            await ctx.reply("Mir fehlen in diesem Kanal die Rechte Nachrichten senden und Links einbetten.")
            return
        set_guild_setting(ctx.guild.id, "log_channel_id", channel.id)
        # Selecting a logging channel enables the core logging events by default.
        # Administrators can turn individual events off later in the dashboard.
        for key in (
            "logging_message_delete",
            "logging_message_edit",
            "logging_member_join",
            "logging_member_leave",
            "logging_channel_events",
            "logging_role_events",
            "logging_voice_events",
        ):
            set_guild_setting(ctx.guild.id, key, True)
        await ctx.reply(f"Logging-Kanal wurde auf {channel.mention} gesetzt. Die Logging-Ereignisse sind standardmäßig aktiviert.")

    @commands.command(name="logstatus")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def log_status(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            return
        channel_id = get_guild_setting(ctx.guild.id, "log_channel_id")
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            await ctx.reply("Es ist noch kein gültiger Logging-Kanal eingerichtet. Nutze !setlogchannel #kanal.")
        else:
            await ctx.reply(f"Logging ist für diesen Server auf {channel.mention} eingestellt.")

    @commands.command(name="logtest")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def log_test(self, ctx: commands.Context) -> None:
        """Send a visible test entry to the configured logging channel."""
        if ctx.guild is None:
            return
        channel_id = get_guild_setting(ctx.guild.id, "log_channel_id")
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await ctx.reply("Kein gültiger Log-Kanal eingerichtet. Wähle ihn im Dashboard oder nutze !setlogchannel #kanal.")
            return
        me = ctx.guild.me
        if me is None:
            await ctx.reply("Ich kann meine Servermitgliedschaft gerade nicht prüfen. Bitte versuche es erneut.")
            return
        permissions = channel.permissions_for(me)
        if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
            await ctx.reply(f"Mir fehlen im {channel.mention} die Rechte „Kanal ansehen“, „Nachrichten senden“ oder „Links einbetten“.")
            return
        try:
            await channel.send(embed=self.make_embed("Logging-Test erfolgreich", f"Der Test wurde von {ctx.author} ausgelöst. Wenn du diesen Eintrag siehst, kann ich in diesem Kanal protokollieren.", discord.Color.green()))
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Logging test failed in channel %s (guild %s)", channel.id, ctx.guild.id)
            await ctx.reply("Discord hat den Testeintrag abgelehnt. Prüfe die Bot-Rechte im Log-Kanal.")
            return
        await ctx.reply(f"Testeintrag wurde in {channel.mention} gesendet.")

    @app_commands.command(name="logstatus", description="Zeigt den konfigurierten Logging-Kanal.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_log_status(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Dieser Befehl funktioniert nur auf einem Server.", ephemeral=True)
            return
        channel_id = get_guild_setting(guild.id, "log_channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(f"Logging-Kanal: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("Noch kein Logging-Kanal eingerichtet. Nutze /setlogchannel und wähle einen Kanal.", ephemeral=True)

    @app_commands.command(name="setlogchannel", description="Legt den Kanal für Bot-Logs fest.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Textkanal, in den Ereignisse protokolliert werden")
    async def slash_set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Dieser Befehl funktioniert nur auf einem Server.", ephemeral=True)
            return
        me = guild.me
        permissions = channel.permissions_for(me) if me else None
        if permissions is None or not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
            await interaction.response.send_message("Mir fehlen in diesem Kanal Rechte: Kanal ansehen, Nachrichten senden und Links einbetten.", ephemeral=True)
            return
        set_guild_setting(guild.id, "log_channel_id", channel.id)
        # Enable all event types when a server configures logging for the first time.
        for key in (
            "logging_message_delete",
            "logging_message_edit",
            "logging_member_join",
            "logging_member_leave",
            "logging_channel_events",
            "logging_role_events",
            "logging_voice_events",
        ):
            set_guild_setting(guild.id, key, True)
        await interaction.response.send_message(
            f"Logging-Kanal wurde auf {channel.mention} gesetzt. Die Logging-Ereignisse sind standardmäßig aktiviert.",
            ephemeral=True,
        )

    @app_commands.command(name="logtest", description="Sendet eine Testmeldung in den Logging-Kanal.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_log_test(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Dieser Befehl funktioniert nur auf einem Server.", ephemeral=True)
            return
        channel_id = get_guild_setting(guild.id, "log_channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Kein Logging-Kanal eingerichtet. Nutze zuerst /setlogchannel.", ephemeral=True)
            return
        me = guild.me
        permissions = channel.permissions_for(me) if me else None
        if permissions is None or not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
            await interaction.response.send_message(f"Mir fehlen Rechte im {channel.mention}: Kanal ansehen, Nachrichten senden oder Links einbetten.", ephemeral=True)
            return
        try:
            await channel.send(embed=self.make_embed("Logging-Test erfolgreich", f"Der Test wurde von {interaction.user} ausgelöst. Das Logging kann in diesem Kanal schreiben.", discord.Color.green()))
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Slash logging test failed in channel %s (guild %s)", channel.id, guild.id)
            await interaction.response.send_message("Discord hat die Testmeldung abgelehnt. Bitte prüfe die Bot-Rechte im Logging-Kanal.", ephemeral=True)
            return
        await interaction.response.send_message(f"Testmeldung wurde in {channel.mention} gesendet.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        content = message.content.strip() or "[Kein Text verfügbar – möglicherweise fehlen Message Content Intents oder es war nur ein Anhang.]"
        embed = self.make_embed("Nachricht gelöscht", f"**Autor:** {message.author} ({message.author.id})\n**Kanal:** {message.channel}\n**Inhalt:**\n{content[:2500]}", discord.Color.red())
        await self.send_log(message.guild, embed, "logging_message_delete")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        if not messages or messages[0].guild is None:
            return
        guild = messages[0].guild
        embed = self.make_embed("Mehrere Nachrichten gelöscht", f"Discord hat {len(messages)} Nachrichten in einem Kanal auf einmal gelöscht. Der Inhalt wird hier nicht einzeln protokolliert.", discord.Color.dark_red())
        await self.send_log(guild, embed, "logging_message_delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot or before.content == after.content:
            return
        embed = self.make_embed("Nachricht bearbeitet", f"**Autor:** {before.author} ({before.author.id})\n**Kanal:** {before.channel}\n**Vorher:**\n{before.content[:1200] or '[leer]'}\n\n**Nachher:**\n{after.content[:1200] or '[leer]'}", discord.Color.orange())
        await self.send_log(before.guild, embed, "logging_message_edit")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.send_log(member.guild, self.make_embed("Mitglied beigetreten", f"{member} ({member.id}) ist dem Server beigetreten.", discord.Color.green()), "logging_member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.send_log(member.guild, self.make_embed("Mitglied verlassen", f"{member} ({member.id}) hat den Server verlassen oder wurde entfernt. Discord liefert für dieses Ereignis nicht zuverlässig den Grund.", discord.Color.dark_grey()), "logging_member_leave")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self.send_log(channel.guild, self.make_embed("Kanal erstellt", f"Kanal: {channel.name} ({channel.id})", discord.Color.green()), "logging_channel_events")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.send_log(channel.guild, self.make_embed("Kanal gelöscht", f"Kanal: {channel.name} ({channel.id})", discord.Color.red()), "logging_channel_events")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if getattr(before, "category_id", None) != getattr(after, "category_id", None):
            old_category = before.category.name if getattr(before, "category", None) else "Keine Kategorie"
            new_category = after.category.name if getattr(after, "category", None) else "Keine Kategorie"
            changes.append(f"**Kategorie:** {old_category} → {new_category}")
        if changes:
            embed = self.make_embed("Kanal geändert", f"**Kanal:** {after.name} ({after.id})\\n" + "\\n".join(changes), discord.Color.orange())
            await self.send_log(after.guild, embed, "logging_channel_events")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self.send_log(role.guild, self.make_embed("Rolle erstellt", f"Rolle: {role.name} ({role.id})", discord.Color.green()), "logging_role_events")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.send_log(role.guild, self.make_embed("Rolle gelöscht", f"Rolle: {role.name} ({role.id})", discord.Color.red()), "logging_role_events")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.permissions != after.permissions:
            changes.append("**Berechtigungen:** geändert")
        if before.color != after.color:
            changes.append("**Rollenfarbe:** geändert")
        if before.hoist != after.hoist:
            changes.append("**Separat anzeigen:** geändert")
        if before.mentionable != after.mentionable:
            changes.append("**Erwähnbar:** geändert")
        if changes:
            embed = self.make_embed("Rolle geändert", f"**Rolle:** {after.name} ({after.id})\\n" + "\\n".join(changes), discord.Color.orange())
            await self.send_log(after.guild, embed, "logging_role_events")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"**Servername:** {before.name} → {after.name}")
        if before.description != after.description:
            changes.append("**Serverbeschreibung:** geändert")
        if before.icon != after.icon:
            changes.append("**Serverbild:** geändert")
        if changes:
            embed = self.make_embed("Server geändert", "\\n".join(changes), discord.Color.orange())
            await self.send_log(after, embed, "logging_channel_events")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if before.channel == after.channel:
            return
        if before.channel is None and after.channel is not None:
            action = f"ist dem Sprachkanal {after.channel.name} beigetreten"
        elif before.channel is not None and after.channel is None:
            action = f"hat den Sprachkanal {before.channel.name} verlassen"
        else:
            action = f"wechselte von {before.channel.name} zu {after.channel.name}"
        await self.send_log(member.guild, self.make_embed("Sprachkanal-Aktivität", f"{member} {action}.", discord.Color.blurple()), "logging_voice_events")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingModule(bot))
