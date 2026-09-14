from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

import discord
from discord.ext import commands

import rcon.model as model
import rcon.rcon as rcon
from lib.config import config
from rcon.discord.discordbase import DiscordBase
from rcon.discord.discordutils import has_Allowed_Role, safe_Send, build_Not_Ingame_View, is_User_Panel_Dryrun, build_Profile_Link, add_Provided_By, PROVIDED_BY

logger = logging.getLogger(__name__)

FRACTION_LABELS = {
    "axis": "Axis",
    "allies": "Allies",
}

LEADER_ROLES = {
    "squadleader": "Squad Leader",
    "officer": "Officer",
    "tankcommander": "Tank Commander",
    "spotter": "Spotter",
    "helicopterlogisticsofficer": "Helicopter Logistics Officer",
    "mortarobserver": "Mortar Observer",
}


def build_Not_Leader_View(name: str) -> discord.ui.LayoutView:
    """Shown instead of the squad checklist when the requester holds a role that isn't
    allowed to remove players from a squad."""
    allowed = "\n".join(f"- {label}" for label in LEADER_ROLES.values())
    container = discord.ui.Container(accent_colour=discord.Color.red())
    container.add_item(discord.ui.TextDisplay(f"### 🚫 Not a Squad Leader"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(
        f"**{name}**, you don't hold a role that's allowed to remove players from a squad.\n\n"
        f"-# Allowed roles:\n{allowed}"
    ))
    add_Provided_By(container)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def build_No_Squad_Members_View(name: str, squad: Optional[str], fraction: Optional[str]) -> discord.ui.LayoutView:
    """Shown instead of the squad checklist when the requester is the only one in their
    squad — nothing to pick from, so this is an information card, not an error."""
    squad_label = str(squad or "").upper()
    fraction_label = FRACTION_LABELS.get(str(fraction or "").lower())

    container = discord.ui.Container(accent_colour=discord.Color.blurple())
    container.add_item(discord.ui.TextDisplay("### 👤 Nobody to remove"))
    container.add_item(discord.ui.Separator())

    if squad_label:
        body = f"**{name}**, you are the only player in squad **{squad_label}** right now."
    else:
        body = f"**{name}**, you are currently not in a squad."
    container.add_item(discord.ui.TextDisplay(body))

    footer = "-# The list only offers your squad mates — you can't remove yourself."
    if squad_label and fraction_label:
        footer = f"-# {fraction_label} · Squad {squad_label}\n{footer}"
    container.add_item(discord.ui.TextDisplay(footer))

    add_Provided_By(container)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


@dataclass
class ChecklistItem:
    id: str
    name: str
    role: str
    level: str
    checked: bool = False

class DigitButton(discord.ui.Button["NumberedChecklistView"]):
    def __init__(self, idx: int, item: ChecklistItem, instance_id: str):
        super().__init__(
            label=str(idx),
            style=discord.ButtonStyle.success if item.checked else discord.ButtonStyle.secondary,
            custom_id=f"rm:num:{instance_id}:{idx}:{item.id}",
            row=0,
        )
        self.zero_based_index = idx - 1

    async def callback(self, interaction: discord.Interaction) -> None:  
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)
        view: NumberedChecklistView = self.view 
        await view.toggle_by_index(self.zero_based_index, interaction)

class SelectAllToggle(discord.ui.Button["NumberedChecklistView"]):
    """Ticks every player at once — and unticks them again on a second press, so the
    button can't strand the list in a state the member didn't intend."""

    SELECT_LABEL = "Select all"
    CLEAR_LABEL = "Clear all"

    def __init__(self, instance_id: str):
        super().__init__(label=self.SELECT_LABEL, style=discord.ButtonStyle.primary,
                         custom_id=f"rm:num:{instance_id}:all", row=1)

    def refresh(self, all_selected: bool) -> None:
        self.label = self.CLEAR_LABEL if all_selected else self.SELECT_LABEL

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)
        view: NumberedChecklistView = self.view
        await view.toggle_All(interaction)


