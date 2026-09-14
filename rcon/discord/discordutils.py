import discord
import logging
import random
from datetime import datetime
from typing import Awaitable, Callable, List, Optional, Tuple
import rcon.rcon as rcon
from lib.config import config
from lib.utils import is_Integer

logger = logging.getLogger(__name__)


class CommandError(Exception):
    """Raised for expected user-facing error conditions in Discord commands.
    The message is shown directly to the user."""
    pass


async def safe_Send(interaction: discord.Interaction, content: str = None, ephemeral: bool = True, embed: discord.Embed = None, view: discord.ui.View = None):
    # Send message or follow-up if already responded.
    # Only pass view when explicitly set — discord.py treats view=None differently from view=MISSING.
    try:
        kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
        if view is not None:
            kwargs["view"] = view
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
        else:
            await interaction.followup.send(**kwargs)

    except Exception as e:
        logger.error(f"Failed to send interaction message: {e}", exc_info=True)


def is_User_Panel_Dryrun() -> bool:
    """True when user_panel[0].dryrun is set. Every user panel command that would change
    something in-game or in the database must then skip the action and only log what it
    would have done — the Discord answer stays the same so the flow can still be tested."""
    return bool(config.get("rcon", 0, "user_panel", 0, "dryrun", default=False))


PROVIDED_BY = "(Provided by Gryhon)"


def provided_By_Text() -> str:
    """The attribution as shown in the map vote result: "(Provided by Gryhon)" followed by
    the time. Embeds render that time themselves from Embed.timestamp; Components V2
    containers have no such field, so a relative Discord <t:…:R> timestamp is used instead
    — localized by each viewer's own client, like the embed footer's "today at"."""
    return f"{PROVIDED_BY} • <t:{int(datetime.now().timestamp())}:R>"


def add_Provided_By(container: discord.ui.Container) -> None:
    """Adds the shared attribution line to a Components V2 container, so the panels and
    result cards carry the same footer that the embed-based features set via
    Embed.set_footer()."""
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"-# {provided_By_Text()}"))


PROFILE_URL = "https://hllvrecords.com/profiles/{player_id}"


def build_Profile_Link(name: str, player_id: Optional[str]) -> str:
    """Player name as a markdown link to their hllvrecords profile, or the plain name when
    no player id is known. Markdown characters in the name are escaped first — in-game
    names like "**RTB**", "oo__C7__oo" or "Lord [NS1200] + PLAN E" would otherwise swallow
    the formatting or break the link label apart."""
    label = discord.utils.escape_markdown(name).replace("[", "\\[").replace("]", "\\]")
    if not player_id:
        return label
    return f"[{label}]({PROFILE_URL.format(player_id=player_id)})"


def build_Not_Ingame_View(hint: Optional[str] = None) -> discord.ui.LayoutView:
    """Shown when a registered member triggers an ingame command while not connected to
    the server. Shared by every cog so the answer looks the same wherever it comes from;
    hint replaces the closing line for callers that can point at a specific button."""
    container = discord.ui.Container(accent_colour=discord.Color.orange())
    container.add_item(discord.ui.TextDisplay("### 🚫 You're not online in-game"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        "This command only works while you're connected to the server.\n\n"
        + (hint or "Join the game, then try again.")
    ))
    add_Provided_By(container)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def build_Match_Stats_View(
    title: str,
    accent: discord.Color,
    stats: List[Tuple[str, str, str]],
    entries: List[Tuple[str, str, Optional[str]]],
    entry_icon: str,
    empty_entries_text: str,
    subtitle: Optional[str] = None,
    footer: Optional[str] = None,
) -> discord.ui.LayoutView:
    """Builds a per-match stat readout (kills/deaths and similar) as a Components V2
    container instead of an embed stacked with one field per row — keeps a long kill/death
    list readable as a single compact block rather than a wall of near-empty fields.

    stats: (icon, label, value) rows shown as a compact key/value block.
    entries: (name, weapon, player_id) rows shown as a numbered list below the stats, the
    name linked to the player's hllvrecords.com profile when a player_id is available.
    """
    container = discord.ui.Container(accent_colour=accent)
    header = f"### {title}"
    if subtitle:
        header += f"\n{subtitle}"
    container.add_item(discord.ui.TextDisplay(header))
    container.add_item(discord.ui.Separator())

    container.add_item(discord.ui.TextDisplay(
        "\n".join(f"**{icon} {label}:** {value}" for icon, label, value in stats)
    ))

    container.add_item(discord.ui.Separator())
    if entries:
        lines = []
        for i, (name, weapon, player_id) in enumerate(entries, start=1):
            name_display = build_Profile_Link(name, player_id)
            lines.append(f"{entry_icon} **#{i}** — {name_display} _{weapon}_")
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
    else:
        container.add_item(discord.ui.TextDisplay(empty_entries_text))

    if footer:
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# {footer}"))

    add_Provided_By(container)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def get_Faction_Names() -> dict:
    """Maps the internal faction keys ("allies", "axis") to their Discord display labels,
    based on the configured game (rcon.game): "Allies"/"Axis" for HLL, "USA"/"NVA" for HLLV.
    Display-only — RCON/CRCON API calls always use the internal "allies"/"axis" values."""
    if config.get("rcon", 0, "game", default="HLL") == "HLLV":
        return {"allies": "USA", "axis": "NVA"}
    return {"allies": "Allies", "axis": "Axis"}


