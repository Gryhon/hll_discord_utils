import logging
from datetime import datetime
from lib.utils import J_Path, Jmes_Path

# get Logger for this modul
logger = logging.getLogger(__name__)

class Map():
    def __init__(self):
        self.id = None
        self.map_id = None
        self.name = None
        self.tag = None
        self.short_name = None
        self.pretty_name = None
        self.game_mode = None
        self.environment = None
        self.attackers = None
        self.image_name = None
        self.orientation = None

class Maps():
    def __init__(self):
        self.json = None
        self.maps = []

    def add_Json (self, json_string):
        self.json = json_string

    def get_Maps (self, enviroment = [], game_mode = []):
        env = None   
        mod = None   
        query = None  
        try:
            if self.json:
                for item in enviroment:
                    if not env:
                        env = f"@.environment == '{item}'"
                    else:
                        env += f" || @.environment == '{item}'"

                for item in game_mode:
                    if not mod:
                        mod = f"@.game_mode == '{item}'"
                    else:
                        mod += f" || @.game_mode == '{item}'"

                if env or mod:
                    query = f"result[?("

                    if env:
                        query += f"({env})"

                    if env and mod:
                        query += f" && "
                    else:
                        query += f"]"

                    if mod:
                        query += f"({mod})"

                    query += f")]"

                logger.debug (f"Get Map Query : {query}")

                result = Jmes_Path.get_Match (query, self.json, "Not Found")

                if result != "Not Found":
                    return result
                else:
                    return None
            else:
                logger.error(f"No Json data")    
                return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
        
    def get_Map_Names (self, enviroment = [], game_mode = [], blacklist = []):
        try:
            matches = self.get_Maps (enviroment, game_mode)

            if matches: 
                names = J_Path.get_Matches ("$[*].id", matches)

                if len (names):
                    filtered_list = list(set(names) - set(blacklist))
                    return filtered_list
                else:
                    return None
            else:
                logger.error(f"No Json data")    
                return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
        
    def get_Maps_from_ID (self, map_ids):
        try:
            for item in map_ids:
                map = Map ()
                map.id = item
                map.pretty_name = J_Path.get_Match (f"$.result[?(@.id == '{item}')].pretty_name", self.json, "End of Game")
                map.environment = J_Path.get_Match (f"$.result[?(@.id == '{item}')].environment", self.json)
                map.image_name = J_Path.get_Match (f"$.result[?(@.id == '{item}')].image_name", self.json)
                self.maps.append (map)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def get_Maps_from_PrettyName (self, map_pretty_names):
        try:
            for item in map_pretty_names:
                map = Map ()
                map.id = J_Path.get_Match (f"$.result[?(@.pretty_name == '{item}')].id", self.json, "End of Game")
                map.pretty_name = item
                map.environment = J_Path.get_Match (f"$.result[?(@.pretty_name == '{item}')].environment", self.json)
                map.image_name = J_Path.get_Match (f"$.result[?(@.pretty_name == '{item}')].image_name", self.json)
                self.maps.append (map)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

class CurrentMap(Map):
    def parse_Json (self, json_string):
        try:
            self.pretty_name = J_Path.get_Match ("$..current_map..pretty_name", json_string, "End of Game")
            self.game_mode = J_Path.get_Match ("$..current_map..game_mode", json_string)
            self.environment = J_Path.get_Match ("$..current_map..environment", json_string)
            self.attackers = J_Path.get_Match ("$..current_map..attackers", json_string)
            self.image_name = J_Path.get_Match ("$..current_map..image_name", json_string)
        except:
            pass

class NextMap(Map):
    def parse_Json (self, json_string):
        try:
            self.pretty_name = J_Path.get_Match ("$..next_map..pretty_name", json_string)
            self.game_mode = J_Path.get_Match ("$..next_map..game_mode", json_string)
            self.environment = J_Path.get_Match ("$..next_map..environment", json_string)
            self.attackers = J_Path.get_Match ("$..next_map..attackers", json_string)
            self.image_name = J_Path.get_Match ("$..next_map..image_name", json_string)
        except:
            pass

