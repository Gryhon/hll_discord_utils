import discord
import logging
import asyncio
import time
import math
import threading
import rcon.model as model
import rcon.rcon as rcon
import lib.utils as utils
from lib.fuzzynamematcher import FuzzyNameMatcher
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from datetime import datetime
from discord.ext import commands
from discord import app_commands

# get Logger for this modul
logger = logging.getLogger(__name__)

class Inappropriate (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.last_check = None
        self.shutdown_event = asyncio.Event()
        self.inappropriate = FuzzyNameMatcher (config.get("rcon", 0, "inappropriate_name", 0, "threshold"))
        self.inappropriate.set_namelist (config.get("rcon", 0, "inappropriate_name", 0, "blacklist", default=[]))        
        self.bot = bot
        self.loop_started = False

    async def check_Name (self):
        try:
        
            server_status = await rcon.get_Server_Status ()

            if server_status != None:
                data = []

                payload = {
                    "end": 250,
                    "filter_action": ["CONNECTED"],
                    "filter_player": [],  
                    "inclusive_filter": "true"
                }

                if not self.last_check:
                    self.last_check = time.time()

                data = await rcon.get_Recent_Logs (payload, model.RecentLogs)
                last_check = time.time()

                players = await rcon.get_In_Game_Players ()

                for item in data.logs:
                    player_id = utils.get_last_parenthesis_content(item)
                    
                    name = players.get_Ingame_Player_Name (player_id)

                    event_time = data.get_Timestamp (player_id)

                    if int (event_time/1000) > int (self.last_check):                
                        trashhold, finding = self.inappropriate.get_match (name)

                        if trashhold >= config.get("rcon", 0, "inappropriate_name", 0, "threshold", default=0.75):
                            logger.error (f"Checked: Name: {name} Trashhold: {trashhold} Finding: {finding}")
                            # ToDo: Send message to discord and admin        
                        else:
                            logger.debug (f"Checked: Name: {name} Trashhold: {trashhold} Finding: {finding}")               
                            
                self.last_check = last_check
        
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")


    async def check_Players (self, players):
        try:
            for player in players:
                trashhold, finding = self.inappropriate.get_match (player.name)

                if trashhold >= config.get("rcon", 0, "inappropriate_name", 0, "threshold", default=0.75):
                    logger.error (f"Checked: Name: {player.name} Trashhold: {trashhold} Finding: {finding}")
                    # ToDo: Send message to discord and admin
                #else:
                #    logger.info (f"Checked: Name: {player.name} Trashhold: {trashhold} Finding: {finding}")                                           

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def check_Ingame_Player (self):
        try:
            players = await rcon.get_Players ()

            await self.check_Players (players.players)
                  
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def check_History_Player (self):
        try:
            
            page = 1
            payload ={"page_size": 100, "page": page}

            players = await rcon.get_Player_History (payload)

            cnt = players.get_Total_Player_Count ()

            pages = math.ceil(cnt / 50)

            logger.info (f"Start verify {cnt} player on {pages} pages.")

            for i in range(1, pages):
                payload["page"] = i
                players = await rcon.get_Player_History (payload)
                await self.check_Players (players.get_Players ())
                logger.info (f"Checking player on page {i:04} of {pages} pages.")

                if self.shutdown_event.is_set():
                    logger.info (f"Checking player aborted.")
                    break

            logger.info (f"End checking.")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def background_task(self):
        last_execution = 0

        await self.check_Ingame_Player ()

        #def run_history_player():
        #    asyncio.run(self.check_History_Player())
        
        #thread = threading.Thread(target=run_history_player)
        #thread.start()
        #logger.info("check_History_Player läuft jetzt im Hintergrund")
    
        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or last_execution == 0:
                try:
                    await self.check_Name()
            
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")

                last_execution = current_time

            await asyncio.sleep (5)

        #logger.info("Warte darauf, dass der Hintergrund-Thread beendet wird...")
        #thread.join()
        #logger.info("Hintergrund-Thread wurde beendet.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

        
