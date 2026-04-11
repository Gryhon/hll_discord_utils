from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

import discord
from discord import app_commands
from discord.ext import commands

import rcon.model as model
import rcon.rcon as rcon
from lib.config import config
from rcon.discord.discordbase import DiscordBase
from rcon.discord.discordutils import has_Allowed_Role, safe_Send

logger = logging.getLogger(__name__)

@dataclass
class ChecklistItem:
    id: str
    name: str
    role: str
    level: str
    checked: bool = False

class FinalConfirmView(discord.ui.View):
    def __init__(
        self,
        parent_view: "NumberedChecklistView",
        orig_interaction: discord.Interaction,
        timeout: Optional[float] = 180.0, 
    ):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.orig_inter = orig_interaction 
        self.message: Optional[discord.Message] = None  

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        try:
            if self.message:
                await self.message.edit(content="(Dialog abgelaufen)", view=self, embed=None)
        except Exception:
            pass

        try:
            self.parent_view.owner._forget_transient(self)  
        except Exception:
            pass

    @discord.ui.button(label="Yes, remove", style=discord.ButtonStyle.danger, custom_id="rm:num:final_yes")
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)

        error_text: Optional[str] = None
        selected_items = self.parent_view.get_selected_items()
        if not selected_items:
            error_text = "❌ No players selected. Operation cancelled."

        if error_text is None:
            try:
                await self.parent_view.owner.remove_selected_players(interaction, selected_items)
            except Exception as ex:
                logger.exception("remove_selected_players failed: %s", ex)
                error_text = f"⚠️ Error while removing.: {ex}"

        try:
            await self.orig_inter.edit_original_response(view=None)
            if self.parent_view.message:
                self.parent_view.owner._forget_view(self.parent_view.message.id)
        except Exception:
            pass

        try:
            if interaction.message:
                if error_text is None:
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        content="✅ Removal completed.",
                        view=None,
                        embed=None,
                    )
                else:
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        content=error_text,
                        view=None,
                        embed=None,
                    )
            else:
                await interaction.followup.send(error_text or "✅ Removal completed.", ephemeral=True)
        except Exception:
            pass

        try:
            self.parent_view.owner._forget_transient(self)  # type: ignore[attr-defined]
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="rm:num:final_no")
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False, ephemeral=True)

        for c in self.parent_view.children:
            c.disabled = False

        try:
            await self.orig_inter.edit_original_response(view=self.parent_view)
        except Exception:
            pass

        try:
            if interaction.message:
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    content="Canceled.",
                    view=None,
                    embed=None,
                )
            else:
                await interaction.followup.send("Canceled.", ephemeral=True)
        except Exception:
            pass

        try:
            self.parent_view.owner._forget_transient(self) 
        except Exception:
            pass
        self.stop()

class _DigitButton(discord.ui.Button["NumberedChecklistView"]):
    def __init__(self, idx: int, item: ChecklistItem):
        super().__init__(
            label=str(idx),
            style=discord.ButtonStyle.success if item.checked else discord.ButtonStyle.secondary,
            custom_id=f"rm:num:{idx}:{item.id}", 
            row=0,
        )
        self.zero_based_index = idx - 1

    async def callback(self, interaction: discord.Interaction) -> None:  
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)
        view: NumberedChecklistView = self.view 
        await view.toggle_by_index(self.zero_based_index, interaction)

class _ConfirmRemove(discord.ui.Button["NumberedChecklistView"]):
    def __init__(self):
        super().__init__(label="Confirm Remove", style=discord.ButtonStyle.danger, custom_id="rm:num:confirm", row=1)

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)

        view: NumberedChecklistView = self.view

        for c in view.children:
            c.disabled = True
        try:
            if interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=view)
        except Exception:
            pass

        selected_items = view.get_selected_items()
        have_selection = bool(selected_items)

        if view.double_confirm:
            if not have_selection:
                try:
                    await view.disable_and_finalize(
                        interaction,
                        error_text="❌ No players selected. Process aborted.",
                    )
                except Exception:
                    pass
            else:
                confirm_embed = view.build_confirm_embed(selected_items)
                final_view = FinalConfirmView(parent_view=view, orig_interaction=view.orig_inter) 
                m2 = await interaction.followup.send(embed=confirm_embed, view=final_view, ephemeral=True)
                
                try:
                    final_view.message = m2
                    view.owner._remember_transient(final_view) 
                except Exception:
                    pass
        else:
            if not have_selection:
                try:
                    await view.disable_and_finalize(
                        interaction,
                        error_text="❌ No players selected. Process aborted.",
                    )
                except Exception:
                    pass
            else:
                await view.confirm(interaction)

