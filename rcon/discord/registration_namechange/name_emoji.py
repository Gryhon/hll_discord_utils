import logging
from typing import Optional, Tuple
import discord
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from lib.config import config

logger = logging.getLogger(__name__)

class NameEmoji(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def validate_emojis(self, emojis: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate emoji input."""
        if not emojis:
            return True, None

        if not config.get("rcon", 0, "name_change_registration", "emojis", "show", default=True):
            return False, "Emojis are not enabled."

        max_count = config.get("rcon", 0, "name_change_registration", "emojis", "max_count", default=3)
        emoji_count = len(emojis.split())

        if emoji_count > max_count:
            return False, f"Maximum {max_count} emojis allowed. Your emojis may be trimmed if they exceed the nickname length limit."

        return True, None

    def strip_emojis(self, name: str) -> str:
        """Remove emojis from the end of the name."""
        # Split on first emoji (if any exist)
        parts = name.split('🎖️', 1)[0].split('⚔️', 1)[0].split('🛡️', 1)[0].split('⭐', 1)[0].split('🎮', 1)[0]
        return parts[0].rstrip()

    async def update_nickname_with_emojis(self, member: discord.Member, emojis: Optional[str]) -> Tuple[bool, str]:
        """Update nickname with new emojis while preserving the base name."""
        try:
            current_name = member.nick or member.name
            base_name = self.strip_emojis(current_name)
            
            # Create new name with emojis
            new_name = base_name
            if emojis:
                new_name = f"{base_name} {emojis}"
            
            # Ensure name doesn't exceed Discord's 32-character limit
            if len(new_name) > 32:
                new_name = new_name[:32]
                
            # Update nickname
            await member.edit(nick=new_name)
            return True, new_name
            
        except discord.Forbidden:
            return False, "I don't have permission to update nicknames."
        except Exception as e:
            logger.error(f"Error updating nickname: {e}")
            return False, "Failed to update nickname."

    @app_commands.command(
        name="name-emoji",
        description="Update the emojis in your Discord nickname (up to 5)"
    )
    @app_commands.describe(
        emojis="Paste your emojis with spaces between them"
    )
    async def name_emoji(
        self,
        interaction: discord.Interaction,
        emojis: Optional[str] = None
    ):
        try:
            logger.info(f"Name emoji request from {interaction.user.name} (ID: {interaction.user.id}) with emojis: {emojis}")
            
            # Check if feature is enabled
            if not config.get("rcon", 0, "name_change_registration", "enabled", default=True):
                logger.info("Feature disabled in config")
                await interaction.response.send_message("This feature is not enabled.", ephemeral=True)
                return

            # Get member
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                logger.error(f"Could not find member for user {interaction.user.name} (ID: {interaction.user.id})")
                await interaction.response.send_message("Could not find your Discord account.", ephemeral=True)
                return

            # Get current registration
            result = self.select_T17_Voter_Registration(interaction.user.id)
            if not result:
                logger.warning(f"User {interaction.user.name} not registered")
                await interaction.response.send_message(
                    "You are not registered. Please use /voter_registration first.",
                    ephemeral=True
                )
                return

            # Get the actual player name first (like update_name does)
            player_name = await get_player_name(result[0])  # Use the stored T17 ID to get the actual player name
            if not player_name:
                logger.error(f"Could not retrieve player name for {interaction.user.name}")
                await interaction.response.send_message(
                    "Could not retrieve your player name. Please contact an administrator.",
                    ephemeral=True
                )
                return

            # Validate emojis
            valid, error = self.validate_emojis(emojis)
            if not valid:
                logger.warning(f"Invalid emojis from {interaction.user.name}: {emojis}. Error: {error}")
                await interaction.response.send_message(error, ephemeral=True)
                return

            # Update nickname with components - using the fetched player_name
            success, formatted_name, error_message = await update_user_nickname(
                self,
                member,
                player_name,  # Use the actual player name we just fetched
                result[2],    # T17 number
                result[1],    # Clan tag
                emojis       # New emojis
            )

            if not success:
                logger.error(f"Failed to update nickname for {interaction.user.name}. Error: {error_message}")
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Update registration with new emojis
            success, message = await update_registration(
                self,
                interaction.user.name,
                interaction.user.id,
                formatted_name,
                result[0],    # Keep existing T17 ID
                None,         # Keep existing vote reminder setting
                result[1],    # Keep existing clan tag
                result[2],    # Keep existing T17 number
                emojis       # Update emojis
            )

            if success:
                logger.info(f"Successfully updated emojis for {interaction.user.name} to: {emojis}")
                await interaction.response.send_message(
                    f"Successfully updated your nickname with emojis: {formatted_name}",
                    ephemeral=True
                )
            else:
                logger.error(f"Failed to update registration for {interaction.user.name}. Error: {message}")
                await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in name_emoji for {interaction.user.name}: {str(e)}", exc_info=True)
            await interaction.response.send_message("An error occurred while updating your emojis.", ephemeral=True) 