import discord
import logging
from typing import Optional
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from rcon.config import config
from rcon.discord.registration_namechange.utils.search_vote_reg import get_registration_details, format_registration_info

logger = logging.getLogger(__name__)

class Unregister(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(
        name="unregister_user",
        description="Remove a user's T17 registration (Admin only)"
    )
    @app_commands.describe(
        user="The Discord user to unregister"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def unregister_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        try:
            # Check if user is registered
            result = self.select_T17_Voter_Registration(user.id)
            if result is None:
                await interaction.response.send_message(
                    f"User {user.name} is not registered.",
                    ephemeral=True
                )
                return

            player_id = result[0]  # Get T17 ID from tuple

            # Remove from database using DiscordBase method
            if self.delete_T17_Voter_Registration(user.id):
                logger.info(f"User {user.name} (ID: {user.id}) was unregistered by {interaction.user.name}")
                await interaction.response.send_message(
                    f"Successfully unregistered {user.name}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Failed to unregister user due to a database error.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in unregister_user: {e}")
            await interaction.response.send_message(
                "An error occurred while trying to unregister the user.",
                ephemeral=True
            )

    @app_commands.command(
        name="check_registration",
        description="Check if a user is registered"
    )
    @app_commands.describe(
        user="The Discord user to check"
    )
    async def check_registration(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Check if a user is registered and display their registration details."""
        try:
            target_user = user or interaction.user
            logger.info(f"Checking registration for user {target_user.name} (ID: {target_user.id})")
            
            result, error = await get_registration_details(self, target_user.id)
            if error:
                await interaction.response.send_message(
                    f"User {target_user.name} is not registered." if "not registered" in error else error,
                    ephemeral=True
                )
                return
                
            info = await format_registration_info(target_user.name, result)
            await interaction.response.send_message(info, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in check_registration: {e}")
            await interaction.response.send_message(
                "An error occurred while checking registration status.",
                ephemeral=True
            )

    @app_commands.command(name="unregister", description="Remove your T17 account registration")
    async def unregister(self, interaction: discord.Interaction):
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

            # Check if user is registered
            result = self.select_T17_Voter_Registration(interaction.user.id)
            if result is None:
                await interaction.response.send_message("You are not registered.", ephemeral=True)
                return

            # Delete registration
            success = self.delete_T17_Voter_Registration(interaction.user.id)
            
            if success:
                # Reset nickname if possible
                try:
                    await member.edit(nick=None)
                except discord.Forbidden:
                    pass  # Ignore if we can't change nickname
                    
                logger.info(f"User {interaction.user.name} (ID: {interaction.user.id}) was unregistered by {interaction.user.name}")
                await interaction.response.send_message("Successfully unregistered your T17 account.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while unregistering.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in unregister: {e}")
            await interaction.response.send_message("An error occurred while unregistering.", ephemeral=True) 