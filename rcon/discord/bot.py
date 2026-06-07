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
from rcon.discord.comfort import BroadcastMessage, AfterGameMessage, AutoUnban
from rcon.discord.artillerycalculator import ArtilleryCalculator
from rcon.discord.registration import Registration
from rcon.discord.unregister import Unregister
from rcon.discord.rotationvote import RotationVote
from rcon.discord.inappropriate import Inappropriate
from rcon.discord.whokilledme import WhoKilledMe
from rcon.discord.whomikilled import WhomIKilled 
from rcon.discord.switchme import SwitchMe
from rcon.discord.punishme import PunishMe
from rcon.discord.removeplayerfromsquad import RemovePlayerFromSquad
from rcon.discord.vip import VipManagement

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
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')

        guild_id = config.get("rcon", 0, "guild_id", default=0)
        guilds_to_sync = [discord.Object(id=guild_id)] if guild_id else self.guilds
        for guild in guilds_to_sync:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Slash commands synced to guild {guild.id}: {[c.name for c in synced]}")
            except discord.HTTPException as e:
                logger.error(f"Guild sync failed for {guild.id}: {e}")

        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)
    
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

            if (config.get("rcon", 0, "comfort_functions", 0, "after_game_message", 0, "enabled")):
                await self.add_cog(AfterGameMessage(self))

            if (config.get("rcon", 0, "comfort_functions", 0, "broadcast_message", 0, "enabled")):
                await self.add_cog(BroadcastMessage(self))

            if (config.get("rcon", 0, "comfort_functions", 0, "auto_unban", 0, "enabled")):
                await self.add_cog(AutoUnban(self))

        if (config.get("rcon", 0, "register_player", 0, "enabled")):
            logger.info ("Start registration functions")
            
            await self.add_cog(Registration(self))
            await self.add_cog(Unregister(self))

        if (config.get("rcon", 0, "artillery_calculator", 0, "enabled")):
            logger.info ("Start auto artillery calculator")
            await self.add_cog(ArtilleryCalculator(self))             

        if (config.get("rcon", 0, "map_rotation_vote", 0, "enabled")):
            logger.info ("Start map rotation vote")
            await self.add_cog(RotationVote(self))

        await self.tree.sync()
        logger.info ("Slash commands have been synced.")
       
            await self.add_cog(ArtilleryCalculator(self))  

        if (config.get("rcon", 0, "discord_commands", 0, "enabled")):
            logger.info ("Start registration functions")
            
            if (config.get("rcon", 0, "discord_commands", 0, "punish_me", 0, "enabled")):
                await self.add_cog(PunishMe(self))

            if (config.get("rcon", 0, "discord_commands", 0, "switch_me", 0, "enabled")):
                await self.add_cog(SwitchMe(self))

            if (config.get("rcon", 0, "discord_commands", 0, "who_killed_me", 0, "enabled")):      
                await self.add_cog(WhoKilledMe(self))

            if (config.get("rcon", 0, "discord_commands", 0, "whom_i_killed", 0, "enabled")):      
                await self.add_cog(WhomIKilled(self))

            if (config.get("rcon", 0, "discord_commands", 0, "remove_player_from_squad", 0, "enabled")):
                await self.add_cog(RemovePlayerFromSquad(self))

            if (config.get("rcon", 0, "discord_commands", 0, "vip_management", 0, "enabled")):
                await self.add_cog(VipManagement(self))

        if (config.get("rcon", 0, "inappropriate_name", 0, "enabled")):
            logger.info ("Start inappropriate name")
            await self.add_cog(Inappropriate(self))

    def run_bot(self):
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