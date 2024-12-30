import discord
import logging
import asyncio
import pytz
import time
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from datetime import datetime
from discord.ext import commands
from discord import app_commands

# get Logger for this modul
logger = logging.getLogger(__name__)

class ServerStatus(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.webhook_url = config.get("rcon", 0, "server_status", 0, "webhook")
        self.webhook = discord.SyncWebhook.from_url(self.webhook_url)
        self.msg_id = self.select_Message_Id (__name__)
        self.shutdown_event = asyncio.Event()
        self.bot = bot 
        self.loop_started = False

    async def update_message (self):
        current_map, next_map, game_status = await rcon.get_Game_State ()
        server_status = await rcon.get_Server_Status ()

        if current_map:            
            stats = discord.Embed(
                title=server_status.name,
                description="\n",
                color=discord.Color.green(),
                url=config.get("rcon", 0, "stats_url")
                )
                            
            stats.add_field(name="Current Map", value=current_map.pretty_name, inline=True)
            stats.add_field(name="Next Map", value=next_map.pretty_name, inline=True) 
            stats.add_field(name="Time Remaining", value=game_status.raw_time_remaining, inline=True)
            stats.add_field(name="\u200b", value="", inline=False)
            stats.add_field(name="Allies vs Axis", value=str (game_status.num_allied_players) + " - " + str (game_status.num_axis_players), inline=True)
            stats.add_field(name="Match Score", value= str (game_status.allied_score) + " - " + str (game_status.axis_score) , inline=True)
            stats.add_field(name="Total Player", value=server_status.current_players, inline=True)    
            stats.set_image (url=f"{config.get("rcon", 0, "stats_url")}/maps/{current_map.image_name}")  
            
            stats.set_footer(text=f"(Provided by Gryhon)")
            stats.timestamp = datetime.now()               

        if not self.msg_id:
            self.msg_id = self.webhook.send(embeds=[stats], wait=True).id
            self.insert_Message_Id(__name__, self.msg_id)  
        else:
            try:
                # Überprüfe, ob die Nachricht noch existiert
                self.webhook.fetch_message(self.msg_id)
                # Bearbeite die Nachricht, wenn sie existiert
                self.webhook.edit_message(message_id=self.msg_id, embeds=[stats])
            except discord.NotFound:
                logger.warning(f"Message with ID {self.msg_id} not found. Sending a new message.")
                self.msg_id = self.webhook.send(embeds=[stats], wait=True).id
                self.update_Message_Id (__name__, self.msg_id)

    async def background_task(self):
        last_execution = 0

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or last_execution == 0:
                
                try:
                    await self.update_message()

                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
            
                last_execution = current_time

            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:  # Check if the loop has already started
            self.loop_started = True  # Mark the loop as started
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")
      