import discord
import logging
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
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
    async def update_name(self, interaction: discord.Interaction):
        try:
            # Check if user is registered
            player_id = self.select_T17_Voter_Registration(interaction.user.id)
            if player_id is None:
                await interaction.response.send_message(
                    "You are not registered. Please use /voter_registration first.",
                    ephemeral=True
                )
                return

            # Get latest player name from T17 ID
            player_name = await get_player_name(player_id)
            if not player_name:
                await interaction.response.send_message(
                    "Could not fetch your latest in-game name.",
                    ephemeral=True
                )
                return

            # Update nickname
            try:
                member = interaction.guild.get_member(interaction.user.id)
                await member.edit(nick=player_name)
                logger.info(f"Updated nickname for {interaction.user.name} to {player_name}")
                await interaction.response.send_message(
                    f"Successfully updated your nickname to {player_name}",
                    ephemeral=True
                )
            except discord.Forbidden:
                logger.error(f"Failed to update nickname for {interaction.user.name} - insufficient permissions")
                await interaction.response.send_message(
                    "I don't have permission to update your nickname.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error(f"HTTP error while updating nickname: {e}")
                await interaction.response.send_message(
                    "There was an error updating your nickname.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in update_name: {e}")
            await interaction.response.send_message(
                "An error occurred while updating your name.",
                ephemeral=True
            ) 