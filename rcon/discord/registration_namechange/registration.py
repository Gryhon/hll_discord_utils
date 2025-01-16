import discord
import logging
import asyncio
from datetime import datetime
from typing import List
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from .utils.search_vote_reg import query_player_database, register_user, handle_autocomplete
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed

# get Logger for this module
logger = logging.getLogger(__name__)

class Registration(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False

    @app_commands.command(name="voter_registration", description="Combine your Discord user with your T17 account")
    @app_commands.describe(
        ingame_name="Choose your in game user",
        vote_reminders="Would you like to receive vote reminders?"
    )
    async def voter_registration(
        self, 
        interaction: discord.Interaction, 
        ingame_name: str,
        vote_reminders: bool = True
    ):
        try:
            # Check if feature is enabled
            if not config.get("rcon", 0, "name_change_registration", "enabled", default=True):
                await interaction.response.send_message("This feature is not enabled.", ephemeral=True)
                return

            success, message = await register_user(
                self,
                interaction.user.name,
                interaction.user.id,
                interaction.guild.get_member(interaction.user.id).nick,
                ingame_name,
                1 if vote_reminders else 0  # Use 1/0 for the votereg_ask_reg_cnt field
            )
            
            if success:
                # Assign role if configured
                error_msg = await handle_roles(interaction.guild.get_member(interaction.user.id), 'registered')
                if error_msg:
                    message += f"\nNote: {error_msg}"
                
                # Send success embed
                await send_success_embed(
                    interaction.guild,
                    interaction.user,
                    'registered',
                    interaction.guild.get_member(interaction.user.id).nick or interaction.user.name,
                    ingame_name
                )
                
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Unexpected error in voter_registration: {e}")
            await interaction.response.send_message("An error occurred during registration.", ephemeral=True)

    @voter_registration.autocomplete("ingame_name")
    async def voter_autocomplete(self, interaction: discord.Interaction, player_name: str) -> List[app_commands.Choice[str]]:
        return await handle_autocomplete(interaction, player_name, self.in_Loop) 