from discord.ext import commands
import discord
from discord import app_commands
from typing import Optional
import logging
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from .utils.name_utils import validate_t17_number, validate_clan_tag, validate_emojis, format_nickname, update_user_nickname
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed, handle_name_update_response
from .utils.search_vote_reg import get_player_name

logger = logging.getLogger(__name__)

class UpdateName(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(
        name="update_name",
        description="Update your Discord nickname to your latest in-game name"
    )
    @app_commands.describe(
        t17_number="Your 4-digit T17 number",
        clan_tag="Your clan tag (optional)",
        emojis="Your emojis (optional, max 3)"
    )
    async def update_name(
        self, 
        interaction: discord.Interaction,
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

            # Get player name and components from database
            result = self.select_T17_Voter_Registration(interaction.user.id)
            if not result:
                await interaction.response.send_message(
                    "You are not registered. Please use /voter_registration first.",
                    ephemeral=True
                )
                return
                
            player_name, stored_clan_tag, stored_t17_number, stored_emojis = result
            
            # Use stored values if not provided in command
            t17_number = t17_number or stored_t17_number
            clan_tag = clan_tag or stored_clan_tag
            emojis = emojis or stored_emojis

            success, formatted_name, error_message = await update_user_nickname(
                self,
                member,
                player_name,
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
            logger.error(f"Unexpected error in update_name: {e}")
            await interaction.response.send_message(
                "An error occurred while updating your nickname.",
                ephemeral=True
            )