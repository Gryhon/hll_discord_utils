from discord.ext import commands
import discord
from discord import app_commands
from typing import Optional
import logging
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from .utils.name_utils import validate_t17_number, validate_clan_tag, validate_emojis, format_nickname
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed
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

            # Validate inputs
            is_valid, error_message = validate_t17_number(t17_number)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            is_valid, error_message = validate_clan_tag(clan_tag)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            is_valid, error_message = validate_emojis(emojis)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Get player name from database
            player_name = await get_player_name(self, interaction.user.id)
            if not player_name:
                await interaction.response.send_message(
                    "You are not registered. Please use /voter_registration first.",
                    ephemeral=True
                )
                return

            # Update nickname
            if player_name:
                formatted_name = format_nickname(player_name, t17_number, clan_tag, emojis)
                try:
                    await member.edit(nick=formatted_name)
                    
                    # Assign role if configured
                    error_msg = await handle_roles(member, 'name_changed')
                    
                    # Send success embed
                    await send_success_embed(
                        interaction.guild,
                        interaction.user,
                        'name_changed',
                        formatted_name
                    )
                    
                    if error_msg:
                        await interaction.response.send_message(
                            f"Nickname updated successfully, but note: {error_msg}",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "Successfully updated your nickname!",
                            ephemeral=True
                        )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "I don't have permission to change your nickname.",
                        ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Unexpected error in update_name: {e}")
            await interaction.response.send_message(
                "An error occurred while updating your nickname.",
                ephemeral=True
            )