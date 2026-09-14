import discord
import logging
import asyncio
import time
from discord.ext import commands
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from rcon.discord.discordutils import (
    PlayerResultView,
    add_Provided_By,
    PROVIDED_BY,
    build_Not_Ingame_View,
    is_User_Panel_Dryrun,
    PlayerSearchModal,
    VerifyIngameNumber,
    has_Allowed_Role,
    is_Round_Active,
    search_Online_Players_As_Choices,
    search_Players_As_Choices,
    send_Verification_Code,
)
from rcon.discord.unregister import build_Result_View

logger = logging.getLogger(__name__)

ROOT_MESSAGE_SENDER = "user_menu_root"

# key -> label / category / one-line description (shown under the category, admin-panel style)
COMMANDS = {
    "punish_me": {
        "label": "🥊 Redeploy",
        "category": "player",
        "description": "Redeploys you in-game to skip the death cooldown.",
    },
    "switch_me": {
        "label": "🔄 Switch me",
        "category": "player",
        "description": "Switches you to the other team, right now.",
    },
    "who_killed_me": {
        "label": "💀 Who killed me",
        "category": "player",
        "description": "Shows who killed you this match.",
    },
    "whom_i_killed": {
        "label": "⚔️ Whom I killed",
        "category": "player",
        "description": "Shows who you've killed this match.",
    },
    "remove_player_from_squad": {
        "label": "🚪 Remove from squad (SL)",
        "category": "player",
        "description": "Removes a player from your squad (Squad Leaders only).",
    },
    "player_stats": {
        "label": "📊 Player stats",
        "category": "stats",
        "description": "Shows your own live match stats.",
    },
    "vip_status": {
        "label": "🎟️ VIP status",
        "category": "stats",
        "description": "Shows your VIP status and remaining days.",
    },
    "gift_vip": {
        "label": "🎁 Gift VIP",
        "category": "stats",
        "description": "Gifts one VIP day to another player.",
    },
    "unlink_me": {
        "label": "❌ Unlink my account",
        "category": "account",
        "description": "Unlinks your T17 account from Discord.",
    },
}

CATEGORIES = {
    "player": "🎮 Player Actions",
    "stats": "📊 Stats & VIP",
    "account": "👤 Account",
}

ROUND_OVER_MESSAGE = "⏸️ The round has ended. Please reopen the menu in the channel to continue."


class UnlinkConfirmButton(discord.ui.Button):
    def __init__(self, cog: "UserPanel", menu_view: "FullMenuView" = None):
        super().__init__(label="Yes, unlink", style=discord.ButtonStyle.danger)
        self.cog = cog
        self.menu_view = menu_view

    async def callback(self, interaction: discord.Interaction) -> None:
        if is_User_Panel_Dryrun():
            logger.info(f"DryRun - User {interaction.user.name} (ID={interaction.user.id}) unlinked their own account via the menu - registration kept.")
            await interaction.response.edit_message(view=build_Result_View(
                discord.Color.green(), "✅ Account Unlinked",
                "Your in-game account has been unlinked. Link it again any time via **Ingame Command**."
            ))
        elif self.cog.delete_T17_Voter_Registration(interaction.user.id):
            logger.info(f"User {interaction.user.name} (ID={interaction.user.id}) unlinked their own account via the menu.")
            await interaction.response.edit_message(view=build_Result_View(
                discord.Color.green(), "✅ Account Unlinked",
                "Your in-game account has been unlinked. Link it again any time via **Ingame Command**."
            ))
        else:
            await interaction.response.edit_message(view=build_Result_View(
                discord.Color.red(), "❌ Unlink Failed",
                "A database error occurred. Please try again."
            ))

        if self.menu_view is not None:
            await self.menu_view.close()


class UnlinkCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(view=build_Result_View(
            discord.Color.blurple(), "Cancelled", "Your account stays linked."
        ))


