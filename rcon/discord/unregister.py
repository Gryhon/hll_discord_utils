import discord
import logging
import asyncio
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from lib.config import config

logger = logging.getLogger(__name__)

class Unregister(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

        @self.bot.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error):
            if isinstance(error, app_commands.MissingAnyRole):
                await interaction.response.send_message(
                    "Du hast keine Berechtigung, diesen Befehl zu verwenden.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Ein Fehler ist aufgetreten.",
                    ephemeral=True
                )

    @app_commands.command(name="unregister_me", description="Remove your T17 registration")
    async def unregister_me(self, interaction: discord.Interaction):
        try:
            user = interaction.user

            player_id,_,_,_,_ = self.select_T17_Voter_Registration (user.id)

            if player_id is None:
                await interaction.response.send_message (f"{user.name}, you are not registered.", ephemeral=True)
                logger.info(f"User {user.name} (ID: {user.id}) is not registered")
            else:
                if self.delete_T17_Voter_Registration(user.id):
                    logger.info(f"User {user.name} (ID: {user.id}) chose to unregister.")
                    await interaction.response.send_message(f"{user.name}, you have been successfully unregistered. Hope we will see you again.", ephemeral=True)
                else:
                    await interaction.response.send_message("Failed to unregister user due to a database error.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in unregister_user: {e}")
            await interaction.response.send_message ("An error occurred while trying to unregister the user.", ephemeral=True)

    @app_commands.command(name="unregister_user", description="Remove a user's T17 registration (Admin only)")
    @app_commands.describe(user="The Discord user to unregister")
    #@app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.has_role ("User")
    async def unregister_user (self, interaction: discord.Interaction, user: discord.Member):
        try:
            # Check if user is registered
            player_id,_,_,_,_ = self.select_T17_Voter_Registration(user.id)

            if player_id is None:
                await interaction.response.send_message(f"User {user.name} is not registered.", ephemeral=True)
                logger.info(f"User {user.name} (ID: {user.id}) is not registered")
            else:
                # Remove from database using DiscordBase method
                if self.delete_T17_Voter_Registration(user.id):
                    logger.info(f"User {user.name} (ID: {user.id}) was unregistered by {interaction.user.name}")
                    await interaction.response.send_message (f"Successfully unregistered {user.name}", ephemeral=True)
                else:
                    await interaction.response.send_message("Failed to unregister user due to a database error.", ephemeral=True)
                    logger.error(f"Failed to unregister user {user.name} (ID: {user.id}) due to database error")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await interaction.response.send_message("An error occurred while trying to unregister the user.",  ephemeral=True)    

    async def background_task(self):
        while not self.shutdown_event.is_set():
                await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")


    