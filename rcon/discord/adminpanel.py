import discord
import logging
import asyncio
from discord.ext import commands
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from rcon.discord.discordutils import get_Faction_Names, PlayerSearchModal, PlayerResultView, add_Provided_By

logger = logging.getLogger(__name__)

ROOT_MESSAGE_SENDER = "admin_panel_root"


class ActionButton(discord.ui.Button):
    """Persistent button that dispatches a fixed action to a named cog method.
    Looks the cog up at click time via interaction.client, so it survives restarts
    without holding any per-instance state."""

    def __init__(self, *, label: str, style: discord.ButtonStyle, custom_id: str,
                 cog_name: str, method_name: str, args: tuple = (), disabled: bool = False):
        super().__init__(label=label, style=style, custom_id=custom_id, disabled=disabled)
        self.cog_name = cog_name
        self.method_name = method_name
        self.args = args

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog(self.cog_name)
        if cog is None:
            await interaction.response.send_message(f"{self.cog_name} is not enabled.", ephemeral=True)
            return
        method = getattr(cog, self.method_name)
        await method(interaction, *self.args)


class BroadcastFractionSelect(discord.ui.Select):
    def __init__(self, broadcast_cog):
        options = [discord.SelectOption(label=c.name, value=c.value) for c in broadcast_cog.FRACTIONS]
        super().__init__(placeholder="Target audience…", options=options, min_values=1, max_values=1)
        self.broadcast_cog = broadcast_cog

    async def callback(self, interaction: discord.Interaction):
        fraction_value = self.values[0]
        view = discord.ui.View(timeout=180)
        view.add_item(BroadcastActionSelect(self.broadcast_cog, fraction_value))
        await interaction.response.edit_message(content="Choose a message to broadcast:", view=view)


class BroadcastActionSelect(discord.ui.Select):
    def __init__(self, broadcast_cog, fraction_value: str):
        options = [discord.SelectOption(label=c.name, value=c.value) for c in broadcast_cog.ACTIONS]
        super().__init__(placeholder="Message…", options=options, min_values=1, max_values=1)
        self.broadcast_cog = broadcast_cog
        self.fraction_value = fraction_value

    async def callback(self, interaction: discord.Interaction):
        action_value = self.values[0]
        if action_value == "text":
            await interaction.response.send_modal(
                BroadcastFreeTextModal(self.broadcast_cog, self.fraction_value)
            )
        else:
            await self.broadcast_cog.broadcast_message(interaction, self.fraction_value, action_value)


class BroadcastFreeTextModal(discord.ui.Modal, title="Broadcast message"):
    def __init__(self, broadcast_cog, fraction_value: str):
        super().__init__()
        self.broadcast_cog = broadcast_cog
        self.fraction_value = fraction_value
        self.free_text = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, required=True, max_length=200)
        self.add_item(self.free_text)

    async def on_submit(self, interaction: discord.Interaction):
        await self.broadcast_cog.broadcast_message(interaction, self.fraction_value, "text", self.free_text.value)


async def handle_Unlink_Search(interaction: discord.Interaction, query: str) -> None:
    """Looks up registered accounts (by Discord nick/username or T17 id) instead of
    listing every server member — a plain user picker gets unusable once the server has
    more than a couple dozen members."""
    cog = interaction.client.get_cog("AdminPanel")
    if cog is None:
        await interaction.response.send_message("Admin panel is not enabled.", ephemeral=True)
        return

    rows = cog.search_Voter_Registrations(query)
    if not rows:
        await interaction.response.send_message(
            "No registered accounts match that search. Try a different name or T17 id.", ephemeral=True
        )
        return

    choices = []
    for discord_user_id, nick, username, t17_id, clan_tag in rows:
        name = nick or username or str(discord_user_id)
        tag = f"[{clan_tag}] " if clan_tag else ""
        choices.append((str(discord_user_id), f"{tag}{name} — T17 {t17_id}"[:100]))

    await interaction.response.send_message(
        "Choose the account to unlink:", view=PlayerResultView(choices, handle_Unlink_Pick), ephemeral=True
    )


async def handle_Unlink_Pick(interaction: discord.Interaction, discord_user_id: str) -> None:
    cog = interaction.client.get_cog("Unregister")
    if cog is None:
        await interaction.response.send_message("Unregister is not enabled.", ephemeral=True)
        return
    await cog.unregister_user_by_id(interaction, int(discord_user_id))


