import discord
import logging
import asyncio
import rcon.rcon as rcon
from typing import List
from datetime import datetime
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands


# get Logger for this modul
logger = logging.getLogger(__name__)

class Statistics (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  # Initialize the parent classes (DiscordBase and commands.Cog)
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
    
    @app_commands.command(name="player_stats", description="Get statistics of the player")
    @app_commands.describe(
        player="Choose a player",
    )
    async def player_stats(self, interaction: discord.Interaction, player: str):
        await interaction.response.send_message(f"Fetching stats for player_id: {player[0]}")

    @player_stats.autocomplete("player")
    async def player_autocomplete(self, interaction: discord.Interaction, player_name: str) -> List[app_commands.Choice[str]]:
        try:
            while self.in_Loop:
                await asyncio.sleep (1)
           
            self.in_Loop = True
            name = player_name
            multi_array = None

            if len (name) > 2:
                logger.info (f"Search query: {name}")
                multi_array = await self.query_Player_Database(name)
        
            if multi_array != None and len (multi_array) >= 1:
                result = [
                    app_commands.Choice(name=f"Last: {datetime.fromtimestamp(player[2]/1000).strftime('%Y-%m-%d')} - {", ".join(player[1])}"[:100], value=player[0])
                    for player in multi_array
                ]
                self.in_Loop = False
                return result
            else:
                self.in_Loop = False
                return []
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.in_Loop = False
            return []
        
    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

       