import discord
import logging
import asyncio
import random
import time
import rcon.rcon as rcon
from dateutil.parser import parse
from rcon.discord.discordbase import DiscordBase
from discord.ext import commands
from discord import app_commands
from lib.config import config
from datetime import timedelta, datetime

logger = logging.getLogger(__name__)


class RotationVote(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.shutdown_event = asyncio.Event()
        self.vote_channel_id = config.get("rcon", 0, "map_rotation_vote", 0, "vote_channel_id")
        self.vote_channel = None
        self.loop_started = False
        self.is_running = False
        self.last_reminder_time = None
        self.reminder_count_this_game = 0
        self.last_game_start = None

    def reset_state(self):
        self.last_reminder_time = None
        self.reminder_count_this_game = 0
        self.last_game_start = None

    def build_poll_title(self, part, total, start_date, end_date) -> str:
        start_str = start_date.strftime("%d/%m/%y")
        end_str = end_date.strftime("%d/%m/%y")
        header = config.get("rcon", 0, "map_rotation_vote", 0, "vote_header")
        if total > 1:
            return f"{header} {start_str} → {end_str} (Part {part}/{total})"
        return f"{header} {start_str} → {end_str}"

    async def get_rotation_maps(self):
        try:
            result = []
            blacklist = list(config.get("rcon", 0, "map_rotation_vote", 0, "map_pool", 0, "blacklist_maps"))
            enforced_maps = config.get("rcon", 0, "map_rotation_vote", 0, "map_pool", 0, "enforced_maps")
            logger.info(f"Rotation vote blacklist: {blacklist}")

            all_maps = await rcon.get_Maps()

            if not all_maps or not all_maps.json or "result" not in all_maps.json:
                logger.error("No map data returned from API")
                return None

            raw = all_maps.json["result"]
            battle_mode = config.get("rcon", 0, "map_rotation_vote", 0, "map_pool", 0, "battle_mode")

            def pick_env(env, count):
                candidates = [
                    m["id"] for m in raw
                    if m.get("environment") == env
                    and m.get("id") not in blacklist
                    and (not battle_mode or m.get("game_mode") in battle_mode)
                ]
                if count == 0 or not candidates:
                    return []
                return random.sample(candidates, min(count, len(candidates)))

            # Day maps always included in full
            day_maps = [
                m["id"] for m in raw
                if m.get("environment") == "day"
                and m.get("id") not in blacklist
                and (not battle_mode or m.get("game_mode") in battle_mode)
            ]
            result.extend(day_maps)
            logger.info(f"Day maps added ({len(day_maps)}): {day_maps}")

            for env in ("dusk", "overcast", "night"):
                count = config.get("rcon", 0, "map_rotation_vote", 0, "map_pool", 0, env)
                picked = pick_env(env, count)
                if picked:
                    result.extend(picked)
                    logger.info(f"{env.capitalize()} maps added ({len(picked)}): {picked}")

            if enforced_maps:
                result = [m for m in result if m not in enforced_maps]
                result = enforced_maps + result
                logger.info(f"Enforced maps added to poll: {enforced_maps}")

            random.shuffle(result)
            logger.info(f"Rotation vote map pool ({len(result)} maps): {result}")
            all_maps.get_Maps_from_ID(result)
            return all_maps

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    async def start_rotation_vote(self, interaction=None):
        sent_messages = []
        try:
            active = self.select_Active_Rotation_Votes()
            if active:
                msg = "A rotation vote is already active."
                logger.warning(msg)
                if interaction:
                    await interaction.followup.send(msg, ephemeral=True)
                return False

            await self.cleanup_old_polls()

            maps = await self.get_rotation_maps()
            if not maps or not maps.maps:
                msg = "Failed to select maps for rotation vote."
                logger.error(msg)
                if interaction:
                    await interaction.followup.send(msg, ephemeral=True)
                return False

            duration_hours = config.get("rcon", 0, "map_rotation_vote", 0, "duration_hours", default=0)
            if not duration_hours:
                duration_hours = config.get("rcon", 0, "map_rotation_vote", 0, "duration_days") * 24
            maps_per_poll = config.get("rcon", 0, "map_rotation_vote", 0, "maps_per_poll")

            if duration_hours < 1:
                logger.warning(f"duration_hours {duration_hours} is below Discord minimum of 1h, capping at 1.")
                duration_hours = 1
            if duration_hours > 168:
                logger.warning(f"duration_hours {duration_hours} exceeds Discord limit of 168h, capping at 168.")
                duration_hours = 168
            if maps_per_poll > 10:
                maps_per_poll = 10

            map_list = maps.maps
            chunks = [map_list[i:i + maps_per_poll] for i in range(0, len(map_list), maps_per_poll)]
            total_parts = len(chunks)

            start_date = datetime.now()
            end_date = start_date + timedelta(hours=duration_hours)

            for part_idx, chunk in enumerate(chunks, start=1):
                title = self.build_poll_title(part_idx, total_parts, start_date, end_date)
                poll = discord.Poll(
                    question=discord.PollMedia(title, emoji=None),
                    duration=timedelta(hours=duration_hours),
                    multiple=True
                )
                for map_item in chunk:
                    poll.add_answer(text=map_item.pretty_name, emoji=None)

                msg = await self.vote_channel.send(poll=poll)
                sent_messages.append((msg, part_idx))
                logger.info(f"Rotation vote Part {part_idx}/{total_parts} posted, msg_id={msg.id}")

            start_str = start_date.isoformat()
            end_str = end_date.isoformat()
            for msg, part in sent_messages:
                self.insert_Rotation_Vote(msg.id, part, start_str, end_str)

            self.last_reminder_time = time.time()

            result_msg = (
                f"Rotation vote started: {total_parts} poll(s) | "
                f"{start_date.strftime('%d/%m/%y')} → {end_date.strftime('%d/%m/%y')} | "
                f"{len(map_list)} maps total"
            )
            logger.info(result_msg)
            if interaction:
                await interaction.followup.send(result_msg)
            return True

        except discord.HTTPException as e:
            logger.error(f"HTTP error during rotation vote start, rolling back: {e}")
            for msg, _ in sent_messages:
                try:
                    await msg.delete()
                except Exception:
                    pass
            self.delete_Rotation_Votes()
            if interaction:
                await interaction.followup.send(f"Failed to create rotation vote polls: {e}", ephemeral=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if interaction:
                await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)
            return False

    async def collect_results(self):
        """Aggregate vote counts across all active polls. Returns list of (map_name, count) sorted desc."""
        try:
            active = self.select_Active_Rotation_Votes()
            if not active:
                return []

            totals = {}
            for msg_id, part in active:
                try:
                    msg = await self.vote_channel.fetch_message(msg_id)
                    for answer in msg.poll.answers:
                        totals[answer.text] = totals.get(answer.text, 0) + answer.vote_count
                except discord.NotFound:
                    logger.warning(f"Poll message {msg_id} (Part {part}) not found")
                except Exception as e:
                    logger.error(f"Error fetching poll {msg_id}: {e}")

            return sorted(totals.items(), key=lambda x: x[1], reverse=True)

        except Exception as e:
            logger.error(f"Unexpected error collecting results: {e}")
            return []

    async def _save_to_history(self, map_ids):
        try:
            active = self.select_Active_Rotation_Votes()
            start_date, end_date = self.select_Rotation_Vote_Dates()
            msg_ids_str = "|".join(str(msg_id) for msg_id, _ in active)
            maps_str = "|".join(map_ids)
            self.insert_Rotation_Vote_History(start_date, end_date, maps_str, msg_ids_str)
            logger.info(f"Rotation vote history saved: {maps_str}")
        except Exception as e:
            logger.error(f"Unexpected error saving rotation vote history: {e}")

    async def cleanup_old_polls(self):
        try:
            msg_ids_str = self.select_Last_Rotation_Vote_History_Msg_Ids()
            if not msg_ids_str:
                return
            for msg_id in msg_ids_str.split("|"):
                try:
                    msg = await self.vote_channel.fetch_message(int(msg_id))
                    await msg.delete()
                    logger.info(f"Deleted old rotation vote poll message {msg_id}")
                except discord.NotFound:
                    pass
                except Exception as e:
                    logger.error(f"Error deleting old poll message {msg_id}: {e}")
            self.clear_Last_Rotation_Vote_History_Msg_Ids()

            async for message in self.vote_channel.history(limit=50):
                if message.type == discord.MessageType.poll_result:
                    try:
                        await message.delete()
                        logger.info(f"Deleted poll result system message {message.id}")
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        logger.error(f"Error deleting poll result system message {message.id}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error cleaning up old polls: {e}")

    async def apply_results(self):
        """Resolve top-voted map pretty names to IDs and set the rotation."""
        try:
            results = await self.collect_results()
            if not results:
                logger.warning("No rotation vote results to apply")
                return False

            top_n = config.get("rcon", 0, "map_rotation_vote", 0, "top_maps_to_set")
            top_names = [name for name, _ in results[:top_n]]

            all_maps = await rcon.get_Maps()
            all_maps.get_Maps_from_PrettyName(top_names)
            map_ids = [m.id for m in all_maps.maps]

            if not map_ids:
                logger.error("Could not resolve any map IDs from rotation vote results")
                return False

            await self._save_to_history(map_ids)

            logger.info(f"Applying rotation vote result: {map_ids}")
            if not config.get("rcon", 0, "map_rotation_vote", 0, "dryrun"):
                await rcon.set_Map_Rotation({"map_names": map_ids})
                logger.info("Map rotation updated from rotation vote")
            else:
                logger.info(f"Dry run: would set rotation to {map_ids}")

            return True

        except Exception as e:
            logger.error(f"Unexpected error applying rotation vote results: {e}")
            return False

    async def end_rotation_vote(self, interaction=None):
        try:
            active = self.select_Active_Rotation_Votes()
            if not active:
                msg = "No active rotation vote found."
                logger.warning(msg)
                if interaction:
                    await interaction.followup.send(msg, ephemeral=True)
                return False

            for msg_id, part in active:
                try:
                    msg = await self.vote_channel.fetch_message(msg_id)
                    if not msg.poll.is_finalised():
                        await msg.poll.end()
                        logger.info(f"Ended rotation vote poll Part {part} (msg_id={msg_id})")
                except discord.NotFound:
                    logger.warning(f"Poll message {msg_id} not found during end")
                except Exception as e:
                    logger.error(f"Error ending poll {msg_id}: {e}")

            await self.apply_results()
            self.delete_Rotation_Votes()
            self.reset_state()

            result_msg = "Rotation vote ended and map rotation updated."
            logger.info(result_msg)
            if interaction:
                await interaction.followup.send(result_msg)
            return True

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if interaction:
                await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)
            return False

    async def send_in_game_reminder(self):
        try:
            vote_header = config.get("rcon", 0, "map_rotation_vote", 0, "vote_header")
            end_date = self.select_Rotation_Vote_End_Date()
            if end_date:
                text = f"{vote_header}\n\nVote ends: {end_date}"
            else:
                text = vote_header

            players = await rcon.get_Players()
            for player in players.players:
                registration = self.select_T17_Voter_Registration_By_T17ID(player.player_id)
                wants_reminders = True
                if registration is not None:
                    _, _, _, _, ask_reg_cnt = registration
                    if ask_reg_cnt is not None:
                        wants_reminders = bool(ask_reg_cnt)

                if wants_reminders:
                    data = {"player_id": str(player.player_id), "message": text}
                    if not config.get("rcon", 0, "map_rotation_vote", 0, "stealth_vote"):
                        if not config.get("rcon", 0, "map_rotation_vote", 0, "dryrun"):
                            await rcon.send_Player_Message(data)
                        else:
                            logger.debug(f"Dry run: reminder to {player.name}")

            logger.info("In-game rotation vote reminder sent")
            self.last_reminder_time = time.time()
            self.reminder_count_this_game += 1

        except Exception as e:
            logger.error(f"Unexpected error sending in-game reminder: {e}")

    async def check_and_send_reminder(self):
        try:
            reminder_interval_hours = config.get("rcon", 0, "map_rotation_vote", 0, "reminder_interval_hours", default=24)
            max_reminders = config.get("rcon", 0, "map_rotation_vote", 0, "max_reminders_per_game", default=1)
            reminder_interval = reminder_interval_hours * 3600

            current_map = await rcon.get_Current_Map()
            if current_map:
                game_start = parse(current_map.start).timestamp()
                if game_start != self.last_game_start:
                    self.last_game_start = game_start
                    self.reminder_count_this_game = 0
                    logger.info("New game detected, resetting rotation vote reminder counter")

            if self.last_reminder_time is None:
                self.last_reminder_time = time.time()
                return

            time_since_last = time.time() - self.last_reminder_time
            can_remind = max_reminders == 0 or self.reminder_count_this_game < max_reminders

            if time_since_last >= reminder_interval and can_remind:
                logger.info(f"Sending rotation vote reminder ({self.reminder_count_this_game + 1})")
                await self.send_in_game_reminder()

        except Exception as e:
            logger.error(f"Unexpected error checking reminders: {e}")

    async def check_poll_expiry(self, active):
        """Auto-apply results when all polls have expired. Returns True if polls were cleared."""
        try:
            all_finalised = True
            for msg_id, part in active:
                try:
                    msg = await self.vote_channel.fetch_message(msg_id)
                    if not msg.poll.is_finalised():
                        all_finalised = False
                        break
                except discord.NotFound:
                    logger.warning(f"Poll {msg_id} not found during expiry check, treating as finalised")
                except Exception as e:
                    logger.error(f"Error checking poll expiry {msg_id}: {e}")
                    all_finalised = False
                    break

            if all_finalised:
                logger.info("All rotation vote polls expired — applying results automatically")
                await self.apply_results()
                self.delete_Rotation_Votes()
                self.reset_state()
                await self.start_rotation_vote()
                return True

            return False

        except Exception as e:
            logger.error(f"Unexpected error checking poll expiry: {e}")
            return False

    async def do_rotation_vote(self):
        try:
            active = self.select_Active_Rotation_Votes()
            if not active:
                return

            cleared = await self.check_poll_expiry(active)
            if not cleared:
                await self.check_and_send_reminder()

        except Exception as e:
            logger.error(f"Unexpected error in do_rotation_vote: {e}")

    async def background_task(self):
        try:
            self.vote_channel = self.bot.get_channel(self.vote_channel_id)

            while not self.shutdown_event.is_set():
                if not self.is_running:
                    self.is_running = True
                    try:
                        await self.do_rotation_vote()
                    except Exception as e:
                        logger.error(f"Background task error: {e}")
                    finally:
                        self.is_running = False

                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Rotation vote background task stopped.")

    @app_commands.command(name="rotation_vote", description="Manage the map rotation vote")
    @app_commands.describe(action="Choose an action for the rotation vote")
    @app_commands.choices(action=[
        app_commands.Choice(name="start", value="start"),
        app_commands.Choice(name="stop", value="stop"),
        app_commands.Choice(name="status", value="status"),
    ])
    async def rotation_vote_command(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer()

        if action == "start":
            logger.info(f"Rotation vote start requested by {interaction.user.name}")
            await self.start_rotation_vote(interaction)

        elif action == "stop":
            logger.info(f"Rotation vote stop requested by {interaction.user.name}")
            await self.end_rotation_vote(interaction)

        elif action == "status":
            active = self.select_Active_Rotation_Votes()
            if not active:
                await interaction.followup.send("No active rotation vote.", ephemeral=True)
                return

            end_date = self.select_Rotation_Vote_End_Date()
            results = await self.collect_results()
            top_n = config.get("rcon", 0, "map_rotation_vote", 0, "top_maps_to_set")

            lines = [f"**Map Rotation Vote** (ends {end_date}) — top {top_n} maps will be set:\n"]
            for i, (name, count) in enumerate(results, start=1):
                marker = "✓" if i <= top_n else " "
                lines.append(f"`{marker}` {i}. **{name}** — {count} votes")

            if not results:
                lines.append("No votes yet.")

            logger.info(f"Rotation vote status requested by {interaction.user.name}")
            await interaction.followup.send("\n".join(lines))

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Rotation vote background task started")