class UnlinkConfirmView(discord.ui.LayoutView):
    """Confirmation step shown before unlinking — closes the requester's Ingame Command
    Menu on success, since it would otherwise sit there showing commands for an account
    that's no longer registered."""

    def __init__(self, cog: "UserPanel", menu_view: "FullMenuView" = None):
        super().__init__(timeout=60)
        container = discord.ui.Container(accent_colour=discord.Color.red())
        container.add_item(discord.ui.TextDisplay("### ⚠️ Unlink your account?"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            "This removes the link between your Discord account and your in-game account. "
            "You'll need to link it again via **Ingame Command** to use registered features."
        ))
        container.add_item(discord.ui.ActionRow(UnlinkConfirmButton(cog, menu_view), UnlinkCancelButton()))
        add_Provided_By(container)
        self.add_item(container)


def disable_All_Buttons(item) -> None:
    if isinstance(item, discord.ui.Button):
        item.disabled = True
    accessory = getattr(item, "accessory", None)
    if accessory is not None:
        disable_All_Buttons(accessory)
    for child in getattr(item, "children", None) or []:
        disable_All_Buttons(child)


def refresh_View_Timeout(view) -> None:
    """Resets the view's 10-minute close timer on interaction. Uses discord.py's private
    View._refresh_timeout() — not officially public API, so this fails silently if a future
    discord.py version removes/renames it (the fixed 10-minute timeout still applies either way)."""
    try:
        view._refresh_timeout()
    except Exception:
        pass


class RootOpenButton(discord.ui.Button):
    """Looks the UserPanel cog up at click time via interaction.client, so it keeps
    working across restarts without holding any per-instance state."""

    def __init__(self):
        super().__init__(label="📋 Ingame Command", style=discord.ButtonStyle.primary, custom_id="hll_menu:root:open")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("UserPanel")
        if cog is None:
            await interaction.response.send_message("The Ingame Command Menu is currently unavailable.", ephemeral=True)
            return
        await cog.handle_Root_Click(interaction)


class RootMenuView(discord.ui.LayoutView):
    """Persistent view for the single always-visible root message. Registered once via
    bot.add_view() so it keeps working across restarts as long as the message exists."""

    def __init__(self, server_name: str = None):
        super().__init__(timeout=None)

        stats_url = config.get("rcon", 0, "stats_url", default="")
        name_display = f"[{server_name}]({stats_url})" if server_name and stats_url else server_name

        header_lines = ["# 📋 Ingame Command Menu"]
        if name_display:
            header_lines.append(f"-# {name_display}")

        container = discord.ui.Container(accent_colour=discord.Color.blurple())
        container.add_item(discord.ui.TextDisplay("\n".join(header_lines)))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            "Press **Ingame Command** to see your available commands.\n\n"
            "**Discord account not linked to your T17 (in-game) account yet?** Press **Ingame Command** "
            "too — it opens the link flow directly:\n"
            "1️⃣ Search and pick your in-game name (you must be online)\n"
            "2️⃣ Enter the short code you'll receive in-game to confirm it's you"
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            "-# The menu only stays valid while a round is running — if the round ends, just "
            "press **Ingame Command** again."
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.ActionRow(RootOpenButton()))
        add_Provided_By(container)
        self.add_item(container)


class FullMenuCommandButton(discord.ui.Button):
    def __init__(self, key: str, cog: "UserPanel"):
        super().__init__(label=COMMANDS[key]["label"], style=discord.ButtonStyle.secondary)
        self.key = key
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        refresh_View_Timeout(self.view)
        asyncio.create_task(self.view.bump_Countdown_Display())
        await self.cog.dispatch_Command(interaction, self.key, self.view)


MENU_TIMEOUT_SECONDS = 600


