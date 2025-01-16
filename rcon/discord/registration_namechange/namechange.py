import discord
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import query_player_database, register_user, get_player_name, handle_autocomplete
from lib.config import config
from .utils.name_utils import validate_t17_number, format_nickname, validate_clan_tag, validate_emojis, update_user_nickname
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed, handle_name_update_response

# get Logger for this module
logger = logging.getLogger(__name__)

class NameChange(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False
        self.t17_required = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False)
        self.t17_show = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "show", default=True)
        self.enabled = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "enabled", default=True)

    @app_commands.command(name="namechange", description="Update your Discord nickname to match your T17 account")
    @app_commands.describe(
        ingame_name="Choose your in game user",
        t17_number="Your 4-digit T17 number",
        clan_tag="Your clan tag (optional)",
        emojis="Your emojis (optional, max 3)"
    )
    async def namechange(
        self, 
        interaction: discord.Interaction, 
        ingame_name: str,
        t17_number: Optional[str] = None,
        clan_tag: Optional[str] = None,
        emojis: Optional[str] = None
    ):
        try:
            # Check if feature is enabled
            if not config.get("comfort_functions", 0, "name_change_registration", "enabled", default=True):
                await interaction.response.send_message("This feature is not enabled.", ephemeral=True)
                return

            # Get member
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("Could not find your Discord account.", ephemeral=True)
                return

            success, formatted_name, error_message = await update_user_nickname(
                self,
                member,
                ingame_name,
                t17_number,
                clan_tag,
                emojis
            )
            
            if not success:
                await interaction.response.send_message(error_message, ephemeral=True)
                return
                
            # Handle role assignment
            role_error = await handle_roles(member, 'name_changed')
            
            # Handle response messages
            await handle_name_update_response(
                interaction,
                member,
                formatted_name,
                {
                    'clan_tag': clan_tag,
                    't17_number': t17_number,
                    'emojis': emojis
                },
                role_error
            )

        except Exception as e:
            logger.error(f"Unexpected error in namechange: {e}")
            await interaction.response.send_message(
                "An error occurred while updating your nickname.",
                ephemeral=True
            )

    @namechange.autocomplete("ingame_name")
    async def namechange_autocomplete(self, interaction: discord.Interaction, player_name: str) -> List[app_commands.Choice[str]]:
        return await handle_autocomplete(interaction, player_name, self.in_Loop) 