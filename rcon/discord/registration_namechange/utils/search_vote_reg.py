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

async def register_user(db_instance, user_name: str, user_id: int, nick_name: str, ingame_name: str, vote_reminders: int = 1) -> Tuple[bool, str]:
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
            vote_reminders,  # votreg_ask_reg_cnt - 1 for enabled, 0 for disabled
            0,  # not_ingame_cnt
            None,  # clan_tag
            None,  # t17_number
            None,  # emojis
            None   # display_format
        )
        return True, f"Registration successful. Vote reminders are {'enabled' if vote_reminders else 'disabled'}."

    except Exception as e:
        logger.error(f"Unexpected error in register_user: {e}")
        return False, "An error occurred during registration"

async def handle_autocomplete(
    interaction: discord.Interaction, 
    current: str,
    in_loop_ref: bool = False,
    min_length: int = 2,
    max_results: int = 25
) -> List[app_commands.Choice[str]]:
    """
    Generic autocomplete handler for player names
    
    Args:
        interaction: Discord interaction object
        current: Current input string
        in_loop_ref: Reference to prevent concurrent lookups
        min_length: Minimum length of search string
        max_results: Maximum number of results to return
    """
    try:
        while in_loop_ref:
            await asyncio.sleep(1)
           
        in_loop_ref = True
        
        if len(current) >= min_length:
            logger.info(f"Search query: {current.replace(' ', '%')}")
            results = await query_player_database(current.replace(" ", "%"))
            
            if results is not None and len(results) >= 1:
                choices = [
                    app_commands.Choice(
                        name=f"Last: {datetime.fromtimestamp(player[3]/1000).strftime('%Y-%m-%d')} - {', '.join(player[1])}"[:100],
                        value=player[0]
                    )
                    for player in results[:max_results]
                ]
                in_loop_ref = False
                return choices
        
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

async def get_registration_details(db_instance, user_id: int) -> Tuple[Optional[tuple], Optional[str]]:
    """Get full registration details for a user.
    Returns (result_tuple, error_message)"""
    try:
        # Get full registration details including votreg_ask_reg_cnt
        db_instance.cursor.execute(
            '''SELECT votreg_t17_id, votreg_clan_tag, votreg_t17_number, votreg_emojis, votreg_ask_reg_cnt 
               FROM voter_register 
               WHERE votreg_dis_user_id = ? 
               ORDER BY votreg_seqno DESC LIMIT 1''', 
            (user_id,)
        )
        result = db_instance.cursor.fetchone()
        
        if not result:
            return None, "User is not registered"
            
        if len(result) != 5:
            logger.error(f"Unexpected result format from database: {result}")
            return None, "Invalid registration data format"
            
        return result, None
        
    except Exception as e:
        logger.error(f"Error getting registration details: {e}")
        return None, "An error occurred while retrieving registration data"

async def format_registration_info(user_name: str, registration_data: tuple) -> str:
    """Format registration data into a readable string."""
    player_id, clan_tag, t17_number, emojis, vote_reminders = registration_data
    
    components = []
    if clan_tag: components.append(f"Clan: {clan_tag}")
    if t17_number: components.append(f"T17#: {t17_number}")
    if emojis: components.append(f"Emojis: {emojis}")
    components.append(f"Vote Reminders: {'Enabled' if vote_reminders else 'Disabled'}")
    
    info = f"User {user_name} is registered with T17 ID: {player_id}"
    if components:
        info += f"\nComponents: {', '.join(components)}"
        
    return info

async def update_registration(
    db_instance,
    user_name: str,
    user_id: int,
    nick_name: str,
    player_id: str,
    vote_reminders: Optional[bool] = None,
    clan_tag: Optional[str] = None,
    t17_number: Optional[str] = None,
    emojis: Optional[str] = None,
    display_format: Optional[str] = None
) -> Tuple[bool, str]:
    """Update or create user registration with specified components."""
    try:
        # Get existing registration
        result, error = await get_registration_details(db_instance, user_id)
        
        # If updating existing registration, preserve current values unless new ones provided
        if result:
            _, current_clan, current_t17, current_emojis, current_vote = result
            clan_tag = clan_tag if clan_tag is not None else current_clan
            t17_number = t17_number if t17_number is not None else current_t17
            emojis = emojis if emojis is not None else current_emojis
            vote_reminders = vote_reminders if vote_reminders is not None else bool(current_vote)
        
        # Insert new registration
        db_instance.insert_Voter_Registration(
            user_name,
            user_id,
            nick_name,
            player_id,
            1 if vote_reminders else 0,  # votreg_ask_reg_cnt
            0,  # not_ingame_cnt
            clan_tag,
            t17_number,
            emojis,
            display_format
        )
        return True, "Registration updated successfully"
        
    except Exception as e:
        logger.error(f"Error updating registration: {e}")
        return False, "An error occurred while updating registration" 