class PlayedMap(Map):
    def __init__(self):
        #super().__init__()
        self.game_id = None
        self.creation_time = None
        self.start = None
        self.end = None
        self.axis = None
        self.allied = None

    def parse_Json (self, json_string):
        try:
            self.game_id = J_Path.get_Match ("$.id",json_string)
            self.creation_time = J_Path.get_Match ("$.creation_time",json_string)
            self.start = J_Path.get_Match ("$.start",json_string)
            self.end = J_Path.get_Match ("$.end",json_string)
            self.axis = J_Path.get_Match ("$.result.axis",json_string)
            self.allied = J_Path.get_Match ("$.result.allied",json_string)

            self.id = J_Path.get_Match ("$.map.id",json_string)
            self.map_id = J_Path.get_Match ("$.map.map.id",json_string)
            self.name = J_Path.get_Match ("$.map.map.name",json_string)
            self.tag = J_Path.get_Match ("$.map.map.tag",json_string)
            self.pretty_name = J_Path.get_Match ("$.map.map.pretty_name",json_string)
            self.short_name = J_Path.get_Match ("$.map.map.shortname",json_string)
            self.orientation = J_Path.get_Match ("$.map.map.orientation",json_string)
            self.game_mode = J_Path.get_Match ("$.map.game_mode",json_string)
            self.environment = J_Path.get_Match ("$.map.environment",json_string)
            self.attackers = J_Path.get_Match ("$.map.attackers",json_string)
            self.image_name = J_Path.get_Match ("$.map.image_name",json_string)
            
        except:
            logger.error ("Exception in PlayedMap")

class PreviousMap(PlayedMap):
    def parse_Json (self, json_string):
        try:
            self.name = J_Path.get_Match ("$.result.name", json_string)
            self.start = J_Path.get_Match ("$.result.start", json_string)
            self.end = J_Path.get_Match ("$.result.end", json_string)
        except:
            pass

class ActualMap(PlayedMap):
    def parse_Json (self, json_string):
        try:
            self.name = J_Path.get_Match ("$.result.current_map.map.map.name", json_string)
            unix_timestamp = J_Path.get_Match ("$.result.current_map.start", json_string)

            if unix_timestamp:
                self.start = datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%dT%H:%M:%S')
                
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

class MapHistory ():
    def __init__(self):
        self.json = None
        self.maps = []   

    def add_Json (self, json_string):
        self.json = json_string 

    def get_Last_Maps (self, cnt):
        try:

            if cnt > 0:
                names = J_Path.get_Matches (f"result[:{cnt}].name", self.json)

                if len (names):
                    return names
                else:
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

class Player():
    def parse_Json (self, json_string):
        try:
            self.name = J_Path.get_Match ("$..current_map..pretty_name", json_string, "End of Game")
            self.player_id = J_Path.get_Match ("$..current_map..game_mode", json_string)
        except:
            logger.error ("Exception in MapRotation")

class InGamePlayers ():
    def __init__(self):
        self.json = None

    def add_Json (self, json_string):
        self.json = json_string

    def get_Ingame_Player_Level (self, player_id):
        try:
            if self.json:
                level = J_Path.get_Match (f"result..players[?(@.player_id == '{player_id}')].level", self.json, "Not Found")

                if level != "Not Found":
                    return level
                else:
                    return None
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def is_Ingame_Player_VIP (self, player_id):
        try:
            if self.json:
                vip = J_Path.get_Match (f"result..players[?(@.player_id == '{player_id}')].is_vip", self.json, "Not Found")

                if vip and vip != "Not Found":
                    return True
                else:
                    return False
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
        

    def get_Ingame_Player_Name (self, player_id):
        try:
            if self.json:
                name = J_Path.get_Match (f"result..players[?(@.player_id == '{player_id}')].name", self.json, "Not Found")

                return name                
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
        
    def get_Ingame_Player_From_Fraction (self, fraction):
        try:
            if self.json:

                if fraction != "both":
                    players = J_Path.get_Matches (f"$.result.{fraction}[*]..players[*].player_id", self.json)
                else:
                    players = J_Path.get_Matches (f"$.result..players[*].player_id", self.json)

                return players                
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

