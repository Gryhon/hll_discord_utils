import logging
import re
from typing import List, Tuple, Optional
import rcon.rcon as rcon

logger = logging.getLogger(__name__)

async def query_player_database(query: str) -> List[str]:
    """Query the player database for matching names."""
    try:
        if len(query) > 1:       
            payload = {"page_size": 25, "page": 1, "player_name": query}
            result = await rcon.get_Player_History(payload)
            player = result.get_Players_Name()
            
            if player is not None and len(player):
                return player[:25]
        return None
            
    except Exception as e:
        logger.error(f"Unexpected error in query_player_database: {e}")
        return None

async def register_user(db_instance, user_name: str, user_id: int, nick_name: str, ingame_name: str) -> Tuple[bool, str]:
    """Register a user in the database. Returns (success, message)."""
    try:
        # Verify T17 ID format
        if not bool(re.fullmatch(r"[0-9a-fA-F]{32}", ingame_name)):
            return False, '''Something went wrong, please select your name from the\n''' \
                         '''list and do not add or remove any characters,\n''' \
                         '''after the selection.'''

        # Check if already registered
        player_id = db_instance.select_T17_Voter_Registration(user_id)
        if player_id is not None:
            return False, "You are already registered. If it wasn't you, please contact @Techsupport!"

        # Register the user
        db_instance.insert_Voter_Registration(user_name, user_id, nick_name, ingame_name, 0, 0)
        return True, "Registration successful"

    except Exception as e:
        logger.error(f"Unexpected error in register_user: {e}")
        return False, "An error occurred during registration"

async def get_player_name(ingame_name: str) -> Optional[str]:
    """Fetch the player's name from the game database."""
    try:
        payload = {"player_id": ingame_name}
        player_info = await rcon.get_Player_Info(payload)
        
        if player_info and player_info.name:
            return player_info.name
        return None

    except Exception as e:
        logger.error(f"Unexpected error in get_player_name: {e}")
        return None 