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
            # Check if feature is enabled
            if not config.get("rcon", 0, "name_change_registration", "enabled", default=True):
                await interaction.response.send_message("This feature is not enabled.", ephemeral=True)
                return

            # Get member
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("Could not find your Discord account.", ephemeral=True)
                return

            # Get current registration
            result = self.select_T17_Voter_Registration(interaction.user.id)
            if not result:
                await interaction.response.send_message(
                    "You are not registered. Please use /voter_registration first.",
                    ephemeral=True
                )
                return

            # Validate emojis
            valid, error = self.validate_emojis(emojis)
            if not valid:
                await interaction.response.send_message(error, ephemeral=True)
                return

            # Update nickname
            success, new_name = await self.update_nickname_with_emojis(member, emojis)
            
            if not success:
                await interaction.response.send_message(new_name, ephemeral=True)  # new_name contains error message
                return

            # Update database
            try:
                self.cursor.execute(
                    '''UPDATE voter_register 
                       SET votreg_emojis = ?
                       WHERE votreg_dis_user_id = ? 
                       ORDER BY votreg_seqno DESC LIMIT 1''',
                    (emojis, interaction.user.id)
                )
                self.conn.commit()
            except Exception as e:
                logger.error(f"Database error in name_emoji: {e}")
                await interaction.response.send_message(
                    "Your nickname was updated but there was an error saving to the database.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"Emojis updated successfully. New nickname: {new_name}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in name_emoji: {e}")
            await interaction.response.send_message(
                "An error occurred while updating your emojis.",
                ephemeral=True
            ) 