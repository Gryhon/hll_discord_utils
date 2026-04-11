import discord
import logging
import asyncio
import time
import math
import rcon.model as model
import rcon.rcon as rcon
import lib.utils as utils
from lib.fuzzynamematcher import FuzzyNameMatcher
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from datetime import datetime, timezone, timedelta
from discord.ext import commands

# get Logger for this modul
logger = logging.getLogger(__name__)


def calculate_Expires_At(duration_days: int) -> str | None:
    if duration_days == 0:
        return None

    expires = datetime.now(timezone.utc) + timedelta(days=duration_days)
    expires = expires.replace(hour=23, minute=59, second=59, microsecond=999000)
    return f"{expires.strftime('%Y-%m-%dT%H:%M:%S')}.{expires.microsecond // 1000:03d}Z"


class InappropriateView(discord.ui.View):
    """Buttons for a reported name violation.

    The custom_ids of the buttons contain the player_id so that the bot can map incoming
    interactions back to the correct entry after a restart (Persistent View).
    Restore: bot.add_view(InappropriateView(player_id, ...), message_id=int(msg_id))
    """

    def __init__(self, player_id: str, name: str, clan_tag: str | None, flagged_value: str, cog,
                 action_taken: bool = False):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.name = name
        self.clan_tag = clan_tag
        self.flagged_value = flagged_value
        self.cog = cog

        # Stable custom_ids for persistence across bot restarts.
        for item in self.children:
            item.custom_id = f"inaname_{item.label.lower()}_{player_id}"

        # Initial state: Reopen is only active if an action has already been taken
        # (watch/ban/whitelist). For new alerts (action_taken=False) Reopen is disabled.
        for item in self.children:
            if item.row == 0:
                item.disabled = action_taken      # Action buttons disabled if action already taken
            elif item.label == "Reopen":
                item.disabled = not action_taken  # Reopen active only after an action was taken

    def set_Action_Buttons_Disabled(self, disabled: bool):
        """Enables or disables the action buttons (row 0) without touching the management buttons."""
        for item in self.children:
            if item.row == 0:
                item.disabled = disabled

    def set_Reopen_Disabled(self, disabled: bool):
        for item in self.children:
            if item.label == "Reopen":
                item.disabled = disabled

    async def finish_Action(self, interaction: discord.Interaction, footer: str, color: discord.Color, decision: str):
        """Disable action buttons, enable Reopen, update embed, and set DB entry."""
        self.cog.update_Inappropriate_Name(self.player_id, "inanme_decision", decision)

        if decision == "watch":
            
            payload = {
                "player_id": self.player_id,
                "reason": config.get("rcon", 0, "inappropriate_name", 0, "watch_message", default=None),
                "by": interaction.user.name,
                "player_name": self.name
            }

            if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun", default=False):
                logger.info(f"Player_id={self.player_id} name='{self.name}' set to WATCH by {interaction.user}")
                await rcon.set_Watch_Player(payload)
            else:
                logger.info(f"DryRun - Player_id={self.player_id} name='{self.name}' set to WATCH by {interaction.user}")

        elif decision == "ban":

            payload = {
                "player_id": self.player_id,
                "blacklist_id": config.get("rcon", 0, "inappropriate_name", 0, "blacklist_id", default=None),
                "reason": config.get("rcon", 0, "inappropriate_name", 0, "blacklist_message", default=None),
                "expires_at": calculate_Expires_At(config.get("rcon", 0, "inappropriate_name", 0, "blacklist_duration", default=0))
            }

            if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun", default=False):
                logger.info(f"Player_id={self.player_id} name='{self.name}' banned by {interaction.user}")
                await rcon.add_Blacklist_Record(payload)
            else:
                logger.info(f"DryRun - Player_id={self.player_id} name='{self.name}' banned by {interaction.user}")

        self.set_Action_Buttons_Disabled(True)
        self.set_Reopen_Disabled(False)
        embed = interaction.message.embeds[0]
        embed.color = color
        embed.set_footer(text=footer)
        await interaction.response.edit_message(embed=embed, view=self)

    # --- Row 0: Action buttons ---

    @discord.ui.button(label="Watch", style=discord.ButtonStyle.secondary, emoji="👁️", row=0)
    async def watch(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Watch requested for player_id={self.player_id} name='{self.name}' by {interaction.user}")
        await self.finish_Action(interaction, f"Watching — set by {interaction.user.display_name}",
                                  discord.Color.yellow(), "watch")

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🔨", row=0)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Ban requested for player_id={self.player_id} name='{self.name}' by {interaction.user}")
        await self.finish_Action(interaction, f"Ban requested by {interaction.user.display_name} — execute manually",
                                  discord.Color.dark_red(), "ban")

    @discord.ui.button(label="Whitelist", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def whitelist(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Whitelisted player_id={self.player_id} name='{self.name}' by {interaction.user}")
        await self.finish_Action(interaction, f"Whitelisted by {interaction.user.display_name}",
                                  discord.Color.green(), "whitelist")

    # --- Row 1: Management buttons ---

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Resets the entry to 'pending', enables action buttons, and disables itself.
        Reads the previous decision from the DB to reverse any API actions if necessary."""
        result = self.cog.select_Inappropriate_Name(self.player_id)
        previous_decision = result[0][2] if result else None

        if previous_decision == "ban":

            payload = {
                "player_id": self.player_id
            }

            if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun", default=False):
                logger.info(f"Reopen: player_id={self.player_id} name='{self.name}' was BANNED — removing from blacklist by {interaction.user}")
                await rcon.set_Unban(payload)
            else:
                logger.info(f"DryRun - Reopen: player_id={self.player_id} name='{self.name}' was BANNED — removing from blacklist by {interaction.user}")
        
        elif previous_decision == "watch":         

            payload = {
                "message": "",
                "player_id": self.player_id,
                "player_name": self.name,
                "reason": ""
            }

            if not config.get("rcon", 0, "inappropriate_name", 0, "dryrun", default=False):
                logger.info(f"Reopen: player_id={self.player_id} name='{self.name}' was on WATCH — removing from watchlist by {interaction.user}")
                await rcon.set_Unwatch_Player(payload)
            else:
                logger.info(f"DryRun - Reopen: player_id={self.player_id} name='{self.name}' was on WATCH — removing from watchlist by {interaction.user}")

        self.cog.update_Inappropriate_Name(self.player_id, "inanme_decision", "pending")
        logger.info(f"Reopened player_id={self.player_id} name='{self.name}' (previous='{previous_decision}') by {interaction.user}")
        self.set_Action_Buttons_Disabled(False)
        self.set_Reopen_Disabled(True)
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text="Action required")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deletes the Discord message. Only deletes the DB entry if no action
        (watch/ban/whitelist) has been taken yet — otherwise the entry is kept."""
        result = self.cog.select_Inappropriate_Name(self.player_id)
        decision = result[0][2] if result else None
        if decision == "pending":
            self.cog.delete_Inappropriate_Name(self.player_id)
            logger.info(f"Deleted message and DB entry (was pending) for player_id={self.player_id} name='{self.name}' by {interaction.user}")
        else:
            logger.info(f"Deleted message (kept DB entry, decision='{decision}') for player_id={self.player_id} name='{self.name}' by {interaction.user}")
        await interaction.message.delete()


class Inappropriate(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.last_check = None
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False

        self.inappropriate = FuzzyNameMatcher(config.get("rcon", 0, "inappropriate_name", 0, "threshold", default=0.85))
        self.inappropriate.set_namelist(config.get("rcon", 0, "inappropriate_name", 0, "blacklist", default=[]))
        self.inappropriate.set_whitelist(config.get("rcon", 0, "inappropriate_name", 0, "whitelist", default=[]))

        self._channel_id = config.get("rcon", 0, "inappropriate_name", 0, "channel_id", default=None)

    # --- Reporting ---

    def is_Whitelisted(self, player_id: str) -> bool:
        """True if this player is marked as whitelisted in the DB."""
        result = self.select_Inappropriate_Name(player_id)
        if not result:
            return False
        _, _, decision = result[0]
        return decision == "whitelist"

    def already_Open(self, player_id: str) -> bool:
        """True if there is already an open entry for this player in the DB
        (pending, watch, or ban — i.e. not yet finally decided)."""
        result = self.select_Inappropriate_Name(player_id)
        if not result:
            return False
        _, _, decision = result[0]
        return decision in ("pending", "watch", "ban")

    async def send_Alert(self, player_id: str, name: str, threshold: float, finding: str,
                          clan_tag: str = None, flagged_value: str = None):
        """Send Discord embed with buttons and save entry to DB."""
        msg_id = None

        channel = self.bot.get_channel(int(self._channel_id)) if self._channel_id else None

        if channel:
            try:
                embed = discord.Embed(
                    title="⚠️ Inappropriate Player Name Detected",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="Player Name", value=f"`{name}`", inline=False)
                if clan_tag:
                    embed.add_field(name="Clan Tag", value=f"`{clan_tag}`", inline=True)
                embed.add_field(name="Player ID", value=f"`{player_id}`", inline=False)
                embed.add_field(name="Flagged", value=f"`{flagged_value or name}`", inline=True)
                embed.add_field(name="Matched Term", value=f"`{finding}`", inline=True)
                embed.add_field(name="Score", value=f"`{threshold:.0%}`", inline=True)
                embed.set_footer(text="Action required")

                view = InappropriateView(player_id, name, clan_tag, flagged_value or name, self)
                msg = await channel.send(embed=embed, view=view)
                msg_id = msg.id
                logger.info(f"Alert sent: name='{name}' match='{finding}' score={threshold:.2f} player_id={player_id}")

            except Exception as e:
                logger.error(f"Failed to send channel alert: {e}")
        else:
            logger.warning("No channel_id configured for inappropriate_name — alert not sent to Discord.")

        # Always save to DB (even if channel is missing)
        result = self.select_Inappropriate_Name(player_id)
        if result:
            self.update_Inappropriate_Name(player_id, "inanme_decision", "pending")
            self.update_Inappropriate_Name(player_id, "inanme_name", name)
            if msg_id:
                self.update_Inappropriate_Name(player_id, "inanme_message_id", str(msg_id))
        else:
            self.insert_Inappropriate_Name(player_id, name, clan_tag, finding, threshold, "pending", str(msg_id) if msg_id else "")

    async def check_And_Report(self, player_id: str, name: str, clan_tag: str = None):
        """Checks name and clan tag and reports on a match — with whitelist and dedup protection."""
        if self.is_Whitelisted(player_id):
            logger.debug(f"Whitelisted: name='{name}' player_id={player_id}")
            return

        limit = config.get("rcon", 0, "inappropriate_name", 0, "threshold", default=0.85)
        effective_clan_tag = clan_tag if clan_tag and clan_tag != "Not Found" else None

        checks = [(name, name)]
        if effective_clan_tag:
            checks.append((effective_clan_tag, f"{effective_clan_tag} (clan tag)"))

        for value, label in checks:
            if not value:
                continue

            threshold, finding = self.inappropriate.get_match(value)

            if threshold >= limit:
                if self.already_Open(player_id):
                    logger.debug(f"Skipped (already pending): name='{name}' clan_tag='{effective_clan_tag}' player_id={player_id}")
                else:
                    logger.warning(f"Flagged: label='{label}' match='{finding}' score={threshold:.2f} player_id={player_id}")
                    await self.send_Alert(player_id, name, threshold, finding, clan_tag=effective_clan_tag, flagged_value=label)
                return

            logger.debug(f"OK: label='{label}' score={threshold:.2f} player_id={player_id}")

    # --- Check methods ---

    async def check_Name(self):
        """Checks players who have connected since the last run."""
        try:
            server_status = await rcon.get_Server_Status()
            if not server_status:
                return

            if not self.last_check:
                self.last_check = time.time()

            payload = {
                "end": 250,
                "filter_action": ["CONNECTED"],
                "filter_player": [],
                "inclusive_filter": "true",
            }

            data = await rcon.get_Recent_Logs(payload, model.RecentLogs)
            last_check = time.time()

            players = await rcon.get_In_Game_Players()

            for item in data.logs:
                player_id = utils.get_last_parenthesis_content(item)
                event_time = data.get_Timestamp(player_id)

                if int(event_time / 1000) > int(self.last_check):
                    name = players.get_Ingame_Player_Name(player_id)
                    clan_tag = players.get_Ingame_Player_ClanTag(player_id)
                    await self.check_And_Report(player_id, name, clan_tag=clan_tag)

            self.last_check = last_check

        except discord.HTTPException as e:
            logger.error(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in check_Name: {e}")

    async def check_Players(self, players):
        """Checks a list of player objects (name + player_id)."""
        try:
            for player in players:
                await self.check_And_Report(player.player_id, player.name)
        except Exception as e:
            logger.error(f"Unexpected error in check_Players: {e}")

    async def check_Ingame_Player(self):
        try:
            players = await rcon.get_In_Game_Players()
            player_ids = players.get_Ingame_Player_From_Fraction("both")
            for player_id in player_ids:
                name = players.get_Ingame_Player_Name(player_id)
                clan_tag = players.get_Ingame_Player_ClanTag(player_id)
                await self.check_And_Report(player_id, name, clan_tag=clan_tag)
        except Exception as e:
            logger.error(f"Unexpected error in check_Ingame_Player: {e}")

    async def check_History_Player(self):
        try:
            page = 1
            payload = {"page_size": 100, "page": page}
            players = await rcon.get_Player_History(payload)
            cnt = players.get_Total_Player_Count()
            pages = math.ceil(cnt / 50)

            logger.info(f"Start verify {cnt} player on {pages} pages.")

            for i in range(1, pages):
                payload["page"] = i
                players = await rcon.get_Player_History(payload)
                await self.check_Players(players.get_Players())
                logger.info(f"Checking player on page {i:04} of {pages} pages.")

                if self.shutdown_event.is_set():
                    logger.info("Checking player aborted.")
                    break

            logger.info("End checking.")

        except Exception as e:
            logger.error(f"Unexpected error in check_History_Player: {e}")

    # --- Background Task ---

    async def background_Task(self):
        last_execution = 0

        await self.check_Ingame_Player()
        #await self.check_History_Player()

        while not self.shutdown_event.is_set():
            current_time = time.time()

            if current_time - last_execution >= 60 or last_execution == 0:
                try:
                    await self.check_Name()
                except Exception as e:
                    logger.error(f"Unexpected error in background_Task: {e}")

                last_execution = current_time

            await asyncio.sleep(5)

    async def restore_Views(self):
        """Re-registers all open views. Messages that no longer exist in Discord
        are detected and the corresponding DB entries are automatically deleted."""
        channel = self.bot.get_channel(int(self._channel_id)) if self._channel_id else None
        open_entries = self.select_Open_Inappropriate_Names()
        restored = skipped = cleaned = 0

        for player_id, name, clan_tag, msg_id, decision in open_entries:
            # Check if the Discord message still exists
            if channel:
                try:
                    await channel.fetch_message(int(msg_id))
                except discord.NotFound:
                    self.delete_Inappropriate_Name(player_id)
                    logger.info(f"Restore: Message {msg_id} not found — deleted DB entry for player_id={player_id}.")
                    cleaned += 1
                    continue
                except discord.HTTPException as e:
                    logger.warning(f"Restore: Message {msg_id} could not be verified ({e}) — skipped.")
                    skipped += 1
                    continue

            try:
                action_taken = decision != "pending"
                view = InappropriateView(player_id, name, clan_tag or None, name, self,
                                         action_taken=action_taken)
                self.bot.add_view(view, message_id=int(msg_id))
                restored += 1
            except Exception as e:
                logger.warning(f"Restore: Could not register view for player_id={player_id} msg_id={msg_id}: {e}")
                skipped += 1

        logger.info(f"Restore: {restored} restored, {cleaned} orphaned DB entries deleted, {skipped} skipped.")

        # Reverse check: delete bot messages in the channel that have no DB reference
        if channel:
            known_ids = self.select_All_Inappropriate_Message_Ids()
            orphaned = 0
            async for message in channel.history(limit=None):
                if message.author == self.bot.user and str(message.id) not in known_ids:
                    try:
                        await message.delete()
                        orphaned += 1
                        logger.info(f"Restore: Deleted orphaned Discord message {message.id} with no DB reference.")
                    except discord.HTTPException as e:
                        logger.warning(f"Restore: Could not delete message {message.id}: {e}")
            if orphaned:
                logger.info(f"Restore: {orphaned} orphaned Discord message(s) deleted.")

    async def purge_Channel(self):
        """Deletes ALL messages in the configured channel and clears the DB.
        For testing only — uncomment in on_ready, then comment out again afterwards."""
        channel = self.bot.get_channel(int(self._channel_id)) if self._channel_id else None
        if not channel:
            logger.warning("_purge_Channel: no channel configured.")
            return
        deleted = await channel.purge(limit=None)
        self.cursor.execute("DELETE FROM inappropriate_name")
        self.conn.commit()
        logger.info(f"_purge_Channel: {len(deleted)} messages deleted, DB cleared.")

    @commands.Cog.listener()
    async def on_ready(self):
        # await self._purge_Channel()  # <-- uncomment to purge the channel (for testing only!)
        await self.restore_Views()
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_Task())
            logger.info("Inappropriate background task started")
