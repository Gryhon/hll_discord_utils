import discord
import logging
import asyncio
import rcon.model as model
import rcon.rcon as rcon
from lib.rconV2 import RconV2
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands
from datetime import datetime

logger = logging.getLogger(__name__)

async def safe_send(interaction: discord.Interaction, content: str, ephemeral: bool = True):
    # Send message or follow-up if already responded.
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=ephemeral)
        else:
            await interaction.followup.send(content, ephemeral=ephemeral)
    
    except Exception as e:
        logger.error(f"Failed to send interaction message: {e}", exc_info=True)

def has_allowed_role(member: discord.Member, item: str) -> bool:
    ret = False

    try:
        allowed_names = (config.get("rcon", 0, "discord_commands", 0, f"{item}", 0, "groups") or
                         config.get("rcon", 0, "discord_commands", 0, "groups") or [])
        
        if config.get("rcon", 0, "discord_commands", 0, "admin_always") and member.guild_permissions.administrator:
            ret = True
        else:
            ret = any(role.name in allowed_names for role in member.roles)

        return ret
    
    except Exception as e:
        logger.error(f"Error in has_allowed_role: {e}", exc_info=True)
        return False

class PunishMe (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)
    
    @app_commands.command(name="punish_me", description="Will punish you in game to avoid additional cooldown")
    async def punish_me(self, interaction: discord.Interaction):
        try:
            if not isinstance(interaction.user, discord.Member):
                await safe_send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_allowed_role(interaction.user, "punish_me"):
                await safe_send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()

                    if ingame.is_Player_Ingame (player_id) == True:
                         
                        data = {"player_name": str(ingame.get_Ingame_Player_Name (player_id)), "reason": "Because you said so! (Respawn)"}

                        await rcon.Punish_Player(data)
                        await safe_send(interaction, "✅ done")

                        logger.info(f"Punish player {player_id} ({data['player_name']}) by {interaction.user.name}.")
                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")   

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (PunishMe) started")

