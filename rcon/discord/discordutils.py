import discord
import logging
from lib.config import config

logger = logging.getLogger(__name__)

async def safe_send(interaction: discord.Interaction, content: str, ephemeral: bool = True):
    # Send message or follow-up if already responded.
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=ephemeral)
        else:
            await interaction.followup.send(content, ephemeral=ephemeral)
    
    except Exception as e:
        logger.error(f"Failed to send interaction message: {e}", exc_info=True)

def has_allowed_role(member: discord.Member, item: str) -> bool:
    ret = False

    try:
        allowed_names = (config.get("rcon", 0, "discord_commands", 0, f"{item}", 0, "groups") or
                         config.get("rcon", 0, "discord_commands", 0, "groups") or [])
        
        if config.get("rcon", 0, "discord_commands", 0, "admin_always") and member.guild_permissions.administrator:
            ret = True
        else:
            ret = any(role.name in allowed_names for role in member.roles)

        return ret
    
    except Exception as e:
        logger.error(f"Error in has_allowed_role: {e}", exc_info=True)
        return False