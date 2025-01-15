import discord
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import query_player_database, register_user, get_player_name
from lib.config import config
from .utils.name_utils import validate_t17_number, format_nickname, validate_clan_tag, validate_emojis
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed

# get Logger for this module
logger = logging.getLogger(__name__)

class NameChange(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False
        self.t17_required = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False)
        self.t17_show = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "show", default=True)
        self.enabled = config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "enabled", default=True)

    @app_commands.command(name="namechange", description="Update your Discord nickname to match your T17 account")
    @app_commands.describe(
        ingame_name="Choose your in game user",
        t17_number="Your 4-digit T17 number (optional)" if not config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else "Your 4-digit T17 number",
        clan_tag="Your clan tag (optional)" if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "clan_tag", "show", default=True) else None,
        emojis="Your emojis (optional, max 3)" if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "emojis", "show", default=True) else None
    )
    async def namechange(
        self, 
        interaction: discord.Interaction, 
        ingame_name: str,
        t17_number: str if config.get("rcon", 0, "comfort_functions", 0, "name_change_registration", "t17_number", "required", default=False) else Optional[str] = None,
        clan_tag: Optional[str] = None,
        emojis: Optional[str] = None
    ):
        if not self.enabled:
            await interaction.response.send_message("Name change functionality is currently disabled.", ephemeral=True)
            return

        try:
            # Validate T17 number
            is_valid, error_message = validate_t17_number(t17_number)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Validate clan tag
            is_valid, error_message = validate_clan_tag(clan_tag)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            is_valid, error_message = validate_emojis(emojis)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

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
                formatted_name = format_nickname(player_name, t17_number, clan_tag, emojis)
                try:
                    await member.edit(nick=formatted_name)
                    
                    # Assign role if configured
                    error_msg = await handle_roles(member, 'name_changed')
                    
                    # Send success embed
                    await send_success_embed(
                        interaction.guild,
                        interaction.user,
                        'name_changed',
                        formatted_name
                    )
                    
                    if error_msg:
                        await interaction.response.send_message(
                            f"Nickname updated successfully, but note: {error_msg}",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "Successfully updated your nickname!",
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