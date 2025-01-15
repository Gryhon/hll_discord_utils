import discord
import logging
import asyncio
from datetime import datetime
from typing import List
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.player_search_vote_reg import query_player_database, register_user, get_player_name
from lib.config import config

# get Logger for this module
logger = logging.getLogger(__name__)

class NameChange(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False
        self.enabled = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "enabled", default=True)

    @app_commands.command(name="namechange", description="Update your Discord nickname to match your T17 account")
    @app_commands.describe(
        ingame_name="Choose your in game user",
    )
    async def namechange(self, interaction: discord.Interaction, ingame_name: str):
        if not self.enabled:
            await interaction.response.send_message("Name change functionality is currently disabled.", ephemeral=True)
            return

        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("Could not find your Discord member information.", ephemeral=True)
                return

            # Check if bot has permission to change nicknames
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if not bot_member.guild_permissions.manage_nicknames:
                await interaction.response.send_message("I don't have permission to change nicknames in this server.", ephemeral=True)
                return

            # Check if user is higher in hierarchy
            if member.top_role >= bot_member.top_role:
                await interaction.response.send_message("I can't modify your nickname due to role hierarchy.", ephemeral=True)
                return

            success, message = await register_user(
                self,
                interaction.user.name,
                interaction.user.id,
                member.nick,
                ingame_name
            )

            if not success:
                await interaction.response.send_message(message, ephemeral=True)
                return

            # Get and update nickname
            player_name = await get_player_name(ingame_name)
            if player_name:
                try:
                    await member.edit(nick=player_name)
                    logger.info(f"Updated nickname for {interaction.user.name} to {player_name}")
                    await interaction.response.send_message(
                        f"Successfully registered and updated your nickname to {player_name}", 
                        ephemeral=True
                    )
                except discord.Forbidden:
                    logger.error(f"Failed to update nickname for {interaction.user.name} - insufficient permissions")
                    await interaction.response.send_message(
                        "Registration successful, but I don't have permission to update your nickname.", 
                        ephemeral=True
                    )
                except discord.HTTPException as e:
                    logger.error(f"HTTP error while updating nickname: {e}")
                    await interaction.response.send_message(
                        "Registration successful, but there was an error updating your nickname.", 
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "Registration successful, but couldn't fetch your in-game name.", 
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Unexpected error in namechange: {e}")
            await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

    @namechange.autocomplete("ingame_name")
    async def namechange_autocomplete(self, interaction: discord.Interaction, player_name: str) -> List[app_commands.Choice[str]]:
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
            logger.error(f"Unexpected error in namechange_autocomplete: {e}")
            self.in_Loop = False
            return [] 