import logging
from typing import Optional
import discord
from lib.config import config

logger = logging.getLogger(__name__)

async def handle_roles(member: discord.Member, action_type: str) -> Optional[str]:
    """
    Handle role assignments based on action type.
    action_type can be 'registered' or 'name_changed'
    Returns error message if something goes wrong, None on success
    """
    try:
        # Check if role management is enabled for this action
        if not config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "roles", action_type, "enabled", default=False):
            return None

        # Get role ID from config
        role_id = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "roles", action_type, "role_id")
        if not role_id:
            logger.error(f"No role ID configured for {action_type}")
            return None

        # Get the role
        role = member.guild.get_role(int(role_id))
        if not role:
            logger.error(f"Could not find role with ID {role_id}")
            return "Could not find the configured role."

        # Check bot permissions
        if not member.guild.me.guild_permissions.manage_roles:
            return "I don't have permission to manage roles."

        # Check role hierarchy
        if role >= member.guild.me.top_role:
            return "I can't assign this role due to role hierarchy."

        # Assign role if member doesn't have it
        if role not in member.roles:
            await member.add_roles(role)
            logger.info(f"Added {action_type} role to {member.name}")

        return None

    except Exception as e:
        logger.error(f"Error handling roles: {e}")
        return f"An error occurred while managing roles: {str(e)}"