import logging
import re
from typing import List, Tuple, Optional
import rcon.rcon as rcon
import asyncio
import discord
from discord import app_commands
from datetime import datetime

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
        result = db_instance.select_T17_Voter_Registration(user_id)
        if result is not None:
            return False, "You are already registered. If it wasn't you, please contact @Techsupport!"

        # Register the user with initial empty components
        db_instance.insert_Voter_Registration(
            user_name,
            user_id,
            nick_name,
            ingame_name,
            0,  # register_cnt
            0,  # not_ingame_cnt
            None,  # clan_tag
            None,  # t17_number
            None,  # emojis
            None   # display_format
        )
        return True, "Registration successful"

    except Exception as e:
        logger.error(f"Unexpected error in register_user: {e}")
        return False, "An error occurred during registration"

async def handle_autocomplete(interaction: discord.Interaction, player_name: str, in_loop_ref) -> List[app_commands.Choice[str]]:
    """Handle autocomplete for player names"""
    try:
        while in_loop_ref:
            await asyncio.sleep(1)
           
        in_loop_ref = True
        name = player_name
        multi_array = None

        if len(name) >= 2:
            logger.info(f"Search query: {name.replace(" ", "%")}")
            multi_array = await query_player_database(name.replace(" ", "%"))
        
        if multi_array is not None and len(multi_array) >= 1:
            result = [
                app_commands.Choice(name=f"Last: {datetime.fromtimestamp(player[3]/1000).strftime('%Y-%m-%d')} - {", ".join(player[1])}"[:100], value=player[0])
                for player in multi_array
            ]
            in_loop_ref = False
            return result
        
        in_loop_ref = False
        return []
            
    except Exception as e:
        logger.error(f"Unexpected error in handle_autocomplete: {e}")
        in_loop_ref = False
        return []
    finally:
        in_loop_ref = False 

async def get_player_name(t17_id: str) -> Optional[str]:
    """Get a player's name from their T17 ID."""
    try:
        history_result = await rcon.get_Player_History({"player_id": t17_id})
        if history_result:
            player_names = history_result.get_Players_Name()
            if player_names and len(player_names) > 0:
                return player_names[0][1][0]  # Get first name from first record
        return None
            
    except Exception as e:
        logger.error(f"Unexpected error in get_player_name: {e}")
        return None 