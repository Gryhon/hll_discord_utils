import discord
import logging
import asyncio
import time
from rcon.discord.discordbase import DiscordBase 
import rcon.rcon as rcon
from lib.config import config
from datetime import datetime
from discord.ext import commands
from discord import app_commands

# get Logger for this modul
logger = logging.getLogger(__name__)

class Balance (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.webhook_url = config.get("rcon", 0, "server_balance", 0, "webhook")
        self.webhook = discord.SyncWebhook.from_url(self.webhook_url)
        self.msg_id = self.select_Message_Id (__name__)
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.limits = config.get("rcon", 0, "server_balance", 0, "level_categories")
        self.weights = config.get("rcon", 0, "server_balance", 0, "combat_weights")
        self.loop_started = False
    
    def generate_Table(self, categories, data_allies, data_axis, max_value=6):

        table = "```"
        table += "  Level   |   Allies  |    Axis\n"
        table += "------------------------------------\n"

        
        max_count = max (max(data_allies), max(data_axis), 1)

        # Create the intervals based on the categories
        limits = [0] + categories + [500]  # Start at 0, end at 500
        counts_allies = [0] * (len(limits) - 1)
        counts_axis = [0] * (len(limits) - 1)

        # Count the values in the corresponding intervals.
        for value in data_allies:
            for i in range(len(limits) - 1):
                if limits[i] <= value < limits[i + 1]:
                    counts_allies[i] += 1
                    break
 
        for value in data_axis:
            for i in range(len(limits) - 1):
                if limits[i] <= value < limits[i + 1]:
                    counts_axis[i] += 1
                    break
 
        # Calculate the maximum number for the progress bar.
        for i in range(len(categories), -1, -1):
            allies_count = data_allies[i]
            axis_count = data_axis[i]

            # Calculate the bar length relative to the maximum length, each on half side.
            allies_bar_length = allies_count * max_value // max_count
            axis_bar_length = axis_count * max_value // max_count

            # Generate the ASCII bars starting from the center.
            allies_bar = "░" * allies_bar_length
            axis_bar = "░" * axis_bar_length

            # Create a row for the category, arranging the bars around the center.
            line = f"{limits[i]:>3} - {limits[i + 1]:<3} | {allies_count:02} [{allies_bar:>{max_value}}|{axis_bar:<{max_value}}] {axis_count:02}\n"
            table += line + "\n"

        table += "```"
        return table

    async def update_message (self):
        try:
            axis_weight, allies_weight, axis, allies = await rcon.get_Balance (self.limits , self.weights)
            logger.debug ("Allies weight: " + str (allies_weight) + " / Axis weight: " + str (axis_weight))

            wt = discord.Embed(
                title="Game balance",
                description="This function is intended to show how balanced a game is.\n\n",
                color=discord.Color.green(),
                )
   
            wt.add_field(name="\u200b", value="", inline=False)   
            
            text = ("```" + 
                    "    Allies: " + str (round (allies_weight, 1)) + " vs. Axis: " + str (round (axis_weight, 1)) + "```")
                
            wt.add_field(name="Combat strength", value=text, inline=True)
            wt.add_field(name="\u200b", value="", inline=False) 

            table = self.generate_Table (self.limits, allies, axis)

            wt.add_field(name="Balance of forces", value=table, inline=False) 
            
            wt.set_footer(text=f"(Provided by Gryhon)")
            wt.timestamp = datetime.now()
            
            if not self.msg_id:
                self.msg_id = self.webhook.send(embeds=[wt], wait=True).id
                self.insert_Message_Id(__name__, self.msg_id)  
                self.insert_Balance (self.limits, allies, axis)
            else:
                try:
                    # Check if the message still exists.
                    self.webhook.fetch_message(self.msg_id)
                    # Edit the message if it exists.
                    self.webhook.edit_message(message_id=self.msg_id, embeds=[wt])
                    self.insert_Balance (self.limits, allies, axis)

                except discord.NotFound:
                    logger.warning(f"Message with ID {self.msg_id} not found. Sending a new message.")
                    self.msg_id = self.webhook.send(embeds=[wt], wait=True).id
                    self.update_Message_Id (__name__, self.msg_id)
                    self.insert_Balance (self.limits, allies, axis)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def background_task(self):
        last_execution = 0

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or current_time == 0:
                
                try:
                    await self.update_message()

                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                
                last_execution = current_time

            await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

        
