import discord
import logging
import asyncio
from datetime import datetime
from typing import List
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import query_player_database, register_user
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
    )
    async def voter_registration(self, interaction: discord.Interaction, ingame_name: str):
        try:
            success, message = await register_user(
                self,
                interaction.user.name,
                interaction.user.id,
                interaction.guild.get_member(interaction.user.id).nick,
                ingame_name
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
        try:
            while self.in_Loop:
                await asyncio.sleep(1)
           
            self.in_Loop = True
            name = player_name
            multi_array = None

            if len(name) >= 2:
                logger.info(f"Search query: {name.replace(" ", "%")}")
                multi_array = await query_player_database(name.replace(" ", "%"))
        
            if multi_array is not None and len(multi_array) >= 1:
                result = [
                    app_commands.Choice(name=f"Last: {datetime.fromtimestamp(player[3]/1000).strftime('%Y-%m-%d')} - {", ".join(player[1])}"[:100], value=player[0])
                    for player in multi_array
                ]
                self.in_Loop = False
                return result
            else:
                self.in_Loop = False
                return []
            
        except Exception as e:
            logger.error(f"Unexpected error in voter_autocomplete: {e}")
            self.in_Loop = False
            return [] 