class SwitchMe (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @app_commands.command(name="switch_me", description="Will switch you on the other team")
    async def switch_me(self, interaction: discord.Interaction):
        try:
            if not isinstance(interaction.user, discord.Member):
                await safe_send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_allowed_role(interaction.user, "punish_me"):
                await safe_send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()

                    if ingame.is_Player_Ingame (player_id) == True:
                         
                        data = {"player_name": str(ingame.get_Ingame_Player_Name (player_id))}

                        await rcon.Switch_Player_Now(data)
                        await safe_send(interaction, "✅ done")

                        logger.info(f"Switch player {player_id} ({data['player_name']}) by {interaction.user.name}.")
                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (SwitchMe) started")

class WhoKilledMe (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @app_commands.command(name="who_killed_me", description="Shows who killed you")
    async def who_killed_me(self, interaction: discord.Interaction):
        try:
            if not isinstance(interaction.user, discord.Member):
                await safe_send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_allowed_role(interaction.user, "who_killed_me"):
                await safe_send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()
                    logger.info(f"Who killed me command by {interaction.user.name} (player_id: {player_id})")

                    if ingame.is_Player_Ingame (player_id) == True:
                        recent_log = []
                        ingame_name = ingame.get_Ingame_Player_Name (player_id)

                        payload = {"end": 500,
                                   "filter_action": ["KILL", "TEAMKILL"],
                                   "filter_player": [f"{ingame_name}"],  
                                   "inclusive_filter": "true"}
                
                        recent_log = await rcon.get_Recent_Logs (payload)

                        table = "```"
                        table += " No |   Killed by   |      Weapon\n"
                        table += "------------------------------------\n"

                        no = 0
                        
                        for i in range(len(recent_log.logs)):

                            action = recent_log.get_LogItem (i, "action")
                            killer = recent_log.get_LogItem (i, "player_name_1")

                            if action == "KILL" and killer != ingame_name:
                                no = no + 1

                                if len(killer) > 13:
                                    killer = killer[:12] + "…"
                                else:
                                    killer = killer.ljust(13)

                                weapon = recent_log.get_LogItem(i, "weapon")
                                weapon = (weapon[:11] + "...") if len(weapon) > 14 else weapon

                                table += f"{str(no):>3} | {killer} | {weapon:14}\n"

                                #table += f"{str (no):>3} | {killer} | {weapon:14}\n"
                            elif action == "MATCHMATCH START":
                                break

                        if no == 0:
                            table += "Not killed in the last 5 minutes\n"

                        table += "```"
                        
                        stats = discord.Embed(title="Who killed me?",
                                              description="\n")
                            
                        stats.add_field(name="", value="", inline=False)
                        stats.add_field(name="", value=table, inline=False) 

                        stats.set_footer(text=f"(Provided by Gryhon)")
                        stats.timestamp = datetime.now()    
                        
                        await interaction.response.send_message(embed=stats, ephemeral=True)           

                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  

class WhomIKilled (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @app_commands.command(name="whom_i_killed", description="Shows whom you killed")
    async def whom_i_killed(self, interaction: discord.Interaction):
        try:
            if not isinstance(interaction.user, discord.Member):
                await safe_send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_allowed_role(interaction.user, "whom_i_killed"):
                await safe_send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()
                    logger.info(f"Whom I killed {interaction.user.name} (player_id: {player_id})")

                    if ingame.is_Player_Ingame (player_id) == True:
                        recent_log = []
                        ingame_name = ingame.get_Ingame_Player_Name (player_id)

                        payload = {"end": 500,
                                   "filter_action": ["KILL", "TEAMKILL"],
                                   "filter_player": [f"{ingame_name}"],  
                                   "inclusive_filter": "true"}
                
                        recent_log = await rcon.get_Recent_Logs (payload)
                
                        table = "```"
                        table += " No |   Killed  \n"
                        table += "------------------------------------\n"

                        no = 0
                        
                        for i in range(len(recent_log.logs)):

                            action = recent_log.get_LogItem (i, "action")
                            me = recent_log.get_LogItem (i, "player_name_1")
                            victim = recent_log.get_LogItem (i, "player_name_2")

                            if action == "KILL" and me == ingame_name:
                                no = no + 1

                                if len(victim) > 30:
                                    victim = victim[:27] + "…"
                                else:
                                    victim = victim.ljust(27)

                                table += f"{str (no):>3} | {victim}\n"
                            elif action == "MATCHMATCH START":
                                break

                        if no == 0:
                            table += "No kills in the last 5 minutes\n"

                        table += "```"
                        
                        stats = discord.Embed(title="Whom I killed?",
                                              description="\n")
                            
                        stats.add_field(name="", value="", inline=False)
                        stats.add_field(name="", value=table, inline=False) 

                        stats.set_footer(text=f"(Provided by Gryhon)")
                        stats.timestamp = datetime.now()    
                        
                        await interaction.response.send_message(embed=stats, ephemeral=True)           

                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (WhomIKilled) started")

class RemovePlayerFromSquad (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False
        #self.rconV2 = rconV2.Get ()

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @app_commands.command(name="remove_player_from_squad", description="Removes a player from their squad. (SL only)")
    async def who_killed_me(self, interaction: discord.Interaction):
        try:
            if not isinstance(interaction.user, discord.Member):
                await safe_send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_allowed_role(interaction.user, "punish_me"):
                await safe_send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                logger.info (f"Use of RconV2 in RemovePlayerFromSquad")
                Rcon = await RconV2.get ()
                
                
                #players = await Rcon.get_players()
                #logger.info (f"Players: {players}")
                
                #await Rcon.remove_player_from_squad ("75712ffe5094adfb3d45fa9d9b6a3040", "Test")
                test = await Rcon.get_command_details ("SetDynamicWeatherEnabled")
                logger.info (f"Commands: {test}")

                logger.info (f"After use of RconV2 in RemovePlayerFromSquad")

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()

                    if ingame.is_Player_Ingame (player_id) == False:
                        
                        # Stub
                        await asyncio.sleep (5)   
                       
                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (WhoKilledMe) started")