class NumberedChecklistView(discord.ui.View):
    def __init__(
        self,
        owner_cog: "RemovePlayerFromSquad",
        title: str,
        items: List[ChecklistItem],
        *,
        with_confirm: bool = True,
        double_confirm: bool = False,
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
        self.double_confirm = double_confirm
        self.message: Optional[discord.Message] = None
        self.orig_inter: Optional[discord.Interaction] = None
        self.requester_id: Optional[int] = None

        for idx, it in enumerate(self.items, start=1):
            self.add_item(_DigitButton(idx, it))

        if with_confirm:
            self.add_item(_ConfirmRemove())

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
                self.owner._forget_view(self.message.id)
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.requester_id is None:
            return True
        return interaction.user and interaction.user.id == self.requester_id

    def get_selected_items(self) -> List[ChecklistItem]:
        return [it for it in self.items if it.checked]

    def build_confirm_embed(self, selected: List[ChecklistItem]) -> discord.Embed:
        e = discord.Embed(
            title="⚠️ The following players will be removed from the squad:",
            colour=discord.Color.red(),
        )
        lines = []
        for i, it in enumerate(selected, start=1):
            lines.append(f"{i}.  **{it.name}** (Level {it.level} - _{it.role}_)")
        e.add_field(name="\u200b", value="\n".join(lines), inline=False)
        return e

    def build_embed(self) -> discord.Embed:
        e = discord.Embed(title=self.title)
        lines = []
        for i, it in enumerate(self.items, start=1):
            mark = "✅" if it.checked else "⬜"
            lines.append(f"{i}. {mark}  **{it.name}** (Level {it.level} - _{it.role}_)")
        e.description = "\n".join(lines)
        return e

    async def toggle_by_index(self, i0: int, interaction: discord.Interaction) -> None:
        if 0 <= i0 < len(self.items):
            self.items[i0].checked = not self.items[i0].checked
            
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.row == 0 and child.label == str(i0 + 1):
                    child.style = (
                        discord.ButtonStyle.success if self.items[i0].checked else discord.ButtonStyle.secondary
                    )
                    break

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

    async def disable_and_finalize(self, interaction: discord.Interaction, error_text: Optional[str] = None) -> None:
        for c in self.children:
            c.disabled = True
        try:
            if interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        try:
            await interaction.followup.send(error_text or "ℹ️ Process completed.", ephemeral=True)
        except Exception:
            pass

        try:
            if self.orig_inter is not None:
                await self.orig_inter.edit_original_response(view=None)
            elif interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=None)
            if self.message:
                self.owner._forget_view(self.message.id)
        except Exception:
            pass

    async def confirm(self, interaction: discord.Interaction) -> None:
        selected_items = self.get_selected_items()
        error_text: Optional[str] = None

        if not selected_items:
            error_text = "❌ No players selected. Operation aborted."

        if error_text is None:
            try:
                await self.owner.remove_selected_players(interaction, selected_items)
            except Exception as ex:
                logger.exception("remove_selected_players failed: %s", ex)
                error_text = f"⚠️ Error while removing: {ex}"

        try:
            if self.orig_inter is not None:
                await self.orig_inter.edit_original_response(view=None)
            elif interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=None)
            if self.message:
                self.owner._forget_view(self.message.id)
        except Exception:
            pass

        if error_text is not None:
            try:
                await interaction.followup.send(error_text, ephemeral=True)
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
        self._transient_views: set[discord.ui.View] = set()

    def _remember_view(self, view: discord.ui.View, msg: discord.Message) -> None:
        self._active_views[msg.id] = view
        try:
            setattr(view, "message", msg)
        except Exception:
            pass

    def _forget_view(self, message_id: int) -> None:
        self._active_views.pop(message_id, None)

    def _remember_transient(self, view: discord.ui.View) -> None:
        self._transient_views.add(view)

    def _forget_transient(self, view: discord.ui.View) -> None:
        self._transient_views.discard(view)

    async def background_task(self) -> None:
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)

    @app_commands.command(name="remove_player_from_squad", description="Removes a player from their squad. (SL only)")
    async def remove_player_from_squad(self, interaction: discord.Interaction) -> None:
        did_defer = False
        error_message: Optional[str] = None
        final_embed: Optional[discord.Embed] = None
        final_view: Optional[NumberedChecklistView] = None

        try:
            if not isinstance(interaction.user, discord.Member):
                error_message = "❌ This command only works on the server."
                logger.info("%s used command outside the server.", interaction.user)

            if error_message is None and not has_Allowed_Role(interaction.user, "remove player from squad"):
                error_message = "❌ You do not have permission for this command."
                logger.info("%s lacks permission 'remove player from squad'.", interaction.user)

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
                    logger.info("%s is not ingame.", interaction.user)
                else:
                    ingame_name = ingame.get_Ingame_Player_Name(player_id)
                    role = ingame.get_Role(player_id)
                    if role not in ("officer", "tankcommander", "spotter"):
                        error_message = f"❌ {ingame_name}, you are not a Squad Leader. Only Squad Leaders can use this command."
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
                    error_message = f"ℹ️ **No** other members in your squad **{(squad or '').upper()}**"

            if error_message is None:
                title = f"Choose the player you want to remove from {(squad or '').upper()}:"
                final_view = NumberedChecklistView(self, title, items, with_confirm=True, double_confirm=True)
                final_embed = final_view.build_embed()

        except Exception as e:
            logger.exception("Unexpected error in remove_player_from_squad: %s", e)
            error_message = f"⚠️ Unexpected error: {e}"

        try:
            if error_message is None and did_defer and final_view and final_embed:
                msg = await interaction.edit_original_response(embed=final_embed, view=final_view)
                final_view.set_context(orig_inter=interaction, msg=msg, requester_id=interaction.user.id)
                self._remember_view(final_view, msg)
            else:
                if not did_defer:
                    await safe_Send(interaction, error_message or "⚠️ Nothing to show.")
                else:
                    await interaction.edit_original_response(content=error_message or "⚠️ Nothing to show.", embed=None, view=None)
        except Exception:
            logger.exception("Failed to send response in remove_player_from_squad.")

    async def remove_selected_players(self, interaction: discord.Interaction, items: List[ChecklistItem]) -> None:
        result_text: Optional[str] = None
        try:
            valid = [it for it in items if isinstance(it, ChecklistItem)]

            seen: set[str] = set()
            unique: List[ChecklistItem] = []
            for it in valid:
                if it.id not in seen:
                    unique.append(it)
                    seen.add(it.id)

            successes: List[ChecklistItem] = []
            failures: List[tuple[ChecklistItem, str]] = []

            if unique:
                for it in unique:
                    try:
                        data = {"player_id": str(it.id), "reason": "The squad leader doesn’t want you in the squad anymore."}

                        if not (config.get("rcon", 0, "discord_commands", 0, "dryrun")):
                            await rcon.remove_from_squad(data)
                            logger.info ("Removed player: " + str (it.name) + " from squad!")
                        else:
                            logger.info ("Dry run player: " + str (it.name) + " not removed from squad!")

                        successes.append(it)
                    except Exception as ex:
                        failures.append((it, str(ex)))
            else:
                result_text = "ℹ️ No valid players to remove."

            if result_text is None:
                parts: List[str] = []
                if successes:
                    parts.append("✅ Removed: " + ", ".join(f"{x.name} ({x.id})" for x in successes))
                if failures:
                    parts.append("⚠️ Failed: " + ", ".join(f"{x.name} ({x.id}) – {reason}" for x, reason in failures))
                if not parts:
                    parts.append("ℹ️ Nothing changed.")
                result_text = "\n".join(parts)

        except Exception as e:
            logger.error("Failed to remove selected players: %s", e)
            result_text = f"⚠️ failed removing: {e}"

        try:
            await interaction.followup.send(result_text or "ℹ️ Done.", ephemeral=True)
        except Exception:
            pass
