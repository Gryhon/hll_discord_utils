import discord
import logging
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import get_player_name
from lib.config import config
from .utils.name_utils import validate_t17_number, format_nickname

logger = logging.getLogger(__name__)

class UpdateName(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.t17_required = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False)
        self.t17_show = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "show", default=True)

    @app_commands.command(
        name="update_name",
        description="Update your Discord nickname to your latest in-game name"
    )
    @app_commands.describe(
        t17_number="Your 4-digit T17 number (optional)" if not config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else "Your 4-digit T17 number"
    )
    async def update_name(
        self, 
        interaction: discord.Interaction,
        t17_number: str if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else Optional[str] = None
    ):
        try:
            # Validate T17 number
            is_valid, error_message = validate_t17_number(t17_number)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

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

            # Add T17 number if provided
            if t17_number:
                player_name = f"{player_name} #{t17_number}"

            # Update nickname
            try:
                member = interaction.guild.get_member(interaction.user.id)
                formatted_name = format_nickname(player_name, t17_number)
                await member.edit(nick=formatted_name)
                logger.info(f"Updated nickname for {interaction.user.name} to {formatted_name}")
                await interaction.response.send_message(
                    f"Successfully updated your nickname to {formatted_name}",
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