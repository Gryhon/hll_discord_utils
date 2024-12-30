import discord
import logging
import asyncio
import time
import rcon.model as model
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from datetime import datetime
from discord.ext import commands
from discord import app_commands

# get Logger for this modul
logger = logging.getLogger(__name__)

class AutoLevel (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.last_check = None
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.lvl_cap_active = True
        self.loop_started = False

    def get_last_parenthesis_content(self, text):
        # Den Text von hinten durchgehen
        open_paren = None
        close_paren = None
        for i in range(len(text) - 1, -1, -1):
            if text[i] == ')':
                close_paren = i
            elif text[i] == '(':
                open_paren = i
                if close_paren is not None:
                    # Den Inhalt zwischen den Klammern extrahieren
                    return text[open_paren + 1:close_paren]
        
        return None  # Falls keine Klammern gefunden werden

    async def kick_Player (self, player_name, player_id, reason, comment):
        try:
            payload = {
                "player_name": player_name,
                "player_id": player_id,
                "reason": reason,
                "comment": comment
            }
            
            if not (config.get("rcon", 0, "auto_level", 0, "dryrun")):
                logger.debug (f"Kick Player: {player_name} ")
                await rcon.kick_Player (payload)
            else:
                logger.info (f"Dry run Kick Player: {player_name} ID: {player_id}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def check_Min_Level (self):
        try:
            min_level = config.get("rcon", 0, "auto_level", 0, "min_level")
            player_count = config.get("rcon", 0, "auto_level", 0, "player_count")
            lvl_bug_enabled = config.get("rcon", 0, "auto_level", 0, "levelbug_enabled")

            server_status = await rcon.get_Server_Status ()

            if server_status != None and server_status.current_players >= player_count:
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
                    player_id = self.get_last_parenthesis_content(item)
                    
                    level = players.get_Ingame_Player_Level (player_id)
                    vip = players.is_Ingame_Player_VIP (player_id)
                    name = players.get_Ingame_Player_Name (player_id)

                    event_time = data.get_Timestamp (player_id)

                    if int (event_time/1000) > int (self.last_check):                 
                        if level == None or (level < min_level and not vip):
                            if level == None or level > 1 and lvl_bug_enabled or not lvl_bug_enabled:
                                logger.info (f"Kick: {item} Level: {str (level)} VIP: {vip}")
                                reason = eval(f"f'''{config.get("rcon", 0, "auto_level", 0, "kick_message")}'''") 
                                await self.kick_Player (name, player_id, reason, "Auto Level")
                            else:
                                logger.info (f"Passed by lvl 1 Bug: {item} Level: {str (level)} VIP: {vip}")
                        else:
                            logger.info (f"Passed: {item} Level: {str (level)} VIP: {vip}")
                            
                self.last_check = last_check
        
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def background_task(self):
        last_execution = 0

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if self.lvl_cap_active and current_time - last_execution >= 60 or last_execution == 0:
                
                try:
                    await self.check_Min_Level()

                except Exception as e:
                    logger.error(f"Unexpected error: {e}")

                last_execution = current_time

            await asyncio.sleep (5)

    @app_commands.command(name="level_cap", description="Adaptive Level Cap")
    @app_commands.describe(action="Choose an action for the map vote")
    @app_commands.choices(action=[
        app_commands.Choice(name="pause", value="pause"),
        app_commands.Choice(name="resume", value="resume"),
        app_commands.Choice(name="status", value="status"),
    ])
    async def level_cap_command(self, interaction: discord.Interaction, action: str):
        
        if action == "pause":
            logger.info (f"Adaptive level cap paused by {interaction.user.name}!")    
            await interaction.response.send_message(f"Adaptive level cap paused by {interaction.user.name}!")

            self.lvl_cap_active = False        

        elif action == "resume":
            logger.info (f"Adaptive level cap resumed by {interaction.user.name}!")      
            await interaction.response.send_message(f"Adaptive level cap resumed by {interaction.user.name}!")

            self.last_check = time.time()
            self.lvl_cap_active = True

        elif action == "status" and self.lvl_cap_active:
            logger.info (f"Get status of Adaptive level cap by {interaction.user.name}!")
            await interaction.response.send_message(f"Adaptive level cap is running")
        
        elif action == "status" and not self.lvl_cap_active:
            logger.info (f"Get status of Adaptive level cap by {interaction.user.name}!")
            await interaction.response.send_message(f"Adaptive level cap is paused")    

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")