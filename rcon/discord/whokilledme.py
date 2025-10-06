import discord
import logging
import asyncio
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from rcon.discord.discordutils import safe_send, has_allowed_role

logger = logging.getLogger(__name__)

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
                await interaction.response.defer(thinking=True, ephemeral=True) 

                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()
                    logger.info(f"Who killed me command by {interaction.user.name} (player_id: {player_id})")

                    if ingame.is_Player_Ingame (player_id) == True:
                        
                        ingame_name = ingame.get_Ingame_Player_Name (player_id) 
                        live_stats = await rcon.get_Live_Game_Stats ()
                        
                        payload = {"limit": 1,
                                   "action": "MATCH START"}

                        start = await rcon.get_Historical_Logs (payload)
                        date = start.get_LogItem (0, "event_time")
                        logger.info (f"Match start time: {date}")
                        
                        payload = {"player_id": f"{player_id}",
                                   "from_": f"{date}",
                                   "time_sort": "desc"}
                        log_items = await rcon.get_Historical_Logs (payload)
                        
                        table = "```"
                        table += " No |   Killed by   |      Weapon\n"
                        table += "------------------------------------\n"

                        no = 0
                        
                        for i in range(len(log_items.logs)):

                            action = log_items.get_LogItem (i, "type")
                            killer = log_items.get_LogItem (i, "player1_name")

                            if action == "KILL" and killer != ingame_name:
                                no = no + 1

                                if len(killer) > 13:
                                    killer = killer[:12] + "…"
                                else:
                                    killer = killer.ljust(13)

                                weapon = log_items.get_LogItem(i, "weapon")
                                weapon = (weapon[:12] + "..") if len(weapon) > 14 else weapon

                                table += f"{str(no):>3} | {killer} | {weapon:14}\n"

                            if no >= 7:
                                break

                        if no == 0:
                            table += "My hero, you survived!\n"

                        table += "```"

                        stats = discord.Embed(title="Who killed me?",
                                              description="\n")
                        
                        stats.add_field(name="Deaths", value=live_stats.get_PlayerStats (player_id, "deaths"), inline=True)
                        stats.add_field(name="Deaths by TK", value=live_stats.get_PlayerStats (player_id, "deaths_by_tk"), inline=True)
                        stats.add_field(name="Deaths per Min", value=live_stats.get_PlayerStats (player_id, "deaths_per_minute"), inline=True)
                        stats.add_field(name="", value="", inline=True)
                            
                        stats.add_field(name="", value="", inline=False)
                        stats.add_field(name="", value=table, inline=False) 

                        stats.set_footer(text=f"(Provided by Gryhon)")
                        stats.timestamp = datetime.now()    

                        await interaction.followup.send(embed=stats, ephemeral=True)

                    else:
                        await safe_send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  
