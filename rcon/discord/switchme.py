import discord
import logging
import asyncio
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from discord.ext import commands
from discord import app_commands
from rcon.discord.discordutils import safe_send, has_allowed_role

logger = logging.getLogger(__name__)

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
                         
                        data = {"player_id": str(player_id)}

                        await rcon.Switch_Player_Now(data)
                        await safe_send(interaction, "✅ done")

                        logger.info(f"Switch player {player_id} ({data['player_id']}) by {interaction.user.name}.")
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