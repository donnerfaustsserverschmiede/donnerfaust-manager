"""Moderation commands for the Donnerfaust Manager."""
import discord
from discord import app_commands
from discord.ext import commands

from app.core.database import get_guild_setting


class ModerationModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="timeout", description="Schaltet ein Mitglied für eine bestimmte Zeit stumm.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minuten: app_commands.Range[int, 1, 40320], grund: str = "Kein Grund angegeben") -> None:
        if interaction.guild and get_guild_setting(interaction.guild.id, "moderation_timeout_enabled") is False:
            await interaction.response.send_message("Diese Moderationsfunktion ist im Dashboard deaktiviert.", ephemeral=True)
            return
        if interaction.guild and member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("Ich kann dieses Mitglied wegen der Rollen-Hierarchie nicht timeouten.", ephemeral=True)
            return
        try:
            await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=minuten), reason=f"{interaction.user}: {grund}")
        except AttributeError:
            from datetime import timedelta
            try:
                await member.timeout(discord.utils.utcnow() + timedelta(minutes=minuten), reason=f"{interaction.user}: {grund}")
            except discord.Forbidden:
                await interaction.response.send_message("Mir fehlt die Berechtigung oder meine Rolle ist zu niedrig.", ephemeral=True)
                return
        except discord.Forbidden:
            await interaction.response.send_message("Mir fehlt die Berechtigung oder meine Rolle ist zu niedrig.", ephemeral=True)
            return
        await interaction.response.send_message(f"{member.mention} wurde für {minuten} Minute(n) timeoutet. Grund: {grund}")

    @app_commands.command(name="kick", description="Entfernt ein Mitglied vom Server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, grund: str = "Kein Grund angegeben") -> None:
        if interaction.guild and get_guild_setting(interaction.guild.id, "moderation_kick_enabled") is False:
            await interaction.response.send_message("Diese Moderationsfunktion ist im Dashboard deaktiviert.", ephemeral=True)
            return
        if interaction.guild and member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("Ich kann dieses Mitglied wegen der Rollen-Hierarchie nicht kicken.", ephemeral=True)
            return
        try:
            await member.kick(reason=f"{interaction.user}: {grund}")
        except discord.Forbidden:
            await interaction.response.send_message("Mir fehlt die Berechtigung oder meine Rolle ist zu niedrig.", ephemeral=True)
            return
        await interaction.response.send_message(f"{member} wurde gekickt. Grund: {grund}")

    @app_commands.command(name="ban", description="Bannt ein Mitglied vom Server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, grund: str = "Kein Grund angegeben") -> None:
        if interaction.guild and get_guild_setting(interaction.guild.id, "moderation_ban_enabled") is False:
            await interaction.response.send_message("Diese Moderationsfunktion ist im Dashboard deaktiviert.", ephemeral=True)
            return
        if interaction.guild and member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("Ich kann dieses Mitglied wegen der Rollen-Hierarchie nicht bannen.", ephemeral=True)
            return
        try:
            await member.ban(reason=f"{interaction.user}: {grund}", delete_message_seconds=0)
        except discord.Forbidden:
            await interaction.response.send_message("Mir fehlt die Berechtigung oder meine Rolle ist zu niedrig.", ephemeral=True)
            return
        await interaction.response.send_message(f"{member} wurde gebannt. Grund: {grund}")

    @app_commands.command(name="clear", description="Löscht bis zu 100 Nachrichten im aktuellen Kanal.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, anzahl: app_commands.Range[int, 1, 100]) -> None:
        if interaction.guild and get_guild_setting(interaction.guild.id, "moderation_clear_enabled") is False:
            await interaction.response.send_message("Diese Moderationsfunktion ist im Dashboard deaktiviert.", ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Dieser Befehl funktioniert nur in Textkanälen.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await channel.purge(limit=anzahl, reason=f"Clear durch {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("Mir fehlt die Berechtigung zum Löschen von Nachrichten.", ephemeral=True)
            return
        await interaction.followup.send(f"{len(deleted)} Nachricht(en) gelöscht.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationModule(bot))
