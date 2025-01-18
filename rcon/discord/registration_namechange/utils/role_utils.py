import logging
from typing import Optional
import discord
from lib.config import config

logger = logging.getLogger(__name__)

async def handle_roles(member: discord.Member, action: str) -> Optional[str]:
    """
    Handle role assignments for registration and name changes.
    Returns error message if there's an issue, None if successful.
    """
    try:
        # Check if roles are configured
        role_config = config.get("rcon", 0, "name_change_registration", "roles", action)
        if not role_config or not role_config.get("enabled", False):
            return None

        role_id = role_config.get("role_id")
        if not role_id:
            logger.error(f"No role_id configured for {action}")
            return f"No role configured for {action}"

        # Get the role
        role = member.guild.get_role(int(role_id))
        if not role:
            logger.error(f"Could not find role with ID {role_id}")
            return f"Could not find configured role"

        # Add role if member doesn't have it
        if role not in member.roles:
            try:
                await member.add_roles(role)
                logger.info(f"Added {role.name} role to {member.name}")
            except discord.Forbidden:
                return "Bot doesn't have permission to assign roles"
            except Exception as e:
                logger.error(f"Error assigning role: {e}")
                return "Error assigning role"

        return None

    except Exception as e:
        logger.error(f"Error in handle_roles: {e}")
        return "Error handling roles" 