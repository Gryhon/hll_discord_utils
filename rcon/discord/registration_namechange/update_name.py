import discord
import logging
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import get_player_name
from lib.config import config
from .utils.name_utils import validate_t17_number, format_nickname, validate_clan_tag, validate_emojis
from typing import Optional
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed

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
        t17_number="Your 4-digit T17 number (optional)" if not config.get("comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else "Your 4-digit T17 number",
        clan_tag="Your clan tag (optional)" if config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "show", default=True) else None,
        emojis="Your emojis (optional, max 3)" if config.get("comfort_functions", 0, "name_change_registration", "emojis", "show", default=True) else None
    )
    async def update_name(
        self, 
        interaction: discord.Interaction,
        t17_number: str if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else Optional[str] = None,
        clan_tag: Optional[str] = None,
        emojis: Optional[str] = None
    ):
        try:
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
                formatted_name = format_nickname(player_name, t17_number, clan_tag, emojis)
                await member.edit(nick=formatted_name)
                logger.info(f"Updated nickname for {interaction.user.name} to {formatted_name}")
                
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