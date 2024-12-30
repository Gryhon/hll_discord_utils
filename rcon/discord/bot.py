import logging
import threading
import asyncio
import discord
from discord.ext import commands
from lib.config import config
from rcon.discord.serverstatus import ServerStatus
from rcon.discord.maprotation import MapRotation
from rcon.discord.balance import Balance
from rcon.discord.votemap import VoteMap
from rcon.discord.autolevel import AutoLevel
from rcon.discord.comfort import Comfort
from rcon.discord.inappropriatename import InappropriateName

# get Logger for this modul
logger = logging.getLogger(__name__)

class MainBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="/", intents=intents)
        self.shutdown_event = asyncio.Event()

    async def on_ready(self):
        logger.info (f'Logged in as {self.user} (ID: {self.user.id})')

        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    async def setup_hook(self):
        
        if (config.get("rcon", 0, "server_status", 0, "enabled")):
            logger.info ("Start server status")
            await self.add_cog(ServerStatus(self)) 

        if (config.get("rcon", 0, "map_rotation", 0, "enabled")):
            logger.info ("Start map rotation")
            await self.add_cog(MapRotation(self)) 
        
        if (config.get("rcon", 0, "server_balance", 0, "enabled")):
            logger.info ("Start server balance")
            await self.add_cog(Balance(self)) 
        
        if (config.get("rcon", 0, "map_vote", 0, "enabled")):
            logger.info ("Start map vote")
            await self.add_cog(VoteMap(self)) 

        if (config.get("rcon", 0, "auto_level", 0, "enabled")):
            logger.info ("Start auto level")
            await self.add_cog(AutoLevel(self)) 

        if (config.get("rcon", 0, "comfort_functions", 0, "enabled")):
            logger.info ("Start comfort functions")
            await self.add_cog(Comfort(self)) 

        if (config.get("rcon", 0, "inappropriate_name", 0, "enabled")):
            logger.info ("Start inappropriate name functions")
            await self.add_cog(InappropriateName(self)) 
            
        await self.tree.sync()
        logger.info ("Slash commands have been synced.")
        

    def run_bot(self):
        self.tree.clear_commands (guild=discord.Object(id=1299285373855203349))
        logger.info ("Slash commands have been synced.")

        token = config.get("rcon", 0, "discord_token")
        self.run(token)

    def shutdown_bot(self):
        asyncio.run_coroutine_threadsafe(self.close(), self.loop)

bot = None
bot_thread = None

def start_bot():
    global bot
    global bot_thread

    bot = MainBot ()
    bot_thread = threading.Thread(target=bot.run_bot)
    bot_thread.start()

def shutdown_bot():
    global bot
    global bot_thread

    bot.shutdown_bot()
    bot_thread.join()