import discord
import logging
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List
from discord import app_commands
from discord.ext import commands
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from rcon.discord.discordutils import safe_Send, require_Role, verify_And_Register, CommandError
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
                embed.set_footer(text=f"Gifted by {interaction.user.display_name}")
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
                embed.set_footer(text=f"DryRun — no changes made · {interaction.user.display_name}")

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"Error in GiftVipConfirmView.confirm: {e}", exc_info=True)
            await interaction.response.edit_message(content="❌ An error occurred while processing the gift.", embed=None, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="Gift cancelled.", embed=None, view=None)


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

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await safe_Send(interaction, f"❌ {error}")
        else:
            logger.error(f"Unexpected command error: {error}")

    async def autocomplete_Player_Name(self, current: str) -> List[app_commands.Choice[str]]:
        """Shared autocomplete logic for player name fields."""
        try:
            logger.info(f"Autocomplete called with query: {current!r}")
            multi_array = await asyncio.wait_for(
                rcon.search_Players(current.replace(" ", "%")),
                timeout=2.5
            )
            if multi_array:
                logger.info(f"Autocomplete returning {len(multi_array)} result(s)")
                return [
                    app_commands.Choice(
                        name=f"Last: {datetime.fromtimestamp(p[3] / 1000).strftime('%Y-%m-%d')} - {', '.join(p[1])}"[:100],
                        value=p[0]
                    )
                    for p in multi_array
                ]
            logger.info("Autocomplete returning no results")
            return []
        except asyncio.TimeoutError:
            logger.warning("Autocomplete timed out — no suggestions returned.")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in autocomplete_Player_Name: {e}", exc_info=True)
            return []

    # --- /vip_status ---

    @app_commands.command(name="vip_status", description="Check your VIP status and remaining days")
    @app_commands.describe(your_ingame_name="Your in-game name — only required if you are not yet registered")
    @require_Role("vip_management")
    async def vip_status(self, interaction: discord.Interaction, your_ingame_name: str = None):
        try:
            player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)

            if not player_id:
                if not your_ingame_name:
                    raise CommandError("You are not registered. Please provide your in-game name via the `your_ingame_name` field.")
                if not bool(re.fullmatch(r"[0-9a-fA-F]{32}", your_ingame_name)):
                    raise CommandError("Invalid in-game name. Please select your name from the autocomplete list.")
                player_id = your_ingame_name
            profile = await self.get_Vip_Profile(player_id)

            if not profile:
                raise CommandError("Could not retrieve your player profile.")

            expiry = profile.get_Vip_Expiry()
            days = profile.get_Vip_Days_Remaining()
            name = profile.get_Player_Name() or player_id

            if expiry is None or days == 0:
                embed = discord.Embed(title=f"VIP Status — {name}", color=discord.Color.greyple())
                embed.add_field(name="Status", value="No active VIP", inline=False)
            elif days == -1:
                embed = discord.Embed(title=f"VIP Status — {name}", color=discord.Color.gold())
                embed.add_field(name="Status", value="Active", inline=True)
                embed.add_field(name="Expires", value="never (permanent)", inline=True)
            else:
                embed = discord.Embed(title=f"VIP Status — {name}", color=discord.Color.green())
                embed.add_field(name="Status", value="Active", inline=True)
                embed.add_field(name="Expires", value=expiry.strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Days remaining", value=str(days), inline=True)

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

            logger.info(f"VIP status checked by {interaction.user.name} — player_id={player_id} days={days}")

        except CommandError as e:
            await safe_Send(interaction, f"❌ {e}")
        except Exception as e:
            logger.error(f"Unexpected error in vip_status: {e}")

    @vip_status.autocomplete("your_ingame_name")
    async def autocomplete_vip_status_name(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.autocomplete_Player_Name(current)

    # --- /gift_vip ---

    @app_commands.command(name="gift_vip", description="Gift one VIP day to another player (deducted from your account)")
    @app_commands.describe(
        recipient="Choose the recipient's in-game name from the autocomplete list",
        my_ingame_name="Your in-game name — only required if you are not yet registered"
    )
    @require_Role("vip_management")
    async def gift_vip(self, interaction: discord.Interaction, recipient: str, my_ingame_name: str = None):
        logger.info(f"gift_vip called by {interaction.user.name} recipient={recipient!r} my_ingame_name={my_ingame_name!r}")
        try:
            player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)

            if not player_id:
                if not my_ingame_name:
                    raise CommandError("You are not registered. Please provide your in-game name via the `my_ingame_name` field.")
                if not bool(re.fullmatch(r"[0-9a-fA-F]{32}", my_ingame_name)):
                    raise CommandError("Invalid in-game name. Please select your name from the autocomplete list.")
                await verify_And_Register(interaction, my_ingame_name, self, verify_ingame=True)
                player_id = my_ingame_name

            if not bool(re.fullmatch(r"[0-9a-fA-F]{32}", recipient)):
                raise CommandError("Invalid recipient. Please select a name from the autocomplete list.")
            if recipient == player_id:
                raise CommandError("You cannot gift VIP to yourself.")

            donor_profile = await self.get_Vip_Profile(player_id)
            if not donor_profile:
                raise CommandError("Could not retrieve your player profile.")

            donor_days = donor_profile.get_Vip_Days_Remaining()
            donor_expiry = donor_profile.get_Vip_Expiry()
            donor_permanent = donor_days == -1

            if donor_permanent and not config.get("rcon", 0, "discord_commands", 0, "vip_management", 0, "allow_gift_from_permanent", default=False):
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

            dryrun = config.get("rcon", 0, "discord_commands", 0, "vip_management", 0, "dryrun", default=False)

            donor_vip_after = "permanent" if donor_permanent else new_donor_expiry.strftime("%Y-%m-%d")
            embed = discord.Embed(
                title="Confirm VIP Gift",
                description=f"**{donor_name}** gifts 1 VIP day to **{recipient_name}**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Your VIP after", value=donor_vip_after, inline=True)
            embed.add_field(name="Recipient VIP after", value=new_recipient_expiry.strftime("%Y-%m-%d"), inline=True)
            embed.set_footer(text="DryRun — no changes will be made" if dryrun else "This action cannot be undone.")

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

    @gift_vip.autocomplete("recipient")
    async def autocomplete_recipient(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        try:
            logger.info(f"autocomplete_recipient called with query: {current!r}")
            multi_array = await asyncio.wait_for(
                rcon.search_Players(current.replace(" ", "%")),
                timeout=2.5
            )
            if multi_array:
                return [
                    app_commands.Choice(
                        name=f"Last: {datetime.fromtimestamp(p[3] / 1000).strftime('%Y-%m-%d')} - {', '.join(p[1])}"[:100],
                        value=p[0]
                    )
                    for p in multi_array
                ]
            return []
        except asyncio.TimeoutError:
            logger.warning("autocomplete_recipient timed out.")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in autocomplete_recipient: {e}", exc_info=True)
            return []

    @gift_vip.autocomplete("my_ingame_name")
    async def autocomplete_my_ingame_name(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.autocomplete_Player_Name(current)

    async def background_Task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_Task())
            logger.info("Background task (VipManagement) started")