class ConfirmRemove(discord.ui.Button["NumberedChecklistView"]):
    def __init__(self, instance_id: str):
        super().__init__(label="Confirm Remove", style=discord.ButtonStyle.danger,
                         custom_id=f"rm:num:{instance_id}:confirm", row=1)

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        """Removes the ticked players straight away — there is no second confirmation — and
        closes the dialog. Only a failure is reported back, a successful removal is visible
        in-game and stays in the log."""
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)

        view: NumberedChecklistView = self.view
        selected_items = view.get_selected_items()

        for c in view.children:
            c.disabled = True

        await view.close()

        if not selected_items:
            try:
                await interaction.followup.send("❌ No players selected. Nothing was removed.", ephemeral=True)
            except Exception:
                pass
            return

        try:
            await view.owner.remove_selected_players(interaction, selected_items)
        except Exception as ex:
            logger.exception("remove_selected_players failed: %s", ex)
            try:
                await interaction.followup.send(f"⚠️ Error while removing: {ex}", ephemeral=True)
            except Exception:
                pass


class NumberedChecklistView(discord.ui.View):
    def __init__(
        self,
        owner_cog: "RemovePlayerFromSquad",
        title: str,
        items: List[ChecklistItem],
        *,
        with_confirm: bool = True,
        timeout: Optional[float] = 840.0,
    ):
        super().__init__(timeout=timeout)
        if not items:
            raise ValueError("Need at least one item.")
        if len(items) > 5:
            raise ValueError("This numbered view supports at most 5 items (one button row).")

        self.owner = owner_cog
        self.title = title
        self.items = items
        self.message: Optional[discord.Message] = None
        self.orig_inter: Optional[discord.Interaction] = None
        self.requester_id: Optional[int] = None
        # Unique per dialog: the buttons of two dialogs listing the same squad would
        # otherwise carry identical custom_ids and become indistinguishable for
        # discord.py's component dispatch.
        self.instance_id = uuid.uuid4().hex[:8]

        for idx, it in enumerate(self.items, start=1):
            self.add_item(DigitButton(idx, it, self.instance_id))

        self.select_all_button: Optional[SelectAllToggle] = None
        if len(self.items) > 1:
            self.select_all_button = SelectAllToggle(self.instance_id)
            self.add_item(self.select_all_button)

        if with_confirm:
            self.add_item(ConfirmRemove(self.instance_id))

    def set_context(self, orig_inter: discord.Interaction, msg: discord.Message, requester_id: int) -> None:
        self.orig_inter = orig_inter
        self.message = msg
        self.requester_id = requester_id

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        try:
            if self.orig_inter is not None:
                await self.orig_inter.edit_original_response(view=self)
            elif self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

        try:
            if self.message:
                self.owner.forget_View(self.message.id)
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.requester_id is None:
            return True
        return interaction.user and interaction.user.id == self.requester_id

    def get_selected_items(self) -> List[ChecklistItem]:
        return [it for it in self.items if it.checked]

    def build_embed(self) -> discord.Embed:
        e = discord.Embed(title=self.title)
        lines = []
        for i, it in enumerate(self.items, start=1):
            mark = "✅" if it.checked else "⬜"
            lines.append(f"{i}. {mark}  **{build_Profile_Link(it.name, it.id)}** (Level {it.level} - _{it.role}_)")
        e.description = "\n".join(lines)
        e.set_footer(text=PROVIDED_BY)
        e.timestamp = datetime.now()
        return e

    def refresh_Buttons(self) -> None:
        """Brings every button in line with the current selection — the digit colours and
        the label of the select-all toggle."""
        for child in self.children:
            if isinstance(child, DigitButton):
                item = self.items[child.zero_based_index]
                child.style = (
                    discord.ButtonStyle.success if item.checked else discord.ButtonStyle.secondary
                )

        if self.select_all_button is not None:
            self.select_all_button.refresh(all(it.checked for it in self.items))

    async def toggle_by_index(self, i0: int, interaction: discord.Interaction) -> None:
        if 0 <= i0 < len(self.items):
            self.items[i0].checked = not self.items[i0].checked

        await self.repaint(interaction)

    async def toggle_All(self, interaction: discord.Interaction) -> None:
        """Selects every player, or clears the selection when everything is already ticked."""
        select_all = not all(it.checked for it in self.items)
        for item in self.items:
            item.checked = select_all

        logger.info(
            "%s %s all %d squad mates in the remove dialog.",
            interaction.user, "selected" if select_all else "cleared", len(self.items),
        )
        await self.repaint(interaction)

    async def repaint(self, interaction: discord.Interaction) -> None:
        self.refresh_Buttons()
        embed = self.build_embed()
        try:
            if interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
        except Exception:
            # Fallback: versuche Response-Edit, falls nicht ge-ack't (sollte selten passieren)
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                pass

    async def close(self) -> None:
        """Takes the dialog off the screen. The checklist is the original response of the
        slash command, so deleting that response makes the whole ephemeral message
        disappear instead of leaving a dead list behind."""
        self.stop()

        try:
            if self.orig_inter is not None:
                await self.orig_inter.delete_original_response()
            elif self.message is not None:
                await self.message.delete()
        except Exception:
            # Falls Discord das Loeschen verweigert: wenigstens die Buttons entfernen.
            try:
                if self.orig_inter is not None:
                    await self.orig_inter.edit_original_response(view=None)
            except Exception:
                pass

        try:
            if self.message:
                self.owner.forget_View(self.message.id)
        except Exception:
            pass


