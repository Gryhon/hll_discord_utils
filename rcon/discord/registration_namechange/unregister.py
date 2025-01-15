import discord
import logging
from typing import Optional
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase

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
            player_id = self.select_T17_Voter_Registration(user.id)
            if player_id is None:
                await interaction.response.send_message(
                    f"User {user.name} is not registered.",
                    ephemeral=True
                )
                return

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
        try:
            target_user = user or interaction.user
            player_id = self.select_T17_Voter_Registration(target_user.id)
            
            if player_id:
                await interaction.response.send_message(
                    f"User {target_user.name} is registered with T17 ID: {player_id}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"User {target_user.name} is not registered.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in check_registration: {e}")
            await interaction.response.send_message(
                "An error occurred while checking registration status.",
                ephemeral=True
            ) 