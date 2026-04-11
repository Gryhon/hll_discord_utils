import discord
import logging
import asyncio
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from rcon.discord.discordutils import safe_Send, has_Allowed_Role

logger = logging.getLogger(__name__)

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
                await safe_Send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_Allowed_Role(interaction.user, "whom_i_killed"):
                await safe_Send(interaction, "❌ You do not have permission for this command.")
                logger.info(f"{interaction.user} does not have permission to use punish_me command.")

            else:
                await interaction.response.defer(thinking=True, ephemeral=True) 

                player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)

                if player_id:
                    ingame = await rcon.get_In_Game_Players ()
                    logger.info(f"Whom I killed {interaction.user.name} (player_id: {player_id})")

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
                
                        kills = []

                        for i in range(len(log_items.logs)):
                            action = log_items.get_LogItem(i, "type")
                            myself = log_items.get_LogItem(i, "player1_name")
                            victim = log_items.get_LogItem(i, "player2_name")

                            if action == "KILL" and myself == ingame_name:
                                weapon = log_items.get_LogItem(i, "weapon")
                                kills.append((victim, weapon))

                            if len(kills) >= 7:
                                break

                        color = discord.Color.green() if kills else discord.Color.orange()

                        stats = discord.Embed(
                            title="Whom I killed?",
                            description="💪 Mate, try harder, no kills." if not kills else "",
                            color=color,
                        )

                        stats.add_field(name="⚔️ Kills", value=live_stats.get_PlayerStats(player_id, "kills"), inline=False)
                        stats.add_field(name="🤝 TK", value=live_stats.get_PlayerStats(player_id, "teamkills"), inline=False)
                        stats.add_field(name="📊 K/D Ratio", value=live_stats.get_PlayerStats(player_id, "kill_death_ratio"), inline=False)
                        stats.add_field(name="⏱️ Kills/min", value=live_stats.get_PlayerStats(player_id, "kills_per_minute"), inline=False)
                        stats.add_field(name="🔥 Kill Streak", value=live_stats.get_PlayerStats(player_id, "kills_streak"), inline=False)

                        if kills:
                            stats.add_field(name="", value="─" * 30, inline=False)

                            for no, (victim, weapon) in enumerate(kills, start=1):
                                victim_display = (victim[:12] + "…") if len(victim) > 13 else victim
                                stats.add_field(
                                    name=f"⚔️ #{no} — {victim_display} ({weapon})",
                                    value="",
                                    inline=False,
                                )

                        stats.set_footer(text="(Provided by Gryhon)")
                        stats.timestamp = datetime.now()

                        await interaction.followup.send(embed=stats, ephemeral=True)           

                    else:
                        await safe_Send(interaction, "❌ You are not ingame. Please join a server first.")
                        logger.info(f"{interaction.user.name} is not ingame. Cannot execute punish_me command.")
                else:
                    await safe_Send(interaction, "❌ You are not registered. Please register first.")
                    logger.info(f"{interaction.user.name} is not registered. Has to register first.")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")  

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task (WhomIKilled) started")