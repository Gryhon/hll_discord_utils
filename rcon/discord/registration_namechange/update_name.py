from discord.ext import commands
import discord
from discord import app_commands
from typing import Optional
import logging
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from .utils.name_utils import validate_t17_number, validate_clan_tag, format_nickname, update_user_nickname
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed, handle_name_update_response
from .utils.search_vote_reg import get_player_name, update_registration

logger = logging.getLogger(__name__)

class UpdateName(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(
        name="update_name",
        description="Update your Discord nickname and registration settings"
    )
    @app_commands.describe(
        t17_number="Your 4-digit T17 number",
        clan_tag="Your clan tag (optional)",
        vote_reminders="Enable/disable vote reminders (optional)"
    )
    async def update_name(
        self, 
        interaction: discord.Interaction,
        t17_number: Optional[str] = None,
        clan_tag: Optional[str] = None,
        vote_reminders: Optional[bool] = None
    ):
        try:
            # Check if feature is enabled
            if not config.get("rcon", 0, "name_change_registration", "enabled", default=True):
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

            # Get the existing player name from the database
            player_name = await get_player_name(result[0])  # Use the stored T17 ID to get the actual player name
            if not player_name:
                await interaction.response.send_message(
                    "Could not retrieve your player name. Please contact an administrator.",
                    ephemeral=True
                )
                return

            # Update nickname with components
            success, formatted_name, error_message = await update_user_nickname(
                self,
                member,
                player_name,  # Use the actual player name, not the T17 ID
                t17_number,
                clan_tag,
                result[3]  # Keep existing emojis
            )

            if not success:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Update registration with new components
            success, message = await update_registration(
                self,
                interaction.user.name,
                interaction.user.id,
                formatted_name,
                result[0],  # Keep existing T17 ID
                vote_reminders if vote_reminders is not None else bool(result[4]),
                clan_tag,
                t17_number,
                result[3]  # Keep existing emojis
            )

            # Send single response with complete status
            await interaction.response.send_message(
                f"Nickname updated to: {formatted_name}\n{message}",
                ephemeral=True
            )

        except discord.errors.InteractionResponded:
            # If we somehow already responded, log it but don't try to respond again
            logger.warning("Interaction was already responded to")
        except Exception as e:
            logger.error(f"Error in update_name: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while updating your nickname.",
                    ephemeral=True
                )