class Players():
    def __init__(self):
        self.players = []
    
    def parse_Json (self, json_string):
        try:
            player_ids = J_Path.get_Matches ("$.result[*].player_id",json_string)

            logger.debug (player_ids)
            for item in player_ids:
                player = Player ()
                player.name = J_Path.get_Match ("$.result[?(@.player_id == \"" + item + "\")].name", json_string)
                player.player_id = J_Path.get_Match ("$.result[?(@.player_id == \"" + item + "\")].player_id", json_string)

                self.players.append (player)  
        except:
            logger.error ("Exception in MapRotation")
 
class ScoreboardMaps():
    def __init__(self):
        self.playedmaps = []
        
    def parse_Json (self, json_string, history=5):
        try:
            for i in range(0, history - 1):
                playedmap = PlayedMap ()
                temp = J_Path.get_Match (f"$.result.maps[{i}]",json_string)
                playedmap.parse_Json (temp)
                
                self.playedmaps.append (playedmap)

            return self.playedmaps 
        except:
            logger.error ("Exception in ScoreboardMaps")
            return None

class GameStatus():
    def __init__(self):
        self.num_allied_players = None
        self.num_axis_players = None
        self.allied_score = None
        self.axis_score = None   
        self.raw_time_remaining = None 

    def parse_Json (self, json_string):
        try:            
            self.num_allied_players = J_Path.get_Match ("$..num_allied_players", json_string)
            self.num_axis_players = J_Path.get_Match ("$..num_axis_players", json_string)
            self.allied_score = J_Path.get_Match ("$..allied_score", json_string)
            self.axis_score = J_Path.get_Match ("$..axis_score", json_string)
            self.raw_time_remaining = J_Path.get_Match ("$..raw_time_remaining", json_string)
        except:
            pass

class RecentLogs():
    def __init__(self):
        self.logs = []
        self.json = None

    def get_Timestamp (self, player_id):
        try:
            if self.json:
                timestamp = J_Path.get_Match (f"$.result.logs[?(@.player_id_1 == '{player_id}')].timestamp_ms", self.json, "0")

                return timestamp 
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def parse_Json (self, json_string):
        try:    
            self.json = json_string
            self.logs = J_Path.get_Matches ("$..logs[*].message", json_string)       
            logger.debug ("Message :" + str (self.logs))
        except:
            logger.error ("Exception in RecentLogs")      

class ServerStatus():
    def __init__(self):
        self.name = None
        self.short_name = None
        self.current_players = None

    def parse_Json (self, json_string):
        try:
            self.name = J_Path.get_Match (("$.result.name"),json_string)
            self.short_name = J_Path.get_Match ("$.result.short_name", json_string)
            self.current_players = J_Path.get_Match ("$.result.current_players", json_string)
        except:
            logger.error ("Exception in ServerStatus")

class MapRotation ():
    def __init__(self):
        self.maps = []

    def parse_Json (self, json_string):
        try:
            map_ids = J_Path.get_Matches ("$.result[*].id", json_string)

            for item in map_ids:
                map = Map ()
                map.id = item
                map.pretty_name = J_Path.get_Match ("$.result[?(@.id == \"" + item + "\")].pretty_name", json_string)
                map.environment = J_Path.get_Match ("$.result[?(@.id == \"" + item + "\")].environment", json_string)
                map.image_name = J_Path.get_Match ("$.result[?(@.id == \"" + item + "\")].image_name", json_string)
                self.maps.append (map)  
        except:
            logger.error ("Exception in MapRotation")

class MapsToVote ():
    def __init__(self):
            self.maps = []

    def parse_Json (self, json_string):
        try:
            map_ids = J_Path.get_Matches ("$.result[*].map.id",json_string)
            logger.info  ("Maps to vote: " + str (map_ids))

            for i in range (0, len (map_ids)):
                map = Map ()
                map.id = J_Path.get_Match ("$.result[" + str (i - 1) + "].map.id", json_string)
                map.pretty_name = J_Path.get_Match ("$.result[" + str (i - 1) + "].map.pretty_name", json_string)
                map.environment = J_Path.get_Match ("$.result[" + str (i - 1) + "].map.environment", json_string)
                map.image_name = J_Path.get_Match ("$.result[" + str (i - 1) + "].map.image_name", json_string)
                self.maps.append (map)  
        except:
            logger.error ("Exception in MapsToVote")

