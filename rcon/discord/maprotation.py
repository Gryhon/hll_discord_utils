import discord
import logging
import asyncio
import time
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from datetime import datetime
from discord.ext import commands
from discord import app_commands

# get Logger for this modul
logger = logging.getLogger(__name__)

class MapRotation (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.webhook_url = config.get("rcon", 0, "map_rotation", 0, "webhook")
        self.webhook = discord.SyncWebhook.from_url(self.webhook_url)
        self.msg_id = self.select_Message_Id (__name__)
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False

    async def update_message (self):
        map_rotation = await rcon.get_Map_Rotation ()
        server_status = await rcon.get_Server_Status ()

        if map_rotation and server_status:
                        
            description = "**Map rotation:**\n"
    
            for map in map_rotation.maps:
                description += f"- {map.pretty_name}\n"
            
            maps = discord.Embed(
                title=server_status.name,
                description=description + "\n",
                color=discord.Color.blue(),
                url=config.get("rcon", 0, "stats_url")
                )                           
                        
            maps.set_image (url=f"{config.get("rcon", 0, "stats_url")}/maps/unknown.webp")  
            maps.set_footer(text=f"(Provided by Gryhon)")
            maps.timestamp = datetime.now()

        if not self.msg_id:
            self.msg_id = self.webhook.send(embeds=[maps], wait=True).id
            self.insert_Message_Id(__name__, self.msg_id)  
        else:
            try:
                # Check whether the message still exists
                self.webhook.fetch_message(self.msg_id)
                # Edit the message if it exists
                self.webhook.edit_message(message_id=self.msg_id, embeds=[maps])

            except discord.NotFound:
                logger.warning(f"Message with ID {self.msg_id} not found. Sending a new message.")
                self.msg_id = self.webhook.send(embeds=[maps], wait=True).id
                self.update_Message_Id (__name__, self.msg_id)

    async def background_task(self):
        last_execution = 0

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or current_time == 0:
                
                try:
                    await self.update_message()

                except Exception as e:
                    logger.error(f"Unexpected error: {e}")

                last_execution = current_time

            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

        