class VerifyIngameNumber(discord.ui.Modal, title="Verify your identity"):
    """Modal for in-game number verification. Shows a 2-digit number input.

    If on_verified is given, it's called with the modal's own submission interaction on a
    correct code instead of the generic "✅ Verified!" message — e.g. to show the user's
    command menu directly, right where the flow ends, instead of a plain confirmation."""

    def __init__(self, expected_number: int, on_verified: Callable[[discord.Interaction], Awaitable[None]] = None):
        super().__init__()
        self.expected_number = expected_number
        self.result = False
        self._on_verified = on_verified
        self.number = discord.ui.TextInput(
            label="In-game displayed number:",
            placeholder="2-digit number",
            required=True,
            max_length=2
        )
        self.add_item(self.number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if is_Integer(self.number.value) and int(self.number.value) == self.expected_number:
                self.result = True
                if self._on_verified:
                    await self._on_verified(interaction)
                else:
                    await interaction.response.send_message("✅ Verified!", ephemeral=True)
            else:
                self.result = False
                await interaction.response.send_message("❌ Invalid code. Please try again.", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.result = False


async def send_Verification_Code(player_id: str) -> int:
    """Sends a random 2-digit in-game verification code to the given player and returns it,
    so the caller can check it against what the user later enters in VerifyIngameNumber."""
    number = random.randint(10, 99)
    data = {
        "player_id": str(player_id),
        "message": f"Enter this number in Discord\nto verify your account:\n\n{number}"
    }
    logger.info(f"Send verification message to player_id={player_id} with number={number}")
    await rcon.send_Player_Message(data)
    return number


def has_Allowed_Role(member: discord.Member, item: str) -> bool:
    ret = False

    try:
        allowed_names = (config.get("rcon", 0, "user_panel", 0, "commands", 0, f"{item}", 0, "groups") or
                         config.get("rcon", 0, "user_panel", 0, "groups") or [])

        if config.get("rcon", 0, "user_panel", 0, "admin_always") and member.guild_permissions.administrator:
            ret = True
        else:
            ret = any(role.name in allowed_names for role in member.roles)

        return ret

    except Exception as e:
        logger.error(f"Error in has_Allowed_Role: {e}", exc_info=True)
        return False


async def is_Round_Active(bot: discord.Client) -> bool:
    """Checks whether players are currently on the server, as a live proxy for 'a round is
    active'. Deliberately independent of VoteMap's log-derived game_active flag, which can
    get stuck stale if the bot restarts mid-round (no fresh MATCH START log to pick up)."""
    try:
        status = await rcon.get_Server_Status()
        if status is None or status.current_players is None:
            return True
        return int(status.current_players) > 0
    except Exception as e:
        logger.error(f"Unexpected error in is_Round_Active: {e}", exc_info=True)
        return True


async def search_Players_As_Choices(query: str) -> List[Tuple[str, str]]:
    """Searches known in-game players by name fragment. Returns up to 25
    (player_id, label) pairs, most recently seen first."""
    try:
        matches = await rcon.search_Players(query.strip().replace(" ", "%"))
        if not matches:
            return []
        choices = []
        for m in matches:
            player_id, names, _first_seen_ms, last_seen_ms = m[0], m[1], m[2], m[3]
            last_seen = datetime.fromtimestamp(last_seen_ms / 1000).strftime("%Y-%m-%d")
            label = f"{', '.join(names)} — last seen {last_seen}"[:100]
            choices.append((player_id, label))
        return choices
    except Exception as e:
        logger.error(f"Unexpected error in search_Players_As_Choices: {e}", exc_info=True)
        return []


async def search_Online_Players_As_Choices(query: str) -> List[Tuple[str, str]]:
    """Searches players currently connected to the server by name fragment. Returns up
    to 25 (player_id, label) pairs. Used where the player must be online right now,
    e.g. linking a T17 account (the verification code is sent in-game)."""
    try:
        ingame = await rcon.get_In_Game_Players()
        player_ids = ingame.get_Ingame_Player_From_Fraction("both") or []
        needle = query.strip().lower()
        choices = []
        for player_id in player_ids:
            name = ingame.get_Ingame_Player_Name(player_id)
            if name and needle in name.lower():
                choices.append((player_id, name))
        return choices[:25]
    except Exception as e:
        logger.error(f"Unexpected error in search_Online_Players_As_Choices: {e}", exc_info=True)
        return []


class PlayerSearchModal(discord.ui.Modal, title="Search player"):
    """Generic modal to search known in-game players by (partial) name.
    on_search(interaction, query) is called with the submitted interaction and query text."""

    def __init__(self, on_search: Callable[[discord.Interaction, str], Awaitable[None]],
                 title: str = None,
                 label: str = "In-game name (part of it is enough)", placeholder: str = "e.g. John Doe"):
        super().__init__(title=title or "Search player")
        self._on_search = on_search
        self.query = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            required=True,
            min_length=2,
            max_length=32,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._on_search(interaction, self.query.value.strip())


class PlayerResultSelect(discord.ui.Select):
    def __init__(self, choices: List[Tuple[str, str]], on_pick: Callable[[discord.Interaction, str], Awaitable[None]]):
        options = [discord.SelectOption(label=label, value=player_id) for player_id, label in choices[:25]]
        super().__init__(placeholder="Choose a player…", options=options, min_values=1, max_values=1)
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_pick(interaction, self.values[0])


class PlayerResultView(discord.ui.View):
    """Shows search results as a select menu. Used as the second step after PlayerSearchModal."""

    def __init__(self, choices: List[Tuple[str, str]], on_pick: Callable[[discord.Interaction, str], Awaitable[None]], timeout: Optional[float] = 300):
        super().__init__(timeout=timeout)
        self.add_item(PlayerResultSelect(choices, on_pick))