class Balance():
    def __init__(self, limits, weights):
        self.axis = []
        self.allies = []
        self.limits = limits
        self.weights = weights

    def calculate_Weighted_Sum(self, numbers, weights):
        # check whether the lists are the same length
        if len(numbers) != len(weights):
            logger.error ("The length of the number list and the weighting list must be the same.")
            return None
        else:
            # Multiply each number by its corresponding weighting and calculate the sum
            weighted_sum = sum(number * weight for number, weight in zip(numbers, weights))
            return weighted_sum

    def get_Group_and_Count(self, numbers, limits):
        # The limits list must be sorted
        limits.sort()
        
        # Add 0 as the starting point
        counts = []
        previous_limit = 0
        
        # Count for each group
        for limit in limits:
            count = sum(1 for number in numbers if previous_limit <= number < limit)
            counts.append(count)  # Füge die Zählung zur Liste hinzu
            previous_limit = limit
        
        # Count for the last group (limit to 500)
        count = sum(1 for number in numbers if previous_limit <= number <= 500)
        counts.append(count)  # Add the count of the last group to the list
        
        return counts

    def calculate_Balance (self):
        if len (self.axis) >= 1 and len (self.allies) >= 1:          
            axis = self.get_Group_and_Count (self.axis, self.limits)
            allies = self.get_Group_and_Count (self.allies, self.limits)

            axis_weight = self.calculate_Weighted_Sum (axis, self.weights)
            allies_weight = self.calculate_Weighted_Sum (allies, self.weights)

            allies_weight = self.calculate_Weighted_Sum (allies, self.weights)
            logger.debug ("Combat strength Axis: " + str (axis_weight) + " / Combat strength Allies: " + str (allies_weight))

            return axis_weight, allies_weight, axis, allies
        else:
            return 0, 0, [0] * (len (self.limits) + 1), [0] * (len (self.limits) + 1)
            
    def parse_Json (self, json_string):
        try:
            self.axis = J_Path.get_Matches ("$..axis..level", json_string)
            self.allies = J_Path.get_Matches ("$..allies..level", json_string)
           
            return self.axis, self.allies
        except:
            logger.error ("Exception while parsing json file: " + json_string)

class PlayerHistory ():
    def __init__(self):
        self.json = None

    def add_Json (self, json_string):
        self.json = json_string

    def get_Players_Name (self):
        try:
            if self.json:
                players = J_Path.get_Matches (f"$.result.players[*][player_id,names_by_match,first_seen_timestamp_ms,last_seen_timestamp_ms]", self.json)

                if players:
                    multi_array = [players[i:i+4] for i in range(0, len(players), 4)]
                    return multi_array
                else:
                    return None
            else:
                logger.error(f"No Json data")    

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def get_Total_Player_Count (self):
        try:
            total_player_count = J_Path.get_Match ("$..total", self.json)

            return total_player_count
        except:
            logger.error ("Exception in MapRotation")

    def get_Players (self):
        players = []
        try:
            player_ids = J_Path.get_Matches ("$.result.players[*].player_id", self.json)

            for item in player_ids:
                player = Player ()  
                player.name = J_Path.get_Match (f"$.result.players[*].names[?(@.player_id == '{item}')].name", self.json)
                player.player_id = item

                players.append (player)  

            return players

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

class PlayerProfile ():
    def __init__(self):
        self.json = None

    def add_Json (self, json_string):
        self.json = json_string

    def is_Watched (self):
        try:
            result = J_Path.get_Matches ("$.result..is_watched", self.json)

            return result

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def is_Banned (self):
        try:
            result = J_Path.get_Matches ("$.result..is_blacklisted", self.json)

            return result

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def is_Blacklisted (self):
        pass