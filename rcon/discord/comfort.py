import discord
import logging
import asyncio
import rcon.rcon as rcon
from typing import List
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands


# get Logger for this modul
logger = logging.getLogger(__name__)

class Comfort (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def query_Player_Database(self, query: str) -> List[str]:
        try:
            if len (query) > 1:       
                payload ={"page_size": 25, "page": 1, "player_name": query}

                result = await rcon.get_Player_History (payload)
                players = result.get_Players_Name ()

                if players != None and len (players):
                    return players[:25]
                else:
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

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

    '''
    async def calculate_Mils (self, distance, min_distance, max_distance, min_mils, max_mils):
        mil = (((distance - min_distance) / (max_distance - min_distance)) * (min_mils - max_mils) + max_mils)
        logger.debug (f"Calculated Mil value for distance {distance} = {mil}")
        return round (mil)
    '''

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
            logger.info("Background task started")


        