class AdminPanelView(discord.ui.LayoutView):
    """Persistent admin panel, built with Components V2 (Container/TextDisplay/Separator)
    so each button group gets its own heading text instead of being a flat button wall.
    Sections are only added for features that are currently enabled/loaded. Access control
    relies entirely on the channel's Discord permissions — no role check is performed here."""

    def __init__(self, bot: commands.Bot, server_name: str = None):
        super().__init__(timeout=None)
        self.section_count = 0

        api_url = config.get("rcon", 0, "api_url", default="")
        name_display = f"[{server_name}]({api_url})" if server_name and api_url else server_name
        header_lines = ["# 🛠️ Admin Panel"]
        if name_display:
            header_lines.append(f"-# {name_display}")
        header_lines.append("Server controls — visible only to those with access to this channel.")

        container = discord.ui.Container(accent_colour=discord.Color.dark_gold())
        container.add_item(discord.ui.TextDisplay("\n".join(header_lines)))

        votemap_cog = bot.get_cog("VoteMap")
        if votemap_cog is not None:
            active = bool(getattr(votemap_cog, "vote_map_active", False))
            self.add_Section(
                container,
                "### 🗺️ Map Vote\n"
                "-# Automatically posts a vote for the next map before each round ends. "
                "**Pause** stops new votes from being started (admin override); **Resume** turns it back on; "
                "**Status** shows whether it's currently running.",
                discord.ui.ActionRow(
                    ActionButton(label="▶️ Resume", style=discord.ButtonStyle.success,
                                 custom_id="hll_admin:mapvote:resume", cog_name="VoteMap",
                                 method_name="mapvote_command", args=("resume",), disabled=active),
                    ActionButton(label="⏸️ Pause", style=discord.ButtonStyle.danger,
                                 custom_id="hll_admin:mapvote:pause", cog_name="VoteMap",
                                 method_name="mapvote_command", args=("pause",), disabled=not active),
                    ActionButton(label="ℹ️ Status", style=discord.ButtonStyle.secondary,
                                 custom_id="hll_admin:mapvote:status", cog_name="VoteMap",
                                 method_name="mapvote_command", args=("status",)),
                ),
            )

        autolevel_cog = bot.get_cog("AutoLevel")
        if autolevel_cog is not None:
            active = bool(getattr(autolevel_cog, "lvl_cap_active", False))
            self.add_Section(
                container,
                "### 📈 Level Cap\n"
                "-# Kicks low-level players once the server has enough players online, so newcomers "
                "aren't kicked while the server is still seeding. **Pause**/**Resume** toggle the check; "
                "**Status** shows whether it's currently running.",
                discord.ui.ActionRow(
                    ActionButton(label="▶️ Resume", style=discord.ButtonStyle.success,
                                 custom_id="hll_admin:levelcap:resume", cog_name="AutoLevel",
                                 method_name="level_cap_command", args=("resume",), disabled=active),
                    ActionButton(label="⏸️ Pause", style=discord.ButtonStyle.danger,
                                 custom_id="hll_admin:levelcap:pause", cog_name="AutoLevel",
                                 method_name="level_cap_command", args=("pause",), disabled=not active),
                    ActionButton(label="ℹ️ Status", style=discord.ButtonStyle.secondary,
                                 custom_id="hll_admin:levelcap:status", cog_name="AutoLevel",
                                 method_name="level_cap_command", args=("status",)),
                ),
            )

        if bot.get_cog("BroadcastMessage") is not None:
            names = get_Faction_Names()
            self.add_Section(
                container,
                "### 📢 Broadcast\n"
                f"-# Sends an announcement to players currently in-game "
                f"({names['axis']}, {names['allies']}, or both).",
                discord.ui.ActionRow(BroadcastEntryButton()),
            )

        if bot.get_cog("Unregister") is not None and config.get(
            "rcon", 0, "admin_panel", 0, "unlink_user", 0, "enabled", default=False
        ):
            self.add_Section(
                container,
                "### 🔓 Registration\n"
                "-# Unlinks a Discord user's saved in-game account — e.g. if it was linked to the "
                "wrong player or the user asked to be removed.",
                discord.ui.ActionRow(UnlinkUserEntryButton()),
            )

        add_Provided_By(container)
        self.add_item(container)

    def add_Section(self, container: discord.ui.Container, heading: str, row: discord.ui.ActionRow) -> None:
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(heading))
        container.add_item(row)
        self.section_count += 1


class BroadcastEntryButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📢 Broadcast Message", style=discord.ButtonStyle.primary, custom_id="hll_admin:broadcast:open")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("BroadcastMessage")
        if cog is None:
            await interaction.response.send_message("Broadcast message is not enabled.", ephemeral=True)
            return
        view = discord.ui.View(timeout=180)
        view.add_item(BroadcastFractionSelect(cog))
        await interaction.response.send_message("Choose the target audience:", view=view, ephemeral=True)


class UnlinkUserEntryButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔓 Unlink User", style=discord.ButtonStyle.secondary, custom_id="hll_admin:unlink_user:open")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PlayerSearchModal(
            handle_Unlink_Search,
            title="🔓 Unlink User",
            label="Discord name, nickname, or T17 id",
            placeholder="e.g. John Doe — at least 2 characters",
        ))


class AdminPanel(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False
        self.root_message = None
        self.server_name = None

    async def get_Server_Name(self) -> str:
        if not self.server_name:
            try:
                status = await rcon.get_Server_Status()
                if status and status.name:
                    self.server_name = status.name
            except Exception as e:
                logger.error(f"AdminPanel: failed to fetch server status: {e}")
        return self.server_name or f"Server {config.get('rcon', 0, 'server_number', default=1)}"

    def current_State(self) -> tuple:
        votemap_cog = self.bot.get_cog("VoteMap")
        autolevel_cog = self.bot.get_cog("AutoLevel")
        return (
            getattr(votemap_cog, "vote_map_active", None) if votemap_cog is not None else None,
            getattr(autolevel_cog, "lvl_cap_active", None) if autolevel_cog is not None else None,
        )

    async def refresh_Loop(self) -> None:
        """Checks the Map Vote / Level Cap status every 5s (independent of any user
        action) and keeps the panel buttons (resume vs. pause) in sync with it."""
        last_state = self.current_State()
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)
            try:
                if self.root_message is None:
                    continue
                state = self.current_State()
                if state == last_state:
                    continue
                last_state = state
                server_name = await self.get_Server_Name()
                await self.root_message.edit(view=AdminPanelView(self.bot, server_name=server_name))
            except discord.NotFound:
                self.root_message = None
            except Exception as e:
                logger.error(f"AdminPanel: failed to refresh panel state: {e}")

    async def ensure_Root_Message(self) -> None:
        channel_id = config.get("rcon", 0, "admin_panel", 0, "channel_id", default=0)
        if not channel_id:
            logger.warning("AdminPanel: channel_id not configured, skipping root message.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            logger.error(f"AdminPanel: channel {channel_id} not found.")
            return

        server_name = await self.get_Server_Name()
        view = AdminPanelView(self.bot, server_name=server_name)
        if view.section_count == 0:
            logger.warning("AdminPanel: no admin features enabled, skipping root message.")
            return

        existing_id = self.select_Message_Id(ROOT_MESSAGE_SENDER)
        async for msg in channel.history(limit=100):
            if msg.author.id == self.bot.user.id:
                try:
                    await msg.delete()
                    logger.info(f"AdminPanel: deleted old message {msg.id}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"AdminPanel: failed to delete old message {msg.id}: {e}")

        msg = await channel.send(view=view)
        self.root_message = msg
        if existing_id:
            self.update_Message_Id(ROOT_MESSAGE_SENDER, msg.id)
        else:
            self.insert_Message_Id(ROOT_MESSAGE_SENDER, msg.id)

    async def close_Root_Message(self) -> None:
        """Deletes the persistent admin panel message on shutdown, so nothing with dead
        buttons is left behind while the bot is offline."""
        if self.root_message is None:
            return
        try:
            await self.root_message.delete()
            logger.info(f"AdminPanel: deleted root message {self.root_message.id} on shutdown")
        except Exception as e:
            logger.error(f"AdminPanel: failed to delete root message on shutdown: {e}", exc_info=True)
        self.root_message = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.add_view(AdminPanelView(self.bot))
            await self.ensure_Root_Message()
            self.bot.loop.create_task(self.refresh_Loop())
            logger.info("AdminPanel ready")
