import discord
import logging
import asyncio
import random
import time
import re
import rcon.model as model
import rcon.rcon as rcon
from typing import List
from dateutil.parser import parse
from rcon.discord.discordbase import DiscordBase 
from discord.ext import commands
from discord import app_commands
from lib.config import config
from datetime import timedelta, datetime


# get Logger for this modul
logger = logging.getLogger(__name__)

class VoteMap(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.in_Loop = False
        self.do_map_vote = False
        self.vote_map_active = True
        self.reminder_count = 0  # Initialize before reset_Vote_Variables
        self.shutdown_event = asyncio.Event()
        self.seeding_message = ("\nImportant:\n\n"
                                "    Vote function available when\n"
                                "        there are more than\n\n"
                               f"          ** {config.get("rcon", 0, "map_vote", 0, "activate_vote")} Player **\n\n"
                                "          on the server!\n\n")
        self.pause_message = ("\n\n"
                            "       Vote function is paused!\n\n"
                            "   We will inform you in the channel\n"
                            "  when the function is anabled again.\n\n"
                            "             Stay tuned!\n\n")
        self.vote_channel_id = config.get("rcon", 0, "map_vote", 0, "vote_channel_id") 
        self.vote_channel = None   
        self.loop_started = False  
        self.reset_Vote_Variables()  # Call reset after initializing reminder_count

    def reset_Vote_Variables(self):
        if self.reminder_count > 0:
            logger.info(f"Resetting vote variables. Sent {self.reminder_count} reminders this game")
        self.vote_msg = None
        self.vote_msg_id = None
        self.seeding_msg = None
        self.game_start = None
        self.game_active = None
        self.vote_active = False
        self.game_id = None
        self.current_map = None
        self.Maps = None
        self.vote_results = []
        self.reminder_count = 0
        self.last_execution = None
        self.send_seeding_message = True
        self.seeded = False
        logger.debug("Vote variables reset")

[... rest of the file remains unchanged ...]