class RemovePlayerFromSquad(commands.Cog, DiscordBase):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False
        self._active_views: dict[int, discord.ui.View] = {}

    def remember_View(self, view: discord.ui.View, msg: discord.Message) -> None:
        self._active_views[msg.id] = view
        try:
            setattr(view, "message", msg)
        except Exception:
            pass

    def forget_View(self, message_id: int) -> None:
        self._active_views.pop(message_id, None)

    def cancel_Previous_Views(self, requester_id: int) -> None:
        """Stops the dialogs this member still has open before a new one is shown. An old
        checklist otherwise stays clickable for its whole timeout and would act on whatever
        was ticked back then, which looks like removing a player that was never selected."""
        for message_id, view in list(self._active_views.items()):
            if getattr(view, "requester_id", None) != requester_id:
                continue

            view.stop()
            self._active_views.pop(message_id, None)
            logger.info("Closed an older remove dialog of %s before opening a new one.", requester_id)

    async def background_task(self) -> None:
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)

    async def remove_player_from_squad(self, interaction: discord.Interaction) -> None:
        did_defer = False
        error_message: Optional[str] = None
        error_view: Optional[discord.ui.LayoutView] = None
        final_embed: Optional[discord.Embed] = None
        final_view: Optional[NumberedChecklistView] = None

        try:
            if not isinstance(interaction.user, discord.Member):
                error_message = "❌ This command only works on the server."
                logger.info("%s used command outside the server.", interaction.user)

            if error_message is None and not has_Allowed_Role(interaction.user, "remove_player_from_squad"):
                error_message = "❌ You do not have permission for this command."
                logger.info("%s lacks permission 'remove_player_from_squad'.", interaction.user)

            if error_message is None:
                await interaction.response.defer(thinking=True, ephemeral=True)
                did_defer = True

                player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)
                if not player_id:
                    error_message = "❌ You are not registered. Please register first."
                    logger.info("%s not registered.", interaction.user)

            ingame = None
            ingame_name = None
            squad = None
            fraction = None

            if error_message is None:
                try:
                    ingame = await rcon.get_In_Game_Players()
                except Exception as ex:
                    error_message = f"⚠️ RCON-Error: {ex}"

            if error_message is None and ingame:
                if not ingame.is_Player_Ingame(player_id):
                    error_message = "❌ You are not ingame. Please join a server first."
                    error_view = build_Not_Ingame_View()
                    logger.info("%s is not ingame.", interaction.user)
                else:
                    ingame_name = ingame.get_Ingame_Player_Name(player_id)
                    role = ingame.get_Role(player_id)
                    if role not in LEADER_ROLES:
                        error_message = f"❌ {ingame_name}, you are not a Squad Leader. Only Squad Leaders can use this command."
                        error_view = build_Not_Leader_View(ingame_name)
                        logger.warning("Player %s is not a Squad Leader", ingame_name)

            items: List[ChecklistItem] = []
            if error_message is None and ingame:
                fraction, squad = ingame.get_Squad_Name(player_id)
                member_ids: Sequence[str] = ingame.get_Squad_Members(fraction, squad) or []

                filtered_ids = [pid for pid in member_ids if str(pid) != str(player_id)]
                for pid in filtered_ids[:5]:
                    pname = ingame.get_Ingame_Player_Name(pid) or "Unknown"
                    prole = ingame.get_Role(pid) or "Unknown"
                    plevel = ingame.get_Ingame_Player_Level(pid) or "Unknown"
                    items.append(ChecklistItem(id=str(pid), name=pname, role=prole, level=plevel, checked=False))

                if not items:
                    error_message = f"ℹ️ No other members in your squad {str(squad or '').upper()}"
                    error_view = build_No_Squad_Members_View(ingame_name, squad, fraction)
                    logger.info("%s is alone in squad %s", ingame_name, squad)

            if error_message is None:
                title = f"Choose the player you want to remove from {str(squad or '').upper()}:"
                final_view = NumberedChecklistView(self, title, items, with_confirm=True)
                final_embed = final_view.build_embed()

        except Exception as e:
            logger.exception("Unexpected error in remove_player_from_squad: %s", e)
            error_message = f"⚠️ Unexpected error: {e}"

        try:
            if error_message is None and did_defer and final_view and final_embed:
                self.cancel_Previous_Views(interaction.user.id)
                msg = await interaction.edit_original_response(embed=final_embed, view=final_view)
                final_view.set_context(orig_inter=interaction, msg=msg, requester_id=interaction.user.id)
                self.remember_View(final_view, msg)
            elif error_view is not None:
                if not did_defer:
                    await safe_Send(interaction, view=error_view)
                else:
                    await interaction.edit_original_response(content=None, embed=None, view=error_view)
            else:
                if not did_defer:
                    await safe_Send(interaction, error_message or "⚠️ Nothing to show.")
                else:
                    await interaction.edit_original_response(content=error_message or "⚠️ Nothing to show.", embed=None, view=None)
        except Exception:
            logger.exception("Failed to send response in remove_player_from_squad.")

    async def remove_selected_players(self, interaction: discord.Interaction, items: List[ChecklistItem]) -> None:
        """Removes the given players. A successful removal stays silent — the dialog is
        already gone at this point and the result is visible in-game — only players that
        could not be removed are reported back, so a failure can't pass unnoticed."""
        failures: List[tuple[ChecklistItem, str]] = []

        try:
            seen: set[str] = set()
            unique: List[ChecklistItem] = []
            for it in items:
                if isinstance(it, ChecklistItem) and it.id not in seen:
                    unique.append(it)
                    seen.add(it.id)

            for it in unique:
                try:
                    data = {"player_id": str(it.id), "reason": "The squad leader doesn’t want you in the squad anymore."}

                    if not is_User_Panel_Dryrun():
                        await rcon.remove_from_squad(data)
                        logger.info(f"Removed player: {it.name} ({it.id}) from squad, requested by {interaction.user}.")
                    else:
                        logger.info(f"DryRun - Removed player: {it.name} ({it.id}) from squad, requested by {interaction.user} - not removed.")

                except Exception as ex:
                    logger.error(f"Failed to remove player {it.name} ({it.id}) from squad: {ex}")
                    failures.append((it, str(ex)))

        except Exception as e:
            logger.error("Failed to remove selected players: %s", e)
            try:
                await interaction.followup.send(f"⚠️ Error while removing: {e}", ephemeral=True)
            except Exception:
                pass
            return

        if failures:
            text = "⚠️ Could not remove: " + ", ".join(f"{x.name} – {reason}" for x, reason in failures)
            try:
                await interaction.followup.send(text, ephemeral=True)
            except Exception:
                pass
