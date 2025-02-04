import discord
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from .utils.search_vote_reg import query_player_database, register_user, get_player_name, handle_autocomplete
from lib.config import config
from .utils.name_utils import validate_t17_number, format_nickname, validate_clan_tag, update_user_nickname
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed, handle_name_update_response
import re

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

    @app_commands.command(
        name="setup-name",
        description="Update your Discord nickname to match your T17 account"
    )
    @app_commands.describe(
        ingame_name="Choose your in game user",
        t17_number="Your 4-digit T17 number (if required)",
        clan_tag="Your clan tag (optional)",
        vote_reminders="Choose your vote reminder preference"
    )
    @app_commands.choices(vote_reminders=[
        app_commands.Choice(name="Remind me if I haven't voted yet", value=1),
        app_commands.Choice(name="No vote reminders", value=0)
    ])
    async def namechange(
        self, 
        interaction: discord.Interaction, 
        ingame_name: str,
        t17_number: Optional[str] = None,
        clan_tag: Optional[str] = None,
        vote_reminders: app_commands.Choice[int] = None
    ):
        try:
            # Use default True if no choice made
            vote_reminder_value = vote_reminders.value if vote_reminders else 1
            
            # Check if feature is enabled
            if not config.get("rcon", 0, "name_change_registration", "enabled", default=True):
                await interaction.response.send_message("This feature is not enabled.", ephemeral=True)
                return

            # Get member
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("Could not find your Discord account.", ephemeral=True)
                return

            # Check if user is already registered
            result = self.select_T17_Voter_Registration(interaction.user.id)
            if result:
                await interaction.response.send_message(
                    "You are already registered! Please use `/update_name` to modify your nickname or settings.",
                    ephemeral=True
                )
                return

            # Get player info from database - the value from autocomplete is already the player_id
            player_id = ingame_name  # The autocomplete Choice.value is the player_id
            if not bool(re.fullmatch(r"[0-9a-fA-F]{32}", player_id)):
                await interaction.response.send_message(
                    '''Something went wrong, please select your name from the\n''' \
                    '''list and do not add or remove any characters,\n''' \
                    '''after the selection.''',
                    ephemeral=True
                )
                return

            # Get actual player name
            player_name = await get_player_name(player_id)  # This will get the name from the ID
            if not player_name:
                await interaction.response.send_message("Could not retrieve your player name.", ephemeral=True)
                return

            # Check T17 number requirement
            t17_required = config.get("rcon", 0, "name_change_registration", "t17_number", "required", default=False)
            if t17_required and not t17_number:
                await interaction.response.send_message(
                    "T17 number is required for registration. Please provide your 4-digit T17 number.",
                    ephemeral=True
                )
                return

            # Register the user
            success, message = await register_user(
                self,
                interaction.user.name,
                interaction.user.id,
                member.nick,
                player_id,
                vote_reminder_value  # Use the integer value
            )
            if not success:
                await interaction.response.send_message(message, ephemeral=True)
                return

            # Update nickname with components
            success, formatted_name, error_message = await update_user_nickname(
                self,
                member,
                player_name,
                t17_number,
                clan_tag,
                None  # No emojis in initial setup
            )
            
            if not success:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            # Handle role assignment
            role_error = await handle_roles(member, 'name_changed')
            
            # Send single response with complete status
            await interaction.response.send_message(
                f"Registration successful! Your nickname has been updated to: {formatted_name}\n" +
                f"Vote reminders are {'enabled' if vote_reminder_value else 'disabled'}\n" +
                (f"\nNote: {role_error}" if role_error else ""),
                ephemeral=True
            )

        except discord.errors.InteractionResponded:
            logger.warning("Interaction was already responded to")
        except Exception as e:
            logger.error(f"Error in namechange: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while updating your nickname.",
                    ephemeral=True
                )

    @namechange.autocomplete("ingame_name")
    async def namechange_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await handle_autocomplete(interaction, current, self.in_Loop) 