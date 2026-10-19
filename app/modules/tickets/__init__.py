"""Ticket module: create a panel and private staff/user ticket channels."""
import re
import discord
from discord import app_commands
from discord.ext import commands

from app.core.database import get_guild_setting

SUPPORT_ROLE_NAME = "Support"
TICKET_CATEGORY_NAME = "Tickets"


def safe_channel_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return (slug or "user")[:18]


class CloseTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="dfm:ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.name.startswith("ticket-"):
            await interaction.response.send_message("Das ist kein DF-Manager-Ticketkanal.", ephemeral=True)
            return
        is_owner = channel.topic and f"owner_id={interaction.user.id}" in channel.topic
        staff_role = discord.utils.get(interaction.guild.roles, name=SUPPORT_ROLE_NAME) if interaction.guild else None
        is_staff = bool(staff_role and staff_role in getattr(interaction.user, "roles", []))
        if not (is_owner or is_staff or interaction.user.guild_permissions.manage_channels):
            await interaction.response.send_message("Nur der Ticket-Ersteller oder das Support-Team kann dieses Ticket schließen.", ephemeral=True)
            return
        await interaction.response.send_message("Ticket wird in 3 Sekunden geschlossen …", ephemeral=True)
        await channel.delete(reason=f"Ticket geschlossen von {interaction.user} ({interaction.user.id})")


class TicketsModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Sendet eine Nachricht, über die Mitglieder ein Support-Ticket öffnen können.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticketpanel(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Dieser Befehl funktioniert nur in einem Server-Textkanal.", ephemeral=True)
            return
        target_id = get_guild_setting(interaction.guild.id, "ticket_panel_channel_id")
        target = interaction.guild.get_channel(int(target_id)) if target_id else interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("Der konfigurierte Ticket-Panel-Kanal ist nicht verfügbar. Prüfe die Einstellungen im Dashboard.", ephemeral=True)
            return
        permissions = target.permissions_for(interaction.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            await interaction.response.send_message("Im Zielkanal fehlen mir die Rechte Nachrichten senden und Links einbetten.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎫 Donnerfaust Support",
            description="Du brauchst Hilfe? Klicke auf **Ticket erstellen**, um einen privaten Kanal mit dem Support-Team zu öffnen.",
            color=discord.Color.gold(),
        )
        await target.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(f"Ticket-Panel wurde in {target.mention} erstellt.", ephemeral=True)

    @app_commands.command(name="ticket", description="Öffnet ein privates Support-Ticket.")
    async def ticket(self, interaction: discord.Interaction) -> None:
        await create_ticket(interaction)


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket erstellen", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="dfm:ticket:create")
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await create_ticket(interaction)


async def create_ticket(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Tickets können nur auf einem Server erstellt werden.", ephemeral=True)
        return
    existing = discord.utils.find(
        lambda c: isinstance(c, discord.TextChannel) and c.topic and f"owner_id={interaction.user.id}" in c.topic and c.name.startswith("ticket-"),
        guild.text_channels,
    )
    if existing:
        await interaction.response.send_message(f"Du hast bereits ein offenes Ticket: {existing.mention}", ephemeral=True)
        return
    category_id = get_guild_setting(guild.id, "ticket_category_id")
    category = guild.get_channel(int(category_id)) if category_id else discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if category is not None and not isinstance(category, discord.CategoryChannel):
        category = None
    if category is None:
        try:
            category = await guild.create_category(TICKET_CATEGORY_NAME, reason="DF-Manager Ticket-System")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Ich kann die Ticket-Kategorie nicht verwenden oder erstellen. Prüfe meine Rechte und die Dashboard-Einstellungen.", ephemeral=True)
            return
    support_role_id = get_guild_setting(guild.id, "ticket_support_role_id")
    support_role = guild.get_role(int(support_role_id)) if support_role_id else discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, embed_links=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
    try:
        channel = await guild.create_text_channel(
            f"ticket-{safe_channel_name(interaction.user.name)}",
            category=category,
            overwrites=overwrites,
            topic=f"DF-Manager ticket; owner_id={interaction.user.id}",
            reason=f"Support-Ticket von {interaction.user} ({interaction.user.id})",
        )
    except discord.Forbidden:
        await interaction.response.send_message("Mir fehlen Rechte zum Erstellen eines privaten Ticketkanals. Bitte prüfe Kanal verwalten und Kanal ansehen.", ephemeral=True)
        return
    except discord.HTTPException:
        await interaction.response.send_message("Discord konnte den Ticketkanal gerade nicht erstellen. Bitte versuche es erneut.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎫 Support-Ticket",
        description=f"{get_guild_setting(guild.id, 'ticket_welcome_message') or f'Hallo {interaction.user.mention}! Beschreibe dein Anliegen bitte möglichst genau.'}\n\nDas Support-Team sieht diesen privaten Kanal. Nutze die Schaltfläche unten, wenn dein Anliegen erledigt ist.",
        color=discord.Color.blurple(),
    )
    try:
        await channel.send(content=f"{interaction.user.mention}" + (f" {support_role.mention}" if support_role else ""), embed=embed, view=CloseTicketView())
    except (discord.Forbidden, discord.HTTPException):
        try:
            await channel.delete(reason="Ticket-Erstellung fehlgeschlagen")
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.response.send_message("Der Ticketkanal wurde erstellt, aber ich konnte die Begrüßung nicht senden. Prüfe meine Kanalrechte.", ephemeral=True)
        return
    await interaction.response.send_message(f"Dein privates Ticket wurde erstellt: {channel.mention}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())
    await bot.add_cog(TicketsModule(bot))
