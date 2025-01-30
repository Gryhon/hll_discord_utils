import discord
import logging
import asyncio
import re
import random
import rcon.rcon as rcon
from lib.utils import is_Integer
from datetime import datetime
from typing import List
from discord import app_commands
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from .utils.role_utils import handle_roles
from .utils.message_utils import send_success_embed

# get Logger for this module
logger = logging.getLogger(__name__)

class Verify_Account(discord.ui.Modal, title="Verify your account"):
    def __init__(self, expected_number: int):
        super().__init__()
        self.expected_number = expected_number
        self.number = discord.ui.TextInput(label="In-game displayed number:", placeholder="Number only", required=True)
        self.add_item(self.number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if is_Integer (self.number.value) == True:
                user_input = int(self.number.value) 

                if user_input == self.expected_number:
                    self.result = True
                    response_text = f"✅ Correct! Your account is now verified."
                else:
                    self.result = False
                    response_text = f"❌ Wrong! You cannot be verified. Please try again."

                await interaction.response.send_message(response_text, ephemeral=True)

            else:
                await interaction.response.send_message("Please enter a valid natural number", ephemeral=True)
                self.result = False

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.result = False

class Registration(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False
    
    async def query_Player_Database(self, query: str) -> List[str]:
        try:
            if len (query) > 1:       
                payload ={"page_size": 25, "page": 1, "player_name": query}

                result = await rcon.get_Player_History (payload)
                player = result.get_Players_Name ()

                if player is not None and len (player):
                    return player[:25]
                else:
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    @app_commands.command(name="register_user", description="Combine you Discord user with you T17 account")
    @app_commands.describe(ingame_name="Choose you in game user",)
    @app_commands.choices(vote_reminders=[
        app_commands.Choice(name="Remind me if I haven't voted yet", value=1),
        app_commands.Choice(name="No vote reminders", value=0)
    ])
    async def register_user(self, interaction: discord.Interaction, ingame_name: str, vote_reminders: app_commands.Choice[int] = None):
        try:
            user_name = interaction.user.name
            user_id = interaction.user.id 
            nick_name = interaction.guild.get_member(user_id).nick

            player_id = self.select_T17_Voter_Registration (user_id)

            # Use default True if no choice made
            vote_reminder_value = vote_reminders.value if vote_reminders else 1

            if player_id == None:

                # verify that that ingame_name is a T17 ID
                if bool (re.fullmatch(r"[0-9a-fA-F]{32}", ingame_name)) == False:
                    await interaction.response.send_message('''Something went wrong, please select your name from the\n'''
                                                            '''list and do not add or remove any characters,\n'''
                                                            '''after the selection.''', ephemeral=True)
                else:
                    if config.get("rcon", 0, "register_player", 0, "verify_ingame") == True:
                        number = random.randint(1, 99)
                        data = {"player_id": str (ingame_name) , "message": f"Enter this number in Discord to verify your accont:\n\n{str (number)}" }   

                        logger.info (f"Send verification message to player: {ingame_name} with number: {number}")  
                        await rcon.send_Player_Message (data)

                        modal = Verify_Account (number)
                        await interaction.response.send_modal(modal)
            
                        # wait until the modal is closed
                        await modal.wait()

                        # Ergebnis zurückgeben
                        register = modal.result
                    else:
                        register = True

                    if register:
                        self.insert_Voter_Registration (user_name, user_id, nick_name, ingame_name, vote_reminder_value, 0)

                    # use the enhanced version of register_user
                    # ToDo: needs to be tested
                    # ToDo: needs to check verify_ingame parameter. otherwise -> Unexpected error: This interaction has already been responded to before
                    if config.get("rcon", 0, "name_change_registration", "enabled"):
                        role_error = await handle_roles(member, 'registered')
                        
                        if role_error:
                            message += f"\nNote: {role_error}"

                        member = interaction.guild.get_member(interaction.user.id)
                
                        # Send success embed
                        await send_success_embed(interaction.guild, 
                                                 interaction.user, 
                                                 'registered', 
                                                 member.nick or interaction.user.name,
                                                 ingame_name)
            
                        await interaction.response.send_message(message, ephemeral=True)

                    elif not config.get("rcon", 0, "register_player", 0, "verify_ingame"):
                        await interaction.response.send_message("You are now registered", ephemeral=True)

            else:
                await interaction.response.send_message("You are already registered. If it was't you, please contacht @Techsupport!", ephemeral=True)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    @register_user.autocomplete("ingame_name")
    async def autocomplete_user(self, interaction: discord.Interaction, player_name: str) -> List[app_commands.Choice[str]]:
        try:
            while self.in_Loop:
                await asyncio.sleep (1)
           
            self.in_Loop = True
            name = player_name
            multi_array = None

            if len (name) >= 2:
                logger.info (f"Search query: {name.replace(" ", "%")}")

                multi_array = await self.query_Player_Database(name.replace(" ", "%"))
        
            if multi_array is not None and len (multi_array) >= 1:
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
            logger.error(f"Unexpected error: {e}")
            self.in_Loop = False
            return []

    async def background_task(self):
        while not self.shutdown_event.is_set():
                await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")