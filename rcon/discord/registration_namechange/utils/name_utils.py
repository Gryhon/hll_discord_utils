import logging
from typing import Tuple, Optional
from lib.config import config
import discord

logger = logging.getLogger(__name__)

def validate_t17_number(t17_number: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate T17 number format."""
    try:
        if not t17_number:
            if config.get("comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False):
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
    """Validate clan tag format and check against blocked tags."""
    if not clan_tag:
        return True, None

    try:
        if not config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "show", default=True):
            return False, "Clan tags are not enabled."

        max_length = config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "max_length", default=4)
        blocked_tags = config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "blocked_tags", default=[])
    except ValueError:
        # If config isn't loaded, use defaults
        max_length = 4
        blocked_tags = []
    
    if len(clan_tag) > max_length:
        return False, f"Clan tag must be {max_length} characters or less."
        
    if clan_tag.upper() in [tag.upper() for tag in blocked_tags]:
        return False, "This clan tag is not allowed."
        
    return True, None

def validate_emojis(emojis: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate emoji input."""
    if not emojis:
        return True, None

    if not config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "emojis", "show", default=True):
        return False, "Emojis are not enabled."

    max_count = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "emojis", "max_count", default=3)
    emoji_count = len(emojis.split())

    if emoji_count > max_count:
        return False, f"Maximum {max_count} emojis allowed."

    return True, None

def format_nickname(base_name: str, t17_number: Optional[str] = None, clan_tag: Optional[str] = None, emojis: Optional[str] = None) -> str:
    """Format the nickname with optional T17 number, clan tag, and emojis."""
    result = ""
    
    # Format clan tag if provided and allowed
    if clan_tag and config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "show", default=True):
        formatted_tag = f"[{clan_tag.upper()}]"
        tag_position = config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "position", default="prefix")
        
        # Add prefix clan tag
        if tag_position == "prefix":
            result += formatted_tag
    
    # Add base name
    result += base_name
    
    # Add T17 number if provided
    if t17_number:
        result += f"#{t17_number}"
    
    # Add emojis if provided and enabled
    if emojis and config.get("comfort_functions", 0, "name_change_registration", "emojis", "show", default=True):
        result += emojis
    
    # Add suffix clan tag
    if clan_tag and config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "show", default=True):
        tag_position = config.get("comfort_functions", 0, "name_change_registration", "clan_tag", "position", default="prefix")
        if tag_position == "suffix":
            result += formatted_tag
    
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

        is_valid, error_message = validate_emojis(emojis)
        if not is_valid:
            return False, "", error_message

        # Format the nickname
        formatted_name = format_nickname(base_name, t17_number, clan_tag, emojis)
        
        # Update nickname
        try:
            await member.edit(nick=formatted_name)
            
            # Store the components
            db_instance.insert_Voter_Registration(
                member.name,
                member.id,
                formatted_name,
                base_name,
                0,  # register_cnt
                0,  # not_ingame_cnt
                clan_tag,
                t17_number,
                emojis,
                None  # display_format
            )
            
            return True, formatted_name, None
            
        except discord.Forbidden:
            return False, "", "I don't have permission to change your nickname."
            
    except Exception as e:
        logger.error(f"Error in update_user_nickname: {e}")
        return False, "", "An error occurred while updating the nickname." 