class FullMenuView(discord.ui.LayoutView):
    """Shows every command the member has access to at once, grouped by category with a
    short explanation each — no click-through navigation needed. Closes itself 10 minutes
    after being opened, with a live Discord countdown shown in the message."""

    def __init__(self, cog: "UserPanel", member: discord.Member):
        super().__init__(timeout=MENU_TIMEOUT_SECONDS)
        self.cog = cog
        self.member = member
        self.message: discord.Message = None

        self.container = discord.ui.Container(accent_colour=discord.Color.blurple())
        self.container.add_item(discord.ui.TextDisplay("# 📋 Ingame Command Menu"))

        any_visible = False
        for category_key in CATEGORIES:
            visible = [key for key, meta in COMMANDS.items()
                       if meta["category"] == category_key and cog.is_Command_Visible(key, member)]
            if not visible:
                continue
            any_visible = True

            for key in visible:
                self.container.add_item(discord.ui.Separator())
                self.container.add_item(discord.ui.TextDisplay(f"-# {COMMANDS[key]['description']}"))
                self.container.add_item(discord.ui.ActionRow(FullMenuCommandButton(key, cog)))

        self.container.add_item(discord.ui.Separator())
        if any_visible:
            self.container.add_item(discord.ui.TextDisplay("-# Commands are only available while a round is active."))
        else:
            self.container.add_item(discord.ui.TextDisplay(
                "Sorry, there's nothing here for you right now — no commands are currently "
                "available to your account. If you think that's wrong, reach out to an admin."
            ))

        self.countdown_display = discord.ui.TextDisplay(self.countdown_Text())
        self.container.add_item(self.countdown_display)

        self.add_item(self.container)

    def countdown_Text(self) -> str:
        """Carries the attribution as well — the menu's closing countdown already sits where
        the "(Provided by Gryhon)" line would go, and two grey footer lines under each other
        just push the buttons further up the screen."""
        expiry_ts = int(time.time()) + MENU_TIMEOUT_SECONDS
        return f"-# {PROVIDED_BY} • This menu closes <t:{expiry_ts}:R>."

    async def bump_Countdown_Display(self) -> None:
        """Updates the shown countdown to match the just-refreshed 10-minute timeout.
        Runs as its own message edit (via the stored InteractionMessage), independent of
        whatever response the triggering button uses for its own action."""
        self.countdown_display.content = self.countdown_Text()
        try:
            if self.message is not None:
                await self.message.edit(view=self)
        except Exception as e:
            logger.error(f"FullMenuView: failed to refresh countdown display: {e}", exc_info=True)

    async def on_timeout(self) -> None:
        await self.delete_Message("10-minute timeout")
        self.cog.unregister_Open_Menu(self)

    async def close(self) -> None:
        """Closes the menu early, e.g. right after the member unlinks their account —
        the command list would otherwise sit there stale until the 10-minute timeout."""
        self.stop()
        await self.delete_Message("closed early")
        self.cog.unregister_Open_Menu(self)

    async def delete_Message(self, reason: str) -> None:
        try:
            if self.message is not None:
                await self.message.delete()
                logger.info(f"FullMenuView: deleted menu message {self.message.id} ({reason})")
        except Exception as e:
            logger.error(f"FullMenuView: failed to delete message ({reason}): {e}", exc_info=True)


