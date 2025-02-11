import discord
import logging
import asyncio
import numpy as np
import rcon.rcon as rcon
from typing import List
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from discord import app_commands


# get Logger for this modul
logger = logging.getLogger(__name__)

class ArtilleryCalculator (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()  
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def calculate_Mils (self, distance, min_distance, max_distance, min_mils, max_mils):
        mil = (((distance - min_distance) / (max_distance - min_distance)) * (min_mils - max_mils) + max_mils)
        logger.debug (f"Calculated Mil value for distance {distance} = {mil}")
        return round (mil)
    
    async def calculate (self, distance, fraction):
        try:
            mil_value = None

            if distance >= 100 and distance <= 1600:
                if fraction == "DE":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                elif fraction == "US":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                elif fraction == "USSR":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 800, 1120)

                elif fraction == "GB":
                    if (distance >= 200 and distance <= 800) or (distance >= 1100 and distance <= 1200): 
                        dis = distance - 5
                    else:
                        dis = distance
                
                    mil_value = await self.calculate_Mils(dis, 100, 1600, 267, 533)
                else:
                    logger.info(f"Unknown fraction: {fraction}")

            return mil_value
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    async def calculate_Intervall(self, distance: int, fraction: str, intervall: int):
        try:
            half_interval = intervall / 2
            lower_bound = max(100, distance - half_interval)
            upper_bound = min(1600, distance + half_interval)

            # Adjust the interval if it exceeds the limits
            if lower_bound == 100:
                upper_bound = min(100 + intervall, 1600)
            elif upper_bound == 1600:
                lower_bound = max(1600 - intervall, 100)

            # Ensure the given distance value is included
            meters = np.linspace(lower_bound, upper_bound, num=9)
            meters = sorted(set(map(lambda x: int(round(x)), meters)), reverse=True)  # Sortiere absteigend

            if distance not in meters:
                meters.append(distance)
                meters = sorted(meters, reverse=True)  # Sortiere erneut absteigend

            # MILs berechnen, aber in der gleichen Reihenfolge wie meters
            MILs = [await self.calculate(m, fraction) for m in meters]

            return await self.create_Table(meters, MILs, distance)

        except Exception:
            logger.exception("Unexpected error")
            return None
        
    async def create_Table(self, meters: list, MILs: list, distance: int):
        try:
            table = "METER  |  MILS\n" + "-" * 16 + "\n"
            for m, mil in zip(meters, MILs):
                mark_left = "--> " if m == distance else " "
                mark_right = " <--" if m == distance else " "
                table += f"{mark_left}{m:04}  |  {mil:4}{mark_right}\n"
            
            return table
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep (5)

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
                        mil_value = await self.calculate (distance, fraction.value)

                        if config.get("rcon", 0, "artillery_calculator", 0, "in_game_messages", default=False):
                            
                            player_id, _, _, _, _ = self.select_T17_Voter_Registration (interaction.user.id)
                            ingame = await rcon.get_In_Game_Players ()                       
                            
                            if ingame.is_Player_Ingame (player_id) == True:
                                table = await self.calculate_Intervall (distance, fraction.value, config.get("rcon", 0, "artillery_calculator", 0, "interval", default=100))

                                if table is not None:
                                    logger.info(f"Send message to player {player_id} with table for distance: {distance}m / {mil_value} MILs.")
                                    data = {"player_id": str(player_id), "message": table}
                                    await rcon.send_Player_Message(data)
                            else:
                                logger.debug(f"Player {player_id} is not ingame. No mail sent.")

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


        