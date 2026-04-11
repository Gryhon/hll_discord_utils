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
                await safe_Send(interaction, "❌ This command only works on the server.")
                logger.info(f"{interaction.user} used command outside the server.")

            elif not has_Allowed_Role(interaction.user, "who_killed_me"):
                await safe_Send(interaction, "❌ You do not have permission for this command.")
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
                        
                        deaths = []

                        for i in range(len(log_items.logs)):
                            action = log_items.get_LogItem(i, "type")
                            killer = log_items.get_LogItem(i, "player1_name")

                            if action == "KILL" and killer != ingame_name:
                                weapon = log_items.get_LogItem(i, "weapon")
                                deaths.append((killer, weapon))

                            if len(deaths) >= 7:
                                break

                        death_count = live_stats.get_PlayerStats(player_id, "deaths")
                        color = discord.Color.red() if deaths else discord.Color.green()

                        stats = discord.Embed(
                            title="Who killed me?",
                            description="🦸 My hero, you survived!" if not deaths else "",
                            color=color,
                        )

                        stats.add_field(name="💀 Deaths", value=live_stats.get_PlayerStats(player_id, "deaths"), inline=False)
                        stats.add_field(name="🤝 Deaths by TK", value=live_stats.get_PlayerStats(player_id, "deaths_by_tk"), inline=False)
                        stats.add_field(name="⏱️ Deaths/min", value=live_stats.get_PlayerStats(player_id, "deaths_per_minute"), inline=False)

                        if deaths:
                            stats.add_field(name="", value="─" * 30, inline=False)

                            for no, (killer, weapon) in enumerate(deaths, start=1):
                                killer_display = (killer[:12] + "…") if len(killer) > 13 else killer
                                stats.add_field(
                                    name=f"💀 #{no} — {killer_display} ({weapon})",
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
