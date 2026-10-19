"""Automatic role assignment for new members, configured per server."""
import logging

import discord
from discord.ext import commands

from app.core.database import get_guild_setting

log = logging.getLogger(__name__)


class AutoRoleModule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        enabled = get_guild_setting(member.guild.id, "autorole_enabled")
        role_id = get_guild_setting(member.guild.id, "autorole_role_id")
        if enabled is not True or not role_id:
            return
        role = member.guild.get_role(int(role_id))
        if role is None or role.is_default or role.managed:
            log.warning("Autorole configuration invalid for guild %s", member.guild.id)
            return
        me = member.guild.me
        if me is None or not me.guild_permissions.manage_roles or role >= me.top_role:
            log.warning("Bot cannot assign configured autorole in guild %s", member.guild.id)
            return
        try:
            await member.add_roles(role, reason="DF-Manager Autorole")
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Failed to assign autorole in guild %s", member.guild.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRoleModule(bot))
