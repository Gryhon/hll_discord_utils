import discord
import logging
import asyncio
from datetime import datetime
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from discord.ext import commands
from rcon.discord.discordutils import build_Not_Ingame_View

# get Logger for this modul
logger = logging.getLogger(__name__)

class Statistics (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  # Initialize the parent classes (DiscordBase and commands.Cog)
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def player_stats(self, interaction: discord.Interaction):
        """Shows the requester's own live-match stats."""
        try:
            await interaction.response.defer(thinking=True, ephemeral=True)

            player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)
            if not player_id:
                await interaction.followup.send("❌ You are not registered. Please register first.", ephemeral=True)
                return

            ingame = await rcon.get_In_Game_Players()

            if not ingame.is_Player_Ingame(player_id):
                await interaction.followup.send(view=build_Not_Ingame_View(), ephemeral=True)
                return

            name = ingame.get_Ingame_Player_Name(player_id) or player_id
            live_stats = await rcon.get_Live_Game_Stats()

            embed = discord.Embed(title=f"📊 Stats — {name}", color=discord.Color.blurple())
            embed.add_field(name="⚔️ Kills", value=live_stats.get_PlayerStats(player_id, "kills"), inline=True)
            embed.add_field(name="💀 Deaths", value=live_stats.get_PlayerStats(player_id, "deaths"), inline=True)
            embed.add_field(name="📈 K/D Ratio", value=live_stats.get_PlayerStats(player_id, "kill_death_ratio"), inline=True)
            embed.add_field(name="⏱️ Kills/min", value=live_stats.get_PlayerStats(player_id, "kills_per_minute"), inline=True)
            embed.add_field(name="⏱️ Deaths/min", value=live_stats.get_PlayerStats(player_id, "deaths_per_minute"), inline=True)
            embed.add_field(name="🔥 Kill Streak", value=live_stats.get_PlayerStats(player_id, "kills_streak"), inline=True)
            embed.set_footer(text="(Provided by Gryhon)")
            embed.timestamp = datetime.now()

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"player_stats requested by {interaction.user.name} for player_id={player_id}")

        except Exception as e:
            logger.error(f"Unexpected error in player_stats: {e}", exc_info=True)

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

       