import logging
import rcon.model as model
from lib.utils import get_Data, post_Data

# get Logger for this module
logger = logging.getLogger(__name__)

async def get_Game_State ():
    try:
        data = await get_Data ("/api/get_gamestate")

        if data:
            current_map = model.CurrentMap()
            next_map = model.NextMap()
            game_status = model.GameStatus()

            current_map.parse_Json(data)
            next_map.parse_Json(data)
            game_status.parse_Json(data)

            await get_Server_Status ()

            return current_map, next_map, game_status
        else:
            return None, None, None
    except:
        logger.error ("Exception in get_Game_State")
        return None, None, None

async def get_Scoreboard_Maps ():
    try:
        data = await get_Data ("/api/get_scoreboard_maps")
        
        if data:
            scoreboard_maps = model.ScoreboardMaps()
            
            scoreboard_maps.parse_Json(data)
            
            return scoreboard_maps
        else:
            return None
    except:
        logger.error ("Exception in get_Server_Status")
        return None
    
async def get_Previous_Map ():
    try:
        data = await get_Data ("/api/get_previous_map")
        
        if data:
            map = model.PreviousMap()
            
            map.parse_Json(data)
            
            return map
        else:
            return None
    except:
        logger.error ("Exception in get_Previous_Map")
        return None
    
async def get_Current_Map ():
    try:
        data = await get_Data ("/api/get_public_info")
        
        if data:
            map = model.ActualMap()
            
            map.parse_Json(data)
            
            return map
        else:
            return None
    except:
        logger.error ("Exception in get_Previous_Map")
        return None

async def get_Last_Game_Id ():
    try:
        scoreboard_maps = await get_Scoreboard_Maps ()
        
        if scoreboard_maps:
            return scoreboard_maps.total
        else:
            return None
    except:
        logger.error ("Exception in get_Server_Status")
        return None

async def get_Server_Status ():
    try:
        data = await get_Data ("/api/get_status")

        if data:
            serverstatus = model.ServerStatus()
            
            serverstatus.parse_Json(data)
            
            return serverstatus
        else:
            return None
    except:
        logger.error ("Exception in get_Server_Status")
        return None
    
async def get_Map_Rotation ():
    data = await get_Data ("/api/get_map_rotation")

    if data:
        serverstatus = model.MapRotation()
        
        serverstatus.parse_Json(data)
        
        return serverstatus
    else:
        return None
      
async def get_Maps_To_Vote ():
    
    data = await get_Data ("/api/get_votemap_status")

    if data:
        mapstovote = model.MapsToVote()
        
        mapstovote.parse_Json(data)
        
        return mapstovote
    else:
        return None

async def get_Balance_Return (limits):
    return 0, 0, [0] * (len (limits) + 1), [0] * (len (limits) + 1)

async def get_Balance (limits = [50, 100, 250], weights = [0.25, 0.5, 1, 1.25]):
    try:
        _, _, game_status = await get_Game_State ()

        if game_status and game_status.num_axis_players >= 1 and game_status.num_allied_players >= 1:
            data = await get_Data ("/api/get_team_view")
            
            if data:  
                balance = model.Balance (limits, weights)
                balance.parse_Json (data)
                return balance.calculate_Balance ()

            else:
                return await get_Balance_Return (limits)
            
        elif not game_status:

            logger.warning ("No information from get_Game_State.")
            return await get_Balance_Return (limits)
        else:
            logger.debug ("Not enough players. Can't calculate balance.")
            return await get_Balance_Return (limits)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return await get_Balance_Return (limits)

async def get_Recent_Logs (filter, generic_class):
    data = await post_Data ("/api/get_recent_logs", filter)

    if data:
        generic = generic_class()
        generic.parse_Json(data)

        return generic
    else:
        return None

async def get_Players ():
    data = await get_Data ("/api/get_players")

    if data:
        players = model.Players()
        
        players.parse_Json(data)
        
        return players
    else:
        return None
    
async def get_Player_Profile (payload):
    data = await post_Data ("/api/get_player_profile", payload)

    if data:
        players = model.PlayerProfile()
        
        players.add_Json(data)
        
        return players
    else:
        return None 

async def get_In_Game_Players ():
    data = await get_Data ("/api/get_team_view")

    if data:
        players = model.InGamePlayers()
        
        players.add_Json(data)
        
        return players
    else:
        return None 
    
async def get_Maps ():
    data = await get_Data ("/api/get_maps")

    if data:
        maps = model.Maps()
        
        maps.add_Json(data)
        
        return maps
    else:
        return None 
    
async def get_Map_History (cnt):
    data = await get_Data ("/api/get_map_history")

    if data:
        maps = model.MapHistory()
        
        maps.add_Json(data)
        list = maps.get_Last_Maps (cnt)
        
        return list
    else:
        return None 

async def set_Map_Rotation (payload):
    await post_Data ("/api/set_maprotation", payload)

async def send_Player_Message (message):
    await post_Data ("/api/message_player", message)

async def kick_Player (payload):
    await post_Data ("/api/kick", payload)

async def get_Player_History (payload):
    data = await post_Data ("/api/get_players_history", payload)

    if data:
        players = model.PlayerHistory()
        
        players.add_Json(data)
        
        return players
    else:
        return None 

async def set_Watch_Player (payload):
    await post_Data ("/api/watch_player", payload)

async def set_Perma_Ban (payload):
    await post_Data ("/api/perma_ban", payload)

async def add_Blacklist_Record (payload):
    print (payload)
    await post_Data ("/api/add_blacklist_record", payload)

    