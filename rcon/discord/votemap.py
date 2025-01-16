import discord
import logging
import asyncio
import random
import time
import re
import rcon.model as model
import rcon.rcon as rcon
from typing import List
from dateutil.parser import parse
from rcon.discord.discordbase import DiscordBase 
from discord.ext import commands
from discord import app_commands
from lib.config import config
from datetime import timedelta, datetime


# get Logger for this modul
logger = logging.getLogger(__name__)

class VoteMap(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False
        self.do_map_vote = False
        self.vote_map_active = True
        self.reset_Vote_Variables()
        self.shutdown_event = asyncio.Event()
        self.seeding_message = ("\nImportant:\n\n"
                                "    Vote function available when\n"
                                "        there are more than\n\n"
                               f"          ** {config.get("rcon", 0, "map_vote", 0, "activate_vote")} Player **\n\n"
                                "          on the server!\n\n")
        self.pause_message = ("\n\n"
                            "       Vote function is paused!\n\n"
                            "   We will inform you in the channel\n"
                            "  when the function is anabled again.\n\n"
                            "             Stay tuned!\n\n")
        self.vote_channel_id = config.get("rcon", 0, "map_vote", 0, "vote_channel_id") 
        self.vote_channel = None   
        self.loop_started = False  

    def reset_Vote_Variables(self):
        self.vote_msg = None
        self.vote_msg_id = None
        self.seeding_msg = None
        self.game_start = None
        self.game_active = None
        self.vote_active = False
        self.game_id = None
        self.current_map = None
        self.Maps = None
        self.vote_results = []

        self.last_execution = None
        self.send_seeding_message = True
        self.seeded = False

    async def send_Pause_Message (self):
        try:
            message = (
                f"""
                    ```  {self.pause_message} ```
                """
            )
            self.seeding_msg = await self.vote_channel.send(message)
            logger.info ("Server is paused message ID: " + str (self.seeding_msg.id))

        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def send_Seeding_Message (self):
        try:
            message = (
                f"""
                    ```  {self.seeding_message} ```
                """
            )
            self.seeding_msg = await self.vote_channel.send(message)
            logger.info ("Server is seeding message ID: " + str (self.seeding_msg.id))

        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def remove_Seeding_Message (self, history=False):
        try:
            if not history and self.seeding_msg:
                await self.seeding_msg.delete() 
                logger.info ("Delete old seeding message ID: " + str (self.seeding_msg.id))

            elif history:

                async for msg in self.vote_channel.history(limit=100):  
                    if msg.author == self.bot.user:
                        if self.seeding_message in msg.content:
                            logger.info ("Delete old Message ID: " + str (msg.id))
                            await msg.delete()
                            
                        await asyncio.sleep(1)

        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def get_Game_State (self):
        try:
            data = []

            payload = {
                "end": 10000,
                "filter_action": ["MATCH ENDED", "MATCH START"],
                "filter_player": [],  
                "inclusive_filter": "true"
            }

            data = await rcon.get_Recent_Logs (payload, model.RecentLogs)

            if (not self.game_active or self.game_active == None) and len (data.logs) and "MATCH START" in data.logs[0]:
                logger.info ("Game status: " + data.logs[0])
                self.game_active = True

            elif (self.game_active or self.game_active == None) and len (data.logs) and "MATCH ENDED" in data.logs[0]:
                logger.info ("Game status: " + data.logs[0])
                self.game_active = False

            elif self.game_active == None:
                self.game_active = False
                logger.warning ("No game status information available.")

            return self.game_active
        
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def clear_All_Messages (self, expect=None, interaction=True):
        try:
            async for msg in self.vote_channel.history(limit=100):  

                if msg.author == self.bot.user:

                    if not msg.interaction_metadata or msg.interaction_metadata and interaction:
                        if not expect or (expect and expect != msg.id):
                            await msg.delete() 
                            logger.info ("Delete old message ID: " + str (msg.id))
                            
                        await asyncio.sleep(1)

        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def get_Maps_from_Vote (self):
        try:
            maps = []

            if self.vote_msg:
                all_maps = await rcon.get_Maps ()
                
                for item in self.vote_msg.poll.answers:
                    maps.append (item.text)
                
                logger.info (f"Get maps from poll: {maps}")

                all_maps.get_Maps_from_PrettyName (maps)

                return all_maps

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    async def check_Active_Vote (self):
        try:
            self.current_map = await rcon.get_Current_Map ()

            if self.current_map:
                self.game_start = parse(self.current_map.start).timestamp()
                self.vote_msg_id = self.select_Last_Map_Vote (self.game_start)

            if self.vote_msg_id:
                # check if the discord message exists
                self.vote_msg = await self.vote_channel.fetch_message (self.vote_msg_id)

                if self.vote_msg and not self.vote_msg.poll.is_finalised():
                    await self.clear_All_Messages (self.vote_msg_id)
                    self.Maps = await self.get_Maps_from_Vote ()
                    await self.set_Vote_Result ()
                    await self.update_All_Voter ()

                    return True
                else:
                    logger.error("Discord poll message does not exist.")
                    # delete legacy database entry
                    await self.clear_All_Messages ()
                    self.delete_Map_Vote (self.game_start)
                    self.vote_msg_id = None
                    self.vote_msg = None
                    await self.clear_All_Messages ()
                    return False
            else: 
                await self.clear_All_Messages ()
                return False
            
        except discord.NotFound:
            logger.error("Discord poll message does not exist.")
            # delete legacy database entry
            await self.clear_All_Messages ()
            self.delete_Map_Vote (self.game_start) 
            return False
        
        except discord.Forbidden:
            logger.error("Permission denied to fetch message.")
            return False
        
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    async def get_Results (self):
        answers = []

        try:
            self.vote_results = []

            result = await self.vote_channel.fetch_message (self.vote_msg_id)

            for item in result.poll.answers:
                voters = [voter async for voter in item.voters()]

                item = [item.text, item.vote_count, voters]
                answers.append (item)
                self.vote_results.append (item)

            # Sort answers by vote_count (descending)
            sorted_answers = sorted(answers, key=lambda x: x[1], reverse=True)
            return sorted_answers

        except discord.NotFound:
            logger.error("Message does not exist.")
            return None
        except discord.Forbidden:
            logger.error("Permission denied to fetch message.")
            return None
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
    
    async def get_Vote_Result (self, maps):
        try:
            candidates = []
            vote_count = -1
            vote_result = None
            vote = ""

            for item in maps:
                if item [1] >= vote_count:
                    vote_count = item [1]
                    candidates.append (item)    

            if len (candidates) == 1:
                vote_result = candidates [0][0]

            elif len (candidates) > 1:
                if vote_result and not any(vote_result in sublist for sublist in candidates):
                    i = random.randint(0, len (candidates) - 1)
                    vote_result = candidates [i][0]

                elif vote_result == None:
                    i = random.randint(0, len (candidates) - 1)
                    vote_result = candidates [i][0]
            else:
                logger.error ("Vote result is empty")    

            for map in self.Maps.maps:
                if map.pretty_name == vote_result:
                    vote = map.id

            logger.debug ("Vote Result: " + vote)

            return vote
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def set_Map (self, map):
        try:
            # Check if map is a string or a dictionary.
            if isinstance(map, str):
                payload = {"map_names": [map]}

            elif isinstance(map, list):
                payload = {"map_names": map}

            else:
                raise ValueError("Parameter 'map' must be a string or a dictionary.")
            
            if not (config.get("rcon", 0, "map_vote", 0, "dryrun")):
                logger.info ("Set vote result: " + str (map))
                await rcon.set_Map_Rotation (payload)
            else:
                logger.info ("Dry run map: " + str (map) + " not set!")
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
    async def set_Vote_Result (self):
        try:
            maps = await self.get_Results ()
            map = await self.get_Vote_Result (maps)
            await self.set_Map (map)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def update_All_Voter (self):
        try:
            logger.info ("Update all voter")
            self.deleter_all_Voter (self.game_start)

            for item in self.vote_results:
                voters = item[2]

                for voter in voters:
                    self.insert_Voter (self.game_start, voter.id, voter.name, item[0])

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def get_Random_Items(self, input_list, num_entries):
        try:

            if num_entries > len(input_list):
                raise ValueError("The number of entries cannot be greater than the list size.")
        
            return random.sample(input_list, num_entries)
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
        
    async def enforce_Match (self, liste1, liste2, match_count):
        try:
            list = []

            matches = set(liste1) & set(liste2)

            if len(matches) < match_count:
                list = await self.get_Random_Items(liste1, len (liste1) - match_count)
                enforced = await self.get_Random_Items(liste2, match_count)
                logger.info (f"No match! Injection is enforced!")

                list.extend (enforced)
            else:
                list = liste1
           
            return list
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []
        
    async def get_Maps_To_Vote (self):
        try:
            result = []
            last_maps = []
            blacklist = []

            modes = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "battle_mode")
            blacklist = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "blacklist_maps")

            last_maps = await rcon.get_Map_History (config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "exclude_played_maps"))

            if last_maps is not None:
                blacklist.extend (last_maps)

            logger.info (f"Blacklist: {blacklist}")

            all_maps = await rcon.get_Maps ()

            day_cnt = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "day")

            if day_cnt > 0:
                list = all_maps.get_Map_Names (["day"], modes, blacklist)
                list = await self.get_Random_Items (list, day_cnt)
                result.extend (list)
                logger.info (f"{day_cnt} random day maps: {list}")

            night_cnt = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "night")

            if night_cnt > 0:
                list = all_maps.get_Map_Names (["night"], modes, blacklist)
                list = await self.get_Random_Items (list, night_cnt)
                result.extend (list)
                logger.info (f"{night_cnt} random night maps: {list}")

            enforced_cnt = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "enforce")
            enforced_list = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "enforced_maps")

            if enforced_cnt > 0:
                result = await self.enforce_Match (result, enforced_list, enforced_cnt)

            wildcard_cnt = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "wildcard")

            if wildcard_cnt > 0:
                wildcard_mode = config.get("rcon", 0, "map_vote", 0, "map_pool", 0, "wildcard_mode")
                list = all_maps.get_Map_Names (["night", "day"], wildcard_mode, blacklist)

                list = await self.get_Random_Items (list, wildcard_cnt)
                result.extend (list)
                logger.info (f"{wildcard_cnt} random wildcard maps: {list}")

            random.shuffle(result)
            logger.info (f"Map proposal: {result}")

            all_maps.get_Maps_from_ID (result)

            return all_maps
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    async def start_Vote (self):
        try:
            self.Maps = await self.get_Maps_To_Vote ()
            self.vote_active = await self.check_Active_Vote ()

            if not self.vote_active:
                topic = "Vote for the next map:"

                await self.get_Game_State ()

                poll = discord.Poll (question=discord.PollMedia(topic, emoji=None), duration=timedelta(hours=2), multiple=False)

                for item in self.Maps.maps:
                    logger.debug ("Add map to vote: " + str (item.pretty_name))
                    poll.add_answer (text=item.pretty_name, emoji=None)

                logger.debug ("Poll: " + str (poll))

                self.vote_msg = await self.vote_channel.send(poll=poll)
                self.vote_msg_id = self.vote_msg.id
                self.insert_Map_Vote (self.vote_msg.id, self.game_start)

                logger.info ("Vote message ID: " + str (self.vote_msg.id))

                await self.send_Vote_Message ()

            else:
                self.vote_msg = await self.vote_channel.fetch_message (self.vote_msg_id)

            self.vote_active = True

        except discord.NotFound:
            logger.error("Message does not exist.")
            self.vote_active = False
        except discord.Forbidden:
            logger.error("Permission denied to fetch message.")
            self.vote_active = False
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
            self.vote_active = False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.vote_active = False

    async def stop_Vote(self):
        try:
            await self.vote_msg.poll.end ()
            await self.set_Vote_Result ()
            self.vote_active = False

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.vote_active = False
            
    async def get_User_Name(self, user_id):
        try:
            user = await self.bot.fetch_user(user_id)
            return user.name
        
        except discord.NotFound:
            logger.info("User not found.")
        except discord.HTTPException:
            logger.info("An error occurred while fetching the user.")

    async def send_Vote_Message(self, reminder=False):
        try:
            # Check if map vote system is enabled
            if not config.get("rcon", 0, "map_vote", 0, "enabled", default=True):
                logger.info("Map vote system is disabled in config")
                return

            # Check if reminders are disabled (0 means disabled)
            if reminder and config.get("rcon", 0, "map_vote", 0, "reminder", default=0) == 0:
                logger.info("Vote reminders are disabled in config (reminder = 0)")
                return

            # Check if stealth vote is enabled
            if config.get("rcon", 0, "map_vote", 0, "stealth_vote", default=False):
                logger.info("Stealth vote is enabled, skipping reminders")
                return

            Text = ""
            voters = None

            if reminder and self.game_start:
                voters = self.select_T17_Voter(self.game_start)

            if not reminder:
                for map in self.Maps.maps:
                    Text += str(map.pretty_name) + "\n"

            elif reminder and len(self.vote_results):
                for map in self.vote_results:
                    Text += str(map[0]) + " - " + str(map[1]) + " votes\n"

            players = await rcon.get_Players()
            
            for player in players.players: 
                # Skip if player has voted
                if voters is not None and player.player_id in voters:
                    logger.info(f"Skipping reminder for {player.name} - already voted")
                    continue

                # Skip if player is registered and remind_registered_users is false
                if not config.get("rcon", 0, "map_vote", 0, "remind_registered_users", default=False):
                    reg = self.select_T17_Voter_Registration(player.player_id)
                    if reg:
                        logger.info(f"Skipping reminder for registered user {player.name}")
                        continue

                data = {
                    "player_id": str(player.player_id), 
                    "message": config.get("rcon", 0, "map_vote", 0, "vote_header") + "\n\n" + str(Text)
                }   
                        
                if not config.get("rcon", 0, "map_vote", 0, "dryrun", default=False):
                    logger.debug(f"Sending vote message to {player.name}")
                    await rcon.send_Player_Message(data)

        except Exception as e:
            logger.error(f"Error in send_Vote_Message: {e}")
            
    async def check_Origin_Map_Rotation (self):
        try:
            map_rotation = await rcon.get_Map_Rotation ()

            if len (map_rotation.maps) > 1:
                maps = "|".join(map.id for map in map_rotation.maps)

                rotation = self.select_Key_Value ("Origin_Map_Rotation")

                if rotation == None:
                    self.insert_Key_Value ("Origin_Map_Rotation", maps)
                    logger.info ("Insert origin map rotation")
                else:
                    set1 = set(maps.split("|"))
                    set2 = set(rotation.split("|"))

                    if set1 != set2:
                        self.update_Key_Value ("Origin_Map_Rotation", maps)
                        logger.info ("Update origin map rotation")

            if (self.seeded == False and len (map_rotation.maps) == 1) or (self.do_map_vote == False and len (map_rotation.maps) == 1):
                rotation = self.select_Key_Value ("Origin_Map_Rotation")
                await self.set_Map (rotation.split("|"))

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
   
    async def do_Map_Vote (self):
        try:
            self.do_map_vote = True

            await self.get_Game_State ()
            server_status = await rcon.get_Server_Status ()
            
            if server_status is not None:
                if server_status.current_players >= config.get("rcon", 0, "map_vote", 0, "activate_vote") and not self.seeded:
                    logger.info (f"Server reached {config.get("rcon", 0, "map_vote", 0, "activate_vote")} player and vote map is active!")
                    self.seeded = True
                    await self.check_Origin_Map_Rotation ()

                elif server_status.current_players <= config.get("rcon", 0, "map_vote", 0, "dectivate_vote"):
                    if self.seeded:
                        logger.info (f"Server drops below or equal to {config.get("rcon", 0, "map_vote", 0, "dectivate_vote")} player and vote map is now deactive!")
                    
                    await self.check_Origin_Map_Rotation ()

                    self.seeded = False
                    
            if self.seeded:
                if self.game_active and not self.vote_active:
                    logger.info ("Vote is being started...")
                    
                    await self.remove_Seeding_Message (True)
                    await self.start_Vote ()
                    await self.set_Vote_Result ()

                    if not config.get("rcon", 0, "map_vote", 0, "stealth_vote"):
                        await self.send_Vote_Message ()

                    self.last_execution = time.time()

                # stop vote
                elif not self.game_active and self.vote_active:
                    logger.info ("Game over vote is being stopped...")

                    await self.stop_Vote ()
                    self.vote_active = False
                    self.last_execution = None

                # reminder
                elif self.game_active and self.vote_active:
                    if not self.last_execution:
                        self.last_execution = time.time()

                    current_time = time.time()

                    if (current_time - self.last_execution) >= (config.get("rcon", 0, "map_vote", 0, "reminder") * 60):
                        logger.info("Send reminder")
                        if not config.get("rcon", 0, "map_vote", 0, "stealth_vote"):
                            await self.send_Vote_Message(True)
                        self.last_execution = current_time

                if not self.send_seeding_message:
                    self.send_seeding_message = True

            else:
                if self.send_seeding_message:
                    await self.clear_All_Messages ()
                    await self.send_Seeding_Message ()

                    self.vote_active = False
                    self.send_seeding_message = False

            self.do_map_vote = False
            
        except Exception as e:
            logger.error(f"Error in do_Map_Vote: {e}")

    async def background_task(self):
        try:
            self.vote_channel = self.bot.get_channel(self.vote_channel_id)

            while not self.shutdown_event.is_set():            
                
                if self.vote_map_active:
                    try:
                        await self.do_Map_Vote()

                    except Exception as e:
                        self.reset_Vote_Variables()

                        logger.error(f"Unexpected error: {e}")

                await asyncio.sleep (5)

        except asyncio.CancelledError:
            logger.info ("Vote map is being stopped...")  

    @app_commands.command(name="map_vote", description="Manage the map vote")
    @app_commands.describe(action="Choose an action for the map vote")
    @app_commands.choices(action=[
        app_commands.Choice(name="resume", value="resume"),
        app_commands.Choice(name="pause", value="pause"),
        app_commands.Choice(name="status", value="status"),
    ])
    async def mapvote_command(self, interaction: discord.Interaction, action: str):

        if action == "pause" and self.vote_map_active:
            self.vote_map_active = False       

            logger.info (f"Vote map paused by {interaction.user.name}!")    
            await interaction.response.send_message(f"Vote map paused by {interaction.user.name}!", ephemeral=False)
            
            while self.do_map_vote == True:
                logger.info ("Method do_Map_Vote () is in execution")
                await asyncio.sleep (1)   

            if self.seeded:
                await self.stop_Vote ()
                await self.check_Origin_Map_Rotation ()

            await self.clear_All_Messages (None, False)                
            await self.send_Pause_Message ()

            self.reset_Vote_Variables()

        elif action == "resume" and not self.vote_map_active:
            self.vote_map_active = True

            logger.info (f"Vote map started by {interaction.user.name}!")      

            await interaction.response.send_message(f"Vote map started by {interaction.user.name}!")

        elif action == "status" and self.vote_map_active:
            logger.info (f"Get status of Vote map by {interaction.user.name}!")
            await interaction.response.send_message(f"Vote map is running")
        
        elif action == "status" and not self.vote_map_active:
            logger.info (f"Get status of Vote map by {interaction.user.name}!")
            await interaction.response.send_message(f"Vote map is stopped") 

        else:
            await interaction.response.send_message(f"Map vote status: {action} called by {interaction.user.name}")
  
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

    @commands.Cog.listener()
    async def on_raw_poll_vote_add(self, payload):
        try:
            
            if (self.vote_msg_id == payload.message_id) and (self.game_active and self.vote_active):
                answer = payload.answer_id
                voter = await self.bot.fetch_user(payload.user_id)

                logger.info (voter.name + " voted for " + self.vote_msg.poll.answers[answer-1].text)
                self.insert_Voter (self.game_start, voter.name, voter.id, self.vote_msg.poll.answers[answer-1].text)

                await self.set_Vote_Result ()
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def query_Player_Database(self, query: str) -> List[str]:
        try:
            if len (query) > 1:       
                payload ={"page_size": 25, "page": 1, "player_name": query}

                result = await rcon.get_Player_History (payload)
                player = result.get_Players_Name ()

                if player is not None and len (player):
                    return player[:25]
                else:
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    @commands.Cog.listener()
    async def on_raw_poll_vote_remove(self, payload):
        try:
            if (self.vote_msg_id == payload.message_id) and (self.game_active and self.vote_active):
                answer = payload.answer_id
                name = await self.get_User_Name (payload.user_id)

                logger.info (name + " removed vote for " + self.vote_msg.poll.answers[answer-1].text)
                self.deleter_Voter (self.game_start, name, self.vote_msg.poll.answers[answer-1].text)
                
                await self.set_Vote_Result ()

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
