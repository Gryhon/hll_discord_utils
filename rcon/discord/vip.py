import discord
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from discord.ext import commands
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from rcon.discord.discordutils import safe_Send, has_Allowed_Role, CommandError, is_User_Panel_Dryrun, add_Provided_By, PROVIDED_BY
from lib.config import config

# get Logger for this module
logger = logging.getLogger(__name__)


class GiftVipConfirmView(discord.ui.View):
    """Confirmation dialog shown before a VIP gift is executed."""

    def __init__(self, author_id: int, donor_id: str, recipient_id: str,
                 new_donor_expiry, new_recipient_expiry: datetime,
                 donor_permanent: bool, dryrun: bool,
                 donor_name: str, recipient_name: str):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.donor_id = donor_id
        self.recipient_id = recipient_id
        self.new_donor_expiry = new_donor_expiry
        self.new_recipient_expiry = new_recipient_expiry
        self.donor_permanent = donor_permanent
        self.dryrun = dryrun
        self.donor_name = donor_name
        self.recipient_name = recipient_name

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Gift", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        try:
            donor_payload = {
                "player_id": self.donor_id,
                "description": f"VIP gifted 1 day to {self.recipient_name} via Discord",
                "expiration": self.new_donor_expiry.isoformat()
            }
            recipient_payload = {
                "player_id": self.recipient_id,
                "description": f"VIP gift from {self.donor_name} to {self.recipient_name} via Discord",
                "expiration": self.new_recipient_expiry.isoformat()
            }

            if not self.dryrun:
                if not self.donor_permanent:
                    await rcon.add_Vip(donor_payload)
                await rcon.add_Vip(recipient_payload)
                logger.info(
                    f"VIP gift confirmed: donor={self.donor_id} ({'permanent' if self.donor_permanent else self.new_donor_expiry.date()}) "
                    f"→ recipient={self.recipient_id} new_expiry={self.new_recipient_expiry.date()} "
                    f"by {interaction.user.name}"
                )
                donor_vip = "permanent" if self.donor_permanent else self.new_donor_expiry.strftime("%Y-%m-%d")
                embed = discord.Embed(
                    title="VIP Gift — Success",
                    description=f"**{self.donor_name}** gifted 1 VIP day to **{self.recipient_name}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Your VIP", value=donor_vip, inline=True)
                embed.add_field(name=f"{self.recipient_name}'s VIP", value=self.new_recipient_expiry.strftime("%Y-%m-%d"), inline=True)
                embed.set_footer(text=f"Gifted by {interaction.user.display_name} · {PROVIDED_BY}")
                embed.timestamp = datetime.now()
            else:
                logger.info(f"DryRun - VIP gift: donor={self.donor_id} → recipient={self.recipient_id} by {interaction.user.name}")
                donor_vip = "permanent" if self.donor_permanent else self.new_donor_expiry.strftime("%Y-%m-%d")
                embed = discord.Embed(
                    title="VIP Gift — DryRun",
                    description=f"**{self.donor_name}** gifted 1 VIP day to **{self.recipient_name}**",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Your VIP", value=donor_vip, inline=True)
                embed.add_field(name=f"{self.recipient_name}'s VIP", value=self.new_recipient_expiry.strftime("%Y-%m-%d"), inline=True)
                embed.set_footer(text=f"DryRun — no changes made · {interaction.user.display_name} · {PROVIDED_BY}")
                embed.timestamp = datetime.now()

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"Error in GiftVipConfirmView.confirm: {e}", exc_info=True)
            await interaction.response.edit_message(content="❌ An error occurred while processing the gift.", embed=None, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="Gift cancelled.", embed=None, view=None)


