import discord
import logging
import asyncio
import rcon.rcon as rcon
from typing import List
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands


# get Logger for this modul
logger = logging.getLogger(__name__)

class Comfort (commands.Cog, DiscordBase):
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
                players = result.get_Players_Name ()

                if players != None and len (players):
                    return players[:25]
                else:
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    async def send_Broadcast_Message (self, message, players):
        try:
            for player_id in players: 
                payload = None

                payload = {"player_id": str (player_id) , "message": str (message) }   

                if not (config.get("rcon", 0, "comfort_functions", 0, "dryrun")) or player_id in config.get("rcon", 0, "comfort_functions", 0, "probands"):
                    logger.debug("Vote message: " + str (payload)) 
                    await rcon.send_Player_Message (payload)
                else:
                    logger.info("Dry run broadcast message: " + str (payload)) 
                    await asyncio.sleep (0.5) 

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def calculate_Mils (self, distance, min_distance, max_distance, min_mils, max_mils):
        mil = (((distance - min_distance) / (max_distance - min_distance)) * (min_mils - max_mils) + max_mils)
        logger.debug (f"Calculated Mil value for distance {distance} = {mil}")
        return round (mil)

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

    @app_commands.command(name="broadcast_message", description="Broadcast message to players")
    @app_commands.describe(
        fraction="Choose the target audience",
        action="Choose a message you would like to broadcast",
        free_text="Provide your custom message (only for 'Free text' option)"
    )
    @app_commands.choices(fraction=[
        app_commands.Choice(name="Axis", value="axis"),
        app_commands.Choice(name="Allies", value="allies"),
        app_commands.Choice(name="Both fractions", value="both"),
    ])
    @app_commands.choices(action=[
        app_commands.Choice(name="Balance", value="balance"),
        app_commands.Choice(name="The server will be closed after this game", value="shutdown"),
        app_commands.Choice(name="Free text", value="text"),
    ])
    async def broadcast_message(self, interaction: discord.Interaction, fraction: app_commands.Choice[str], action: app_commands.Choice[str], free_text: str = None):
        fraction_value = fraction.value
        action_value = action.value

        message = None

        if action_value == "balance":
            message = "Please balance the server!"

        elif action_value == "shutdown":
            message = "Server will be shutdown after this game. \nThank you for your understanding. \n\nWe look forward to seeing you again!"

        elif action_value == "text":
            if not free_text:
                await interaction.response.send_message("You selected 'Free text', but no custom message was provided!", ephemeral=True)
                return
            
            message = free_text
            
        ingame = await rcon.get_In_Game_Players ()
        players = ingame.get_Ingame_Player_From_Fraction (fraction_value)

        asyncio.create_task(self.send_Broadcast_Message(message, players))
     
        logger.info(f"Broadcast message by {interaction.user.name} to {fraction_value} {'fractions' if fraction_value == 'both' else ''}: {message.replace("\n", "")}")
        await interaction.response.send_message(f"Broadcast message to {fraction_value} {'fractions' if fraction_value == 'both' else ''}:\n{message}")        

    @app_commands.command(name="mil_calculator", description="Calculate mils from distance in meters")
    @app_commands.describe(fraction="Choose a fraction")
    @app_commands.choices(fraction=[
        app_commands.Choice(name="Germany", value="DE"),
        app_commands.Choice(name="USA", value="US"),
        app_commands.Choice(name="USSR", value="USSR"),
        app_commands.Choice(name="England", value="GB"),
    ])
    async def mil_calculator(self, interaction: discord.Interaction, fraction: app_commands.Choice[str]):
        logger.info(f"Mil Calculator used by {interaction.user.name} for fraction {fraction.name}.")

        # Check if the interaction occurs in a text channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Threads can only be created in text channels.", ephemeral=True)
            return

        await interaction.response.send_message(
            "A private thread has been created for your calculation. Please enter the distance in meters.\n"
            "Type `exit` to leave the calculator.",
            ephemeral=True
        )

        # Create a private thread
        private_thread = await interaction.channel.create_thread(
            name=f"{fraction.name} Mil Calculator - {interaction.user}",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=60 # 1440
        )
        await private_thread.add_user(interaction.user)
        await private_thread.send(f"Welcome to your exlusive Mil Calcuator, {interaction.user.mention}!\n\n"
                                   "The thread will be automatically deleted if you enter `exit` or \n"
                                   "after 10 minutes of inactivity.\n\n"
                                   "Valid input values are between 100 and 1600 meters.")

        def check(msg):
            return msg.author == interaction.user and msg.channel == private_thread

        while True:
            try:
                # Wait for user input in the thread
                message = await self.bot.wait_for('message', timeout=600.0, check=check)

                if message.content.lower() == "exit":
                    await private_thread.send("Exiting the calculator. See you next time!")
                    await asyncio.sleep (2) 
                    break

                try:
                    mil_value = None

                    # Parse distance and calculate Mils
                    distance = int(message.content)

                    if distance >= 100 and distance <= 1600:
                        if fraction.value == "DE":
                            mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                        elif fraction.value == "US":
                            mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                        elif fraction.value == "USSR":
                            mil_value = await self.calculate_Mils(distance, 100, 1600, 800, 1120)

                        elif fraction.value == "GB":
                            if (distance >= 200 and distance <= 800) or (distance >= 1100 and distance <= 1200): 
                                dis = distance - 5
                            else:
                                dis = distance

                            mil_value = await self.calculate_Mils(dis, 100, 1600, 267, 533)

                        await private_thread.send(f"Calculated Mil at {distance} meters: {mil_value} Mil.")
                    else:
                        await private_thread.send(f"Distance must be between 100 and 1600 meter!")

                except ValueError:
                    await private_thread.send("Invalid input. Please enter a valid number for the distance.")

            except asyncio.TimeoutError:
                await private_thread.send("Yue are inactive since 10 minutes. The thread will be closed now.")
                await asyncio.sleep (5) 
                break

        await private_thread.delete(reason="Thread cleanup")
        logger.info(f"Close Mil Calculator used by {interaction.user.name} for fraction {fraction.name}.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")


        