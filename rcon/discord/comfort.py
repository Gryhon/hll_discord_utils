import discord
import logging
import asyncio
import time
import rcon.model as model
import rcon.rcon as rcon
from typing import List
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta


# get Logger for this modul
logger = logging.getLogger(__name__)

class SetAfterGameMessage(discord.ui.Modal, title="Configure 'After Game Message' function"):
    def __init__(self):
        super().__init__()
                
        self.add_item(discord.ui.TextInput(label="Enter your after game message", 
                                           placeholder="Enter your after game text", 
                                           default=config.get("rcon", 0, "comfort_functions", 0, "after_game_message", 0, "message", default=""), 
                                           style=discord.TextStyle.paragraph, 
                                           required=True))
                
        self.result = None

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.result = self.children[0].value
            logger.info(f"Modal submitted with: {self.result}")

            config.set("rcon", 0, "comfort_functions", 0, "after_game_message", 0, "message", self.result)
            config.save_Config()

            response_text = f"✅ After game message is saved in config file."
            
            await interaction.response.send_message(response_text, ephemeral=True)

            self.result = True

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.result = False

class AfterGameMessage (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False
        self.game_last_active = None
        self.game_active = None

    async def background_task(self):
        try:
            while not self.shutdown_event.is_set():
                await self.do_After_Game_Message()
                await asyncio.sleep (5)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        await asyncio.sleep (5)

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
       
    async def do_After_Game_Message (self):
        try:
            game_active = await self.get_Game_State()

            if self.game_last_active == True and game_active == False:

                self.game_last_active = game_active

                logger.info ("Game ended, sending after game message...")

                after_game_message = config.get("rcon", 0, "comfort_functions", 0, "after_game_message", 0, "message", default="")
                
                if after_game_message:
                    players = await rcon.get_Players ()

                    for player in players.players: 
                        payload = {"player_id": str (player.player_id) , "message": str (after_game_message)}   

                        if not (config.get("rcon", 0, "comfort_functions", 0, "dryrun")) or player.player_id in config.get("rcon", 0, "comfort_functions", 0, "probands"):
                            logger.info("After game message: " + str (payload)) 
                            await rcon.send_Player_Message (payload)
                        else:
                            logger.info("Dry run after game message: " + str (payload)) 
                            await asyncio.sleep (0.5)

            elif self.game_last_active == False and game_active == True:
                self.game_last_active = game_active
                logger.info ("Game started, resetting after game message state.")

            elif self.game_last_active == None:
                logger.warning ("No game state information available. Setting game_active to False.")
                self.game_last_active = False
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    @app_commands.command(name="configure_after_game_message", description="Change the after game message")
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_after_game_message (self, interaction: discord.Interaction):
        try:
            modal = SetAfterGameMessage ()
            await interaction.response.send_modal(modal)
            
            # wait until the modal is closed
            await modal.wait()

                        # Ergebnis zurückgeben
            register = modal.result
            logger.info(f"Modal submitted with after game message: {register}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await interaction.response.send_message("An error occurred while trying to unregister the user.",  ephemeral=True)  

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (AfterGameMessage) started")

class BroadcastMessage (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def query_Player_Database(self, query: str) -> List[str]:
        return await rcon.search_Players(query)

    async def send_Broadcast_Message (self, message, players):
        try:
            for player_id in players: 
                payload = None

                payload = {"player_id": str (player_id) , "message": str (message) }   

                if not (config.get("rcon", 0, "comfort_functions", 0, "dryrun")) or player_id in config.get("rcon", 0, "comfort_functions", 0, "probands"):
                    logger.debug("Vote message: " + str (payload)) 
                    await rcon.send_Player_Message (payload)
                else:
                    logger.info("Dry run broadcast message: " + str (payload)) 
                    await asyncio.sleep (0.5) 

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)
            
    @app_commands.command(name="broadcast_message", description="Broadcast message to players")
    @app_commands.describe(
        fraction="Choose the target audience",
        action="Choose a message you would like to broadcast",
        free_text="Provide your custom message (only for 'Free text' option)"
    )
    @app_commands.choices(fraction=[
        app_commands.Choice(name="Axis", value="axis"),
        app_commands.Choice(name="Allies", value="allies"),
        app_commands.Choice(name="Both fractions", value="both"),
    ])
    @app_commands.choices(action=[
        app_commands.Choice(name="Balance", value="balance"),
        app_commands.Choice(name="The server will be closed after this game", value="shutdown"),
        app_commands.Choice(name="Only fight over the 3rd objective while seeding", value="seeding1"),
        app_commands.Choice(name="No garrisons beyond zones E and F may be destroyed", value="seeding2"),
        app_commands.Choice(name="Free text", value="text"),
    ])
    async def broadcast_message(self, interaction: discord.Interaction, fraction: app_commands.Choice[str], action: app_commands.Choice[str], free_text: str = None):
        fraction_value = fraction.value
        action_value = action.value

        message = None

        if action_value == "balance":
            message = "Please balance the server!"

        elif action_value == "shutdown":
            message = "Server will be shutdown after this game. \nThank you for your understanding. \n\nWe look forward to seeing you again!"

        elif action_value == "seeding1":
            message = "Only fight over the 3rd objective while seeding!"

        elif action_value == "seeding2":
            message = "No garrisons beyond zones E and F may be destroyed!"
            

        elif action_value == "text":
            if not free_text:
                await interaction.response.send_message("You selected 'Free text', but no custom message was provided!", ephemeral=True)
                return
            
            message = free_text
            
        ingame = await rcon.get_In_Game_Players ()
        players = ingame.get_Ingame_Player_From_Fraction (fraction_value)

        asyncio.create_task(self.send_Broadcast_Message(message, players))
     
        logger.info(f"Broadcast message by {interaction.user.name} to {fraction_value} {'fractions' if fraction_value == 'both' else ''}: {message.replace("\n", "")}")
        await interaction.response.send_message(f"Broadcast message to {fraction_value} {'fractions' if fraction_value == 'both' else ''}:\n{message}")        

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (BroadcastMessage) started")

class AutoUnban (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False
        self.last_check = None

    async def do_Auto_Unban (self):
        try:
            if self.last_check == None:
                now = datetime.now()
                self.last_check = now - timedelta(minutes=90)
                logger.info (f"Initial last check time set to {self.last_check}")
                        
            payload = {"action": f"ADMIN BANNED",
                       "from_": f"{self.last_check}",
                       "time_sort": "desc"}
            log_items = await rcon.get_Historical_Logs (payload)

            self.last_check = datetime.now()

            logger.info (f"Auto unban check from {self.last_check}, found {log_items.json} ban log items.")
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
        

    async def background_task(self):
        last_execution = 0

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or last_execution == 0:
                
                try:
                    await self.do_Auto_Unban()

                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
            
                last_execution = current_time

            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (AutoUnban) started")