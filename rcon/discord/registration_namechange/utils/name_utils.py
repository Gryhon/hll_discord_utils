import logging
from typing import Tuple, Optional
from lib.config import config
import discord

logger = logging.getLogger(__name__)

def validate_t17_number(t17_number: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate T17 number format."""
    try:
        if not t17_number:
            if config.get("rcon", 0, "name_change_registration", "t17_number", "required", default=False):
                return False, "T17 number is required. Please provide your 4-digit T17 number."
            return True, None
    except ValueError:
        # If config isn't loaded, assume not required
        if not t17_number:
            return True, None
        
    if not t17_number.isdigit() or len(t17_number) != 4:
        return False, "Invalid T17 number. Please provide a 4-digit number."
        
    return True, None

def validate_clan_tag(clan_tag: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate clan tag format and check against hidden tags."""
    if not clan_tag:
        return True, None

    try:
        if not config.get("rcon", 0, "name_change_registration", "clan_tag", "show", default=True):
            return True, None  # Still valid, just won't be shown

        # Get max length from config
        max_length = config.get("rcon", 0, "name_change_registration", "clan_tag", "max_length", default=4)
        if len(clan_tag) > max_length:
            return False, f"Clan tag must be {max_length} characters or less."

        # Get hidden tags list
        hidden_tags = config.get("rcon", 0, "name_change_registration", "clan_tag", "blocked_tags", default=[])
        
        # Tag is valid but might be hidden
        return True, None

    except Exception as e:
        logger.error(f"Error validating clan tag: {e}")
        return False, "An error occurred while validating the clan tag."

def format_nickname(base_name: str, t17_number: Optional[str] = None, clan_tag: Optional[str] = None, emojis: Optional[str] = None) -> str:
    """Format the nickname with optional T17 number and clan tag."""
    result = ""
    
    # Format clan tag if provided and allowed
    if clan_tag and config.get("rcon", 0, "name_change_registration", "clan_tag", "show", default=True):
        # Check if tag should be hidden
        hidden_tags = config.get("rcon", 0, "name_change_registration", "clan_tag", "blocked_tags", default=[])
        if clan_tag.upper() not in [tag.upper() for tag in hidden_tags]:
            formatted_tag = f"[{clan_tag.upper()}]"
            tag_position = config.get("rcon", 0, "name_change_registration", "clan_tag", "position", default="prefix")
            
            # Add prefix clan tag
            if tag_position == "prefix":
                result += formatted_tag
    
    # Add base name
    result += base_name
    
    # Add T17 number if provided and show is enabled
    if t17_number and config.get("rcon", 0, "name_change_registration", "t17_number", "show", default=True):
        result += f"#{t17_number}"
    
    # Add suffix clan tag if not hidden
    if clan_tag and config.get("rcon", 0, "name_change_registration", "clan_tag", "show", default=True):
        hidden_tags = config.get("rcon", 0, "name_change_registration", "clan_tag", "blocked_tags", default=[])
        if clan_tag.upper() not in [tag.upper() for tag in hidden_tags]:
            tag_position = config.get("rcon", 0, "name_change_registration", "clan_tag", "position", default="prefix")
            if tag_position == "suffix":
                result += formatted_tag
    
    # Add emojis if provided and enabled
    if emojis and config.get("rcon", 0, "name_change_registration", "emojis", "show", default=True):
        # Remove any custom emoji format attempts
        if '<:' in emojis:
            logger.warning("Custom Discord emojis are not supported in nicknames. Skipping emoji.")
        else:
            result += f" {emojis}"
    
    return result[:32]

async def update_user_nickname(
    db_instance,
    member: discord.Member,
    base_name: str,
    t17_number: Optional[str] = None,
    clan_tag: Optional[str] = None,
    emojis: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Update a user's nickname with the given components.
    Returns (success, formatted_name, error_message)
    """
    try:
        # Validate inputs
        is_valid, error_message = validate_t17_number(t17_number)
        if not is_valid:
            return False, "", error_message

        is_valid, error_message = validate_clan_tag(clan_tag)
        if not is_valid:
            return False, "", error_message

        # Format nickname with components
        formatted_name = format_nickname(base_name, t17_number, clan_tag, emojis)

        # Update nickname
        try:
            await member.edit(nick=formatted_name)
            return True, formatted_name, None
        except discord.Forbidden:
            return False, "", "I don't have permission to update nicknames."
        except Exception as e:
            logger.error(f"Error updating nickname: {e}")
            return False, "", "Failed to update nickname."

    except Exception as e:
        logger.error(f"Error in update_user_nickname: {e}")
        return False, "", "An error occurred while updating the nickname." 