def build_Vip_Status_View(name: str, expiry, days) -> discord.ui.LayoutView:
    """Builds the VIP status display as a Components V2 container, matching the look of
    the rest of the admin/user panels instead of a plain embed."""
    if expiry is None or days == 0:
        accent, icon = discord.Color.greyple(), "🎫"
        body = "No active VIP subscription."
    elif days == -1:
        accent, icon = discord.Color.gold(), "👑"
        body = "**Status:** ✅ Active\n**Expires:** never — permanent VIP"
    else:
        expiring_soon = days <= 3
        accent = discord.Color.orange() if expiring_soon else discord.Color.green()
        icon = "⏳" if expiring_soon else "✅"
        body = (
            "**Status:** ✅ Active\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d')}\n"
            f"**Days remaining:** {days}"
        )
        if expiring_soon:
            body += "\n\n-# ⚠️ Expiring soon."

    container = discord.ui.Container(accent_colour=accent)
    container.add_item(discord.ui.TextDisplay(f"### {icon} VIP Status — {name}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))

    add_Provided_By(container)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


class VipManagement(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.loop_started = False

    async def get_Vip_Profile(self, player_id: str):
        """Fetches the PlayerProfile for a given T17 ID."""
        try:
            return await rcon.get_Player_Profile({"player_id": player_id})
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    # --- VIP status ---

    async def vip_status(self, interaction: discord.Interaction):
        try:
            if not has_Allowed_Role(interaction.user, "vip_status"):
                raise CommandError("You do not have permission for this command.")

            player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)

            if not player_id:
                raise CommandError("You are not registered.")
            profile = await self.get_Vip_Profile(player_id)

            if not profile:
                raise CommandError("Could not retrieve your player profile.")

            expiry = profile.get_Vip_Expiry()
            days = profile.get_Vip_Days_Remaining()
            name = profile.get_Player_Name() or player_id

            view = build_Vip_Status_View(name, expiry, days)
            await interaction.response.send_message(view=view, ephemeral=True)

            logger.info(f"VIP status checked by {interaction.user.name} — player_id={player_id} days={days}")

        except CommandError as e:
            await safe_Send(interaction, f"❌ {e}")
        except Exception as e:
            logger.error(f"Unexpected error in vip_status: {e}")

    # --- Gift VIP ---
    # `recipient` is a player_id already resolved via the shared player-search flow
    # in the user menu (see userpanel.py) — the caller is always a registered user by the
    # time this is reachable, since the menu only shows this action to registered users.

    async def gift_vip(self, interaction: discord.Interaction, recipient: str):
        logger.info(f"gift_vip called by {interaction.user.name} recipient={recipient!r}")
        try:
            if not has_Allowed_Role(interaction.user, "gift_vip"):
                raise CommandError("You do not have permission for this command.")

            player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)

            if not player_id:
                raise CommandError("You are not registered.")
            if recipient == player_id:
                raise CommandError("You cannot gift VIP to yourself.")

            donor_profile = await self.get_Vip_Profile(player_id)
            if not donor_profile:
                raise CommandError("Could not retrieve your player profile.")

            donor_days = donor_profile.get_Vip_Days_Remaining()
            donor_expiry = donor_profile.get_Vip_Expiry()
            donor_permanent = donor_days == -1

            if donor_permanent and not config.get("rcon", 0, "user_panel", 0, "commands", 0, "vip_management", 0, "allow_gift_from_permanent", default=False):
                raise CommandError("You have permanent VIP. Gifting from a permanent account is not supported.")
            if not donor_permanent and donor_days <= 1:
                raise CommandError(f"You only have `{donor_days}` VIP day(s) remaining. You need more than 1 day to gift one.")

            now = datetime.now(timezone.utc)
            new_donor_expiry = donor_expiry if donor_permanent else donor_expiry - timedelta(days=1)

            recipient_profile = await self.get_Vip_Profile(recipient)
            donor_name = donor_profile.get_Player_Name() or player_id
            recipient_name = (recipient_profile.get_Player_Name() if recipient_profile else None) or recipient
            recipient_expiry = recipient_profile.get_Vip_Expiry() if recipient_profile else None
            base = max(now, recipient_expiry) if recipient_expiry else now
            new_recipient_expiry = base + timedelta(days=1)

            dryrun = is_User_Panel_Dryrun()

            donor_vip_after = "permanent" if donor_permanent else new_donor_expiry.strftime("%Y-%m-%d")
            embed = discord.Embed(
                title="Confirm VIP Gift",
                description=f"**{donor_name}** gifts 1 VIP day to **{recipient_name}**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Your VIP after", value=donor_vip_after, inline=True)
            embed.add_field(name="Recipient VIP after", value=new_recipient_expiry.strftime("%Y-%m-%d"), inline=True)
            embed.set_footer(text=f"{'DryRun — no changes will be made' if dryrun else 'This action cannot be undone.'} · {PROVIDED_BY}")
            embed.timestamp = datetime.now()

            view = GiftVipConfirmView(
                author_id=interaction.user.id,
                donor_id=player_id,
                recipient_id=recipient,
                new_donor_expiry=new_donor_expiry,
                new_recipient_expiry=new_recipient_expiry,
                donor_permanent=donor_permanent,
                dryrun=dryrun,
                donor_name=donor_name,
                recipient_name=recipient_name
            )
            await safe_Send(interaction, embed=embed, view=view)

        except CommandError as e:
            await safe_Send(interaction, f"❌ {e}")
        except Exception as e:
            logger.error(f"Unexpected error in gift_vip: {e}", exc_info=True)

    async def background_Task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_Task())
            logger.info("Background task (VipManagement) started")
