import logging
import asyncio
import time
import discord
import math
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase 
from lib.config import config
from discord.ext import commands
from fuzzywuzzy import fuzz
import textdistance
import jellyfish
from discord.ui import Button, View
from cachetools import TTLCache

# get Logger for this modul
logger = logging.getLogger(__name__)

class InappropriateName (commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.last_check = None
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False
        self.last_active = 0
        self.inappropriate = config.get("rcon", 0, "inappropriate_name", 0, "inappropriate")
        self.channel = None
        self.channel_id = config.get("rcon", 0, "inappropriate_name", 0, "channel_id") 
        self.cache = TTLCache(maxsize=300, ttl=5400)
        self.suspicious = TTLCache(maxsize=300, ttl=5400)

    async def kick_Player (self, player_name, player_id, reason, comment):
        try:
            payload = {
                "player_name": player_name,
                "player_id": player_id,
                "reason": reason,
                "comment": comment
            }
            
            if not (config.get("rcon", 0, "auto_level", 0, "dryrun")):
                logger.debug (f"Kick Player: {player_name} ")
                await rcon.kick_Player (payload)
            else:
                logger.info (f"Dry run Kick Player: {player_name} ID: {player_id}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def clear_All_Messages (self, expect=None, interaction=True):
        try:
            async for msg in self.channel.history(limit=100):  

                if msg.author == self.bot.user:

                    if not msg.interaction_metadata or msg.interaction_metadata and interaction:
                        if not expect or (expect and expect != msg.id):
                            await msg.delete() 
                            logger.info ("Delete old message ID: " + str (msg.id))
                            
                        await asyncio.sleep(1)

        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def get_Phonetic_Similarity_Score(self, name1, name2):
        try:
            soundex1 = jellyfish.soundex(name1)
            soundex2 = jellyfish.soundex(name2)

            return fuzz.ratio(soundex1, soundex2)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
    async def get_Similarity_Scores(self, name1, name2):
        return {
            "fuzz_ratio": fuzz.ratio(name1, name2),
            "fuzz_partial_ratio": fuzz.partial_ratio(name1, name2),
            "fuzz_token_sort_ratio": fuzz.token_sort_ratio(name1, name2),
            "jaro_winkler": textdistance.jaro_winkler.normalized_similarity(name1, name2) * 100,
            "levenshtein": textdistance.levenshtein.normalized_similarity(name1, name2) * 100,
            "soundex": await self.get_Phonetic_Similarity_Score(name1, name2),
        }
    
        # fuzz.ratio: Gut für allgemeine Ähnlichkeitsbewertung.
        # fuzz.partial_ratio: Ideal, wenn ein String einen Teil des anderen enthält.
        # fuzz.token_sort_ratio: Sinnvoll bei unterschiedlichen Wortreihenfolgen.
        # jaro_winkler: Präzise, wenn Präfixe wichtig sind. 
        # levenshtein: Exakt für genaue Zeichenanpassung.
    
    async def get_Best_Match(self, name1, name_list):
        best_match = None
        best_method = None
        best_score = -1
        best_scores = {}

        for name2 in name_list:
            scores = await self.get_Similarity_Scores(name1, name2)
            max_method = max(scores, key=scores.get)
            max_score = scores[max_method]

            if max_score > best_score:
                best_match = name2
                best_method = max_method
                best_score = max_score
                best_scores = {name2: scores}

        return best_match, best_method, best_score, best_scores

    async def check_Players (self, players):
        try:
            for player in players:

                if player.player_id not in self.cache:

                    self.cache[f"{player.player_id}"] = player.name
                    best_match, _, best_score, best_scores = await self.get_Best_Match(player.name, self.inappropriate)

                    #logger.info (f"Bestscore for {player.name}: {best_score}")

                    if best_score >= config.get("rcon", 0, "inappropriate_name", 0, "probability_1"):

                        for scores in best_scores.items():
                            logger.info(f"{player.name}: {scores}")

                        scores_above = sum(1 for score in best_scores[best_match].values() if score >= config.get("rcon", 0, "inappropriate_name", 0, "probability_2"))

                        if scores_above >= config.get("rcon", 0, "inappropriate_name", 0, "probability_cnt") and player.player_id not in self.suspicious:

                            result = self.select_Inappropriate_Name (player.player_id)
                            # ToDo: check decision but verify that the name is still the same

                            if result != None:
                                msg_id, player_name, decision = result[0]

                            msg = None

                            if result != None and player_name == player.name:
                                try:
                                    msg = await self.channel.fetch_message(msg_id)
                                    self.bot.add_view(View(timeout=None), message_id=msg.id)
                                except discord.NotFound:
                                    msg = None                                

                            if msg == None or player.name != player_name:

                                message = ("Found:\n"
                                        "```"
                                        f"Player: '{player.name}'\n"
                                        f"ID: '{player.player_id}'\n"
                                        "```"
                                        "Details:"
                                        f"```"
                                        f"Best match: '{best_match}'\n"
                                        f"{"".join("\n".join(f"  {method}: {score:.2f}" for method, score in scores.items()) for name, scores in best_scores.items())}```")
                                
                                view = View()
                                view.add_item(Button(label="Blacklist", style=discord.ButtonStyle.danger, custom_id=f"blacklist_{player.name}_{player.player_id}"))
                                view.add_item(Button(label="Watch", style=discord.ButtonStyle.secondary, custom_id=f"watch_{player.name}_{player.player_id}"))
                                view.add_item(Button(label="Ignore", style=discord.ButtonStyle.success, custom_id=f"ignore_{player.name}_{player.player_id}"))

                                msg = await self.channel.send(message, view=view)

                                logger.info (message.replace("\n", " ").replace("`", ""))
                                self.suspicious[f"{player.player_id}"] = player.name
                                self.insert_Inappropriate_Name (player.player_id, player.name, "", msg.id)                         

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def check_Ingame_Player (self):
        try:
            players = await rcon.get_Players ()

            await self.check_Players (players.players)
                  
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def check_History_Player (self):
        try:
            
            page = 1
            payload ={"page_size": 100, "page": page}

            players = await rcon.get_Player_History (payload)

            cnt = players.get_Total_Player_Count ()

            pages = math.ceil(cnt / 50)

            logger.info (f"Start verify {cnt} player on {pages} pages.")

            for i in range(1, pages):
                payload["page"] = i
                players = await rcon.get_Player_History (payload)
                await self.check_Players (players.get_Players ())

            logger.info (f"End checking.")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data["custom_id"]
            player_name = custom_id.split("_")[1]
            player_id = custom_id.split("_")[2]

            if custom_id.startswith("blacklist"):
                payload = {"blacklist_id": config.get("rcon", 0, "inappropriate_name", 0, "blacklist_id"), 
                           "player_id" : f"{player_id}",
                           "reason": f"{config.get("rcon", 0, "inappropriate_name", 0, "blacklist_message")}"}
                
                if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun"):
                    await rcon.add_Blacklist_Record (payload)
                    self.update_Inappropriate_Name(player_id, "inanme_decision", "blacklist")
                else:
                    logger.info (f"Dry run ban player: {payload}")

                await interaction.response.send_message(f"{player_name} has been banned.")

            elif custom_id.startswith("watch"):

                payload = {"player_name": f"{player_name}", 
                           "player_id": f"{player_id}", 
                           "reason" : f"{config.get("rcon", 0, "inappropriate_name", 0, "watch_message")}",
                           "by": f"{interaction.user.name}"}
                
                if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun"):
                    await rcon.set_Watch_Player (payload)
                    self.update_Inappropriate_Name(player_id, "inanme_decision", "watch")
                else:
                    logger.info (f"Dry run watch player: {payload}")

                await interaction.response.send_message(f"{player_name} is being watched.")

            elif custom_id.startswith("ignore"):
                await interaction.response.send_message(f"{player_name} has been ignored.")
                self.update_Inappropriate_Name(player_id, "inanme_decision", "ignore")


    async def background_task(self):
        last_execution = 0
        self.channel = self.bot.get_channel(self.channel_id)

        #await self.check_History_Player ()
        #await self.clear_All_Messages ()

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or last_execution == 0:
                
                try:
                    await self.check_Ingame_Player()

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

# ToDo:
#   - new registration of existing messages and delete any old messges
#   - discord command to check player database
#   - discord command only available for specific roles
#   - change buttons according to the decision or delete the message after the decision was done (maybe time delay)