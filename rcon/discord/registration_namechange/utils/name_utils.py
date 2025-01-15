import logging
from typing import Tuple, Optional
from lib.config import config

logger = logging.getLogger(__name__)

def validate_t17_number(t17_number: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate T17 number format."""
    if not t17_number:
        if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False):
            return False, "T17 number is required. Please provide your 4-digit T17 number."
        return True, None
        
    if not t17_number.isdigit() or len(t17_number) != 4:
        return False, "Invalid T17 number. Please provide a 4-digit number."
        
    return True, None

def validate_clan_tag(clan_tag: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate clan tag format and check against blocked tags."""
    if not clan_tag:
        return True, None

    max_length = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "clan_tag", "max_length", default=4)
    blocked_tags = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "clan_tag", "blocked_tags", default=[])
    
    if len(clan_tag) > max_length:
        return False, f"Clan tag must be {max_length} characters or less."
        
    if clan_tag.upper() in [tag.upper() for tag in blocked_tags]:
        return False, "This clan tag is not allowed."
        
    return True, None

def format_nickname(base_name: str, t17_number: Optional[str] = None, clan_tag: Optional[str] = None) -> str:
    """Format the nickname with optional T17 number and clan tag."""
    name_parts = []
    
    # Format clan tag if provided
    if clan_tag:
        formatted_tag = f"[{clan_tag.upper()}]"
        
    # Get position for clan tag
    tag_position = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "clan_tag", "position", default="prefix")
    
    # Build name based on position
    if tag_position == "prefix" and clan_tag:
        name_parts.append(formatted_tag)
    
    name_parts.append(base_name)
    
    if tag_position == "suffix" and clan_tag:
        name_parts.append(formatted_tag)
        
    if t17_number:
        name_parts.append(f"#{t17_number}")
    
    # Join all parts with spaces and respect Discord's limit
    return " ".join(name_parts)[:32] 