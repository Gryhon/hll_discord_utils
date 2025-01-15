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

async def get_player_name(t17_id: str) -> Optional[str]:
    """Fetch the player's most recent name from their history using their T17 ID."""
    try:
        history_result = await rcon.get_Player_History({"player_id": t17_id})
        if history_result:
            players = history_result.get_Players_Name()
            if players and len(players) > 0:
                # Get most recent name and take only the first name before any comma
                recent_name = players[0][1][0]  # Take first name from the array
                return recent_name[:32]  # Discord nickname limit
                
        return None

    except Exception as e:
        logger.error(f"Unexpected error in get_player_name: {e}")
        return None 