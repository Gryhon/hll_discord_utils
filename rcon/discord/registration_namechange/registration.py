import discord
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
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
        self.bot = bot
        self.in_Loop = False
        DiscordBase.__init__(self)

    @app_commands.command(
        name="voter_registration",
        description="Register your Discord account with your T17 account"
    )
    @app_commands.describe(
        ingame_name="Choose your in game user",
        vote_reminders="Choose your vote reminder preference"
    )
    @app_commands.choices(vote_reminders=[
        app_commands.Choice(name="Remind me if I haven't voted yet", value=1),
        app_commands.Choice(name="No vote reminders", value=0)
    ])
    async def voter_registration(
        self,
        interaction: discord.Interaction,
        ingame_name: str,
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

            # Register the user
            success, message = await register_user(
                self,
                interaction.user.name,
                interaction.user.id,
                member.nick,
                ingame_name,
                vote_reminder_value  # Convert bool to int for database
            )
            
            if success:
                # Handle role assignment
                role_error = await handle_roles(member, 'registered')
                if role_error:
                    message += f"\nNote: {role_error}"
                
                # Send success embed
                await send_success_embed(
                    interaction.guild,
                    interaction.user,
                    'registered',
                    member.nick or interaction.user.name,
                    ingame_name
                )
            
            await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in voter_registration: {e}")
            await interaction.response.send_message("An error occurred during registration.", ephemeral=True)

    @voter_registration.autocomplete("ingame_name")
    async def voter_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await handle_autocomplete(interaction, current, self.in_Loop) 