class UserPanel(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False
        self.server_name = None
        self.open_menus = set()
        self.root_message = None

    def register_Open_Menu(self, view: "FullMenuView") -> None:
        self.open_menus.add(view)

    def unregister_Open_Menu(self, view: "FullMenuView") -> None:
        self.open_menus.discard(view)

    async def close_All_Open_Menus(self) -> None:
        """Deletes every currently-open ephemeral menu message, called right before the
        bot shuts down (while the in-memory view/message association still exists — an
        already-restarted process can no longer reach these). Only works for menus opened
        within the last ~15 minutes (Discord's interaction webhook token validity)."""
        for view in list(self.open_menus):
            try:
                if view.message is not None:
                    await view.message.delete()
                    logger.info(f"UserPanel: deleted open menu message {view.message.id} on shutdown")
            except Exception as e:
                logger.error(f"UserPanel: failed to delete open menu on shutdown: {e}", exc_info=True)
        self.open_menus.clear()

    async def get_Server_Name(self) -> str:
        if not self.server_name:
            try:
                status = await rcon.get_Server_Status()
                if status and status.name:
                    self.server_name = status.name
            except Exception as e:
                logger.error(f"UserPanel: failed to fetch server status: {e}")
        return self.server_name or f"Server {config.get('rcon', 0, 'server_number', default=1)}"

    # --- Visibility -------------------------------------------------------

    def is_Command_Visible(self, key: str, member: discord.Member) -> bool:
        bot = self.bot
        if key == "punish_me":
            return bot.get_cog("PunishMe") is not None and has_Allowed_Role(member, "punish_me")
        if key == "switch_me":
            return bot.get_cog("SwitchMe") is not None and has_Allowed_Role(member, "switch_me")
        if key == "who_killed_me":
            return bot.get_cog("WhoKilledMe") is not None and has_Allowed_Role(member, "who_killed_me")
        if key == "whom_i_killed":
            return bot.get_cog("WhomIKilled") is not None and has_Allowed_Role(member, "whom_i_killed")
        if key == "remove_player_from_squad":
            return bot.get_cog("RemovePlayerFromSquad") is not None and has_Allowed_Role(member, "remove_player_from_squad")
        if key == "player_stats":
            return bot.get_cog("Statistics") is not None
        if key == "vip_status":
            return (
                bot.get_cog("VipManagement") is not None
                and config.get("rcon", 0, "user_panel", 0, "commands", 0, "vip_status", 0, "enabled", default=True)
                and has_Allowed_Role(member, "vip_status")
            )
        if key == "gift_vip":
            return (
                bot.get_cog("VipManagement") is not None
                and config.get("rcon", 0, "user_panel", 0, "commands", 0, "gift_vip", 0, "enabled", default=True)
                and has_Allowed_Role(member, "gift_vip")
            )
        if key == "unlink_me":
            return (
                bot.get_cog("Unregister") is not None
                and config.get("rcon", 0, "user_panel", 0, "commands", 0, "unlink_me", 0, "enabled", default=True)
                and has_Allowed_Role(member, "unlink_me")
            )
        return False

    # --- Root / registration ----------------------------------------------

    async def handle_Root_Click(self, interaction: discord.Interaction) -> None:
        try:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("❌ This only works on the server.", ephemeral=True)
                return

            player_id, *_ = self.select_T17_Voter_Registration(interaction.user.id)

            if not player_id:
                await interaction.response.send_modal(PlayerSearchModal(
                    self.handle_Register_Search,
                    title="🔗 Link your T17 account",
                    label="Type your in-game name to link it",
                    placeholder="e.g. John Doe — you must be online now",
                ))
                return

            ingame = await rcon.get_In_Game_Players()
            if not ingame.is_Player_Ingame(player_id):
                await interaction.response.send_message(
                    view=build_Not_Ingame_View("Join the game, then press **📋 Ingame Command** again."),
                    ephemeral=True,
                )
                return

            await self.send_Full_Menu(interaction)

        except Exception as e:
            logger.error(f"Unexpected error in handle_Root_Click: {e}", exc_info=True)

    async def send_Full_Menu(self, interaction: discord.Interaction) -> None:
        view = FullMenuView(self, interaction.user)
        await interaction.response.send_message(view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except Exception as e:
            logger.error(f"UserPanel: failed to fetch original response for menu timeout: {e}", exc_info=True)
        self.register_Open_Menu(view)

    async def handle_Register_Search(self, interaction: discord.Interaction, query: str) -> None:
        # Ack immediately — the RCON lookup below can take longer than Discord's 3-second
        # response window, which would otherwise invalidate the interaction token (404
        # "Unknown interaction") before we get to send anything back.
        await interaction.response.defer(ephemeral=True, thinking=True)
        choices = await search_Online_Players_As_Choices(query)
        if not choices:
            await interaction.edit_original_response(
                content="No matching online players found. Make sure you're connected to the server and try again.",
            )
            return
        await interaction.edit_original_response(
            content="Choose your name — you'll then get a short random number in-game to confirm it's you:",
            view=PlayerResultView(choices, self.handle_Register_Pick),
        )

    async def handle_Register_Pick(self, interaction: discord.Interaction, player_id: str) -> None:
        try:
            number = await send_Verification_Code(player_id)

            async def on_verified(verify_interaction: discord.Interaction) -> None:
                nick = verify_interaction.guild.get_member(verify_interaction.user.id).nick if verify_interaction.guild else None
                self.insert_Voter_Registration(
                    verify_interaction.user.name, verify_interaction.user.id, nick, player_id, 0, 0
                )
                logger.info(f"User {verify_interaction.user.name} (ID={verify_interaction.user.id}) linked T17 ID {player_id}")
                await self.send_Full_Menu(verify_interaction)

            modal = VerifyIngameNumber(number, on_verified=on_verified)
            await interaction.response.send_modal(modal)
            await modal.wait()
            # Best effort: Discord may not allow deleting a message whose response type was a
            # modal — if so this silently no-ops and the "Choose your name" message just stays.
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Unexpected error in handle_Register_Pick: {e}", exc_info=True)

    # --- Command dispatch ---------------------------------------------------

    async def dispatch_Command(self, interaction: discord.Interaction, key: str, view: "FullMenuView" = None) -> None:
        if not await is_Round_Active(self.bot):
            if view is not None:
                disable_All_Buttons(view)
                view.container.add_item(discord.ui.Separator())
                view.container.add_item(discord.ui.TextDisplay(ROUND_OVER_MESSAGE))
                view.stop()
                await interaction.response.edit_message(view=view)
                self.unregister_Open_Menu(view)
            else:
                await interaction.response.send_message(ROUND_OVER_MESSAGE, ephemeral=True)
            return

        try:
            if key == "punish_me":
                await self.bot.get_cog("PunishMe").punish_me(interaction)
            elif key == "switch_me":
                await self.bot.get_cog("SwitchMe").switch_me(interaction)
            elif key == "who_killed_me":
                await self.bot.get_cog("WhoKilledMe").who_killed_me(interaction)
            elif key == "whom_i_killed":
                await self.bot.get_cog("WhomIKilled").whom_i_killed(interaction)
            elif key == "remove_player_from_squad":
                await self.bot.get_cog("RemovePlayerFromSquad").remove_player_from_squad(interaction)
            elif key == "unlink_me":
                await interaction.response.send_message(view=UnlinkConfirmView(self, view), ephemeral=True)
            elif key == "vip_status":
                await self.bot.get_cog("VipManagement").vip_status(interaction)
            elif key == "player_stats":
                await self.bot.get_cog("Statistics").player_stats(interaction)
            elif key == "gift_vip":
                await self.start_Player_Search(interaction)
        except Exception as e:
            logger.error(f"Unexpected error dispatching command {key}: {e}", exc_info=True)

    async def start_Player_Search(self, interaction: discord.Interaction) -> None:
        """Opens the search-and-pick flow for gifting VIP to another player."""
        async def on_search(modal_interaction: discord.Interaction, query: str):
            choices = await search_Players_As_Choices(query)
            if not choices:
                await modal_interaction.response.send_message(
                    "No matching players found. Try a different name.", ephemeral=True
                )
                return

            async def on_pick(select_interaction: discord.Interaction, player_id: str):
                await self.bot.get_cog("VipManagement").gift_vip(select_interaction, player_id)

            await modal_interaction.response.send_message(
                "Choose the player:", view=PlayerResultView(choices, on_pick), ephemeral=True
            )

        await interaction.response.send_modal(PlayerSearchModal(
            on_search, title="🎁 Gift VIP", label="Type the recipient's in-game name"
        ))

    # --- Persistent root message --------------------------------------------

    async def ensure_Root_Message(self) -> None:
        channel_id = config.get("rcon", 0, "user_panel", 0, "channel_id", default=0)
        if not channel_id:
            logger.warning("UserPanel: user_panel.channel_id not configured, skipping root message.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            logger.error(f"UserPanel: channel {channel_id} not found.")
            return

        existing_id = self.select_Message_Id(ROOT_MESSAGE_SENDER)
        async for msg in channel.history(limit=100):
            if msg.author.id == self.bot.user.id:
                try:
                    await msg.delete()
                    logger.info(f"UserPanel: deleted old message {msg.id}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"UserPanel: failed to delete old message {msg.id}: {e}")

        server_name = await self.get_Server_Name()
        msg = await channel.send(view=RootMenuView(server_name=server_name))
        self.root_message = msg
        if existing_id:
            self.update_Message_Id(ROOT_MESSAGE_SENDER, msg.id)
        else:
            self.insert_Message_Id(ROOT_MESSAGE_SENDER, msg.id)

    async def close_Root_Message(self) -> None:
        """Deletes the persistent root menu message on shutdown, so nothing with dead
        buttons is left behind while the bot is offline."""
        if self.root_message is None:
            return
        try:
            await self.root_message.delete()
            logger.info(f"UserPanel: deleted root message {self.root_message.id} on shutdown")
        except Exception as e:
            logger.error(f"UserPanel: failed to delete root message on shutdown: {e}", exc_info=True)
        self.root_message = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.add_view(RootMenuView())
            await self.ensure_Root_Message()
            logger.info("UserPanel ready")
