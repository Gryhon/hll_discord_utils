import logging
from typing import Tuple, Optional
from lib.config import config

logger = logging.getLogger(__name__)

def validate_t17_number(t17_number: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate T17 number format.
    Returns (is_valid, error_message)
    """
    if not t17_number:
        # Check if T17 is required by config
        if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False):
            return False, "T17 number is required. Please provide your 4-digit T17 number."
        return True, None
        
    if not t17_number.isdigit() or len(t17_number) != 4:
        return False, "Invalid T17 number. Please provide a 4-digit number."
        
    return True, None

def format_nickname(base_name: str, t17_number: Optional[str] = None) -> str:
    """Format the nickname with optional T17 number."""
    if not t17_number:
        return base_name[:32]  # Discord's nickname limit
        
    full_name = f"{base_name} #{t17_number}"
    return full_name[:32]  # Discord's nickname limit 