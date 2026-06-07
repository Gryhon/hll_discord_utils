import discord
import logging
import asyncio
import numpy as np
import rcon.rcon as rcon
from rcon.discord.discordbase import DiscordBase
from lib.config import config
from discord.ext import commands
from discord import app_commands


# get Logger for this modul
logger = logging.getLogger(__name__)


class MilCalculatorModal(discord.ui.Modal):
    def __init__(self, cog, fraction: app_commands.Choice[str], last_elevation: str = ""):
        super().__init__(title="🎯 Mil Calculator")
        self.cog = cog
        self.fraction = fraction

        self.distance_input = discord.ui.TextInput(
            label="Distance (m)",
            placeholder="100 – 1600",
            required=True,
            max_length=4,
        )
        self.elevation_input = discord.ui.TextInput(
            label="Elevation (mils)",
            placeholder="0 (optional)",
            required=False,
            max_length=5,
            default=last_elevation,
        )
        self.add_item(self.distance_input)
        self.add_item(self.elevation_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            distance = int(self.distance_input.value.strip())
            elevation_str = self.elevation_input.value.strip()
            elevation = int(elevation_str) if elevation_str else 0

            if not (100 <= distance <= 1600):
                await interaction.response.send_message(
                    "❌ Distance must be between 100 and 1600 meters.", ephemeral=True
                )
                return

            mil_value = await self.cog.calculate(distance, self.fraction.value)
            if elevation != 0:
                mil_value = mil_value - elevation

            await self.cog._send_ingame(interaction, distance, self.fraction.value, elevation)

            elev_hint = f" | Elevation: {elevation:+d} mils" if elevation != 0 else ""
            embed = discord.Embed(
                title=f"🎯 {self.fraction.name} — {distance} m{elev_hint}",
                description=f"## {mil_value} mils",
                color=discord.Color.orange(),
            )

            view = CalculateAgainView(self.cog, self.fraction, str(elevation) if elevation != 0 else "")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid input. Please enter valid numbers.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error in MilCalculatorModal: {e}")
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)


class CalculateAgainView(discord.ui.View):
    def __init__(self, cog, fraction: app_commands.Choice[str], last_elevation: str = ""):
        super().__init__(timeout=300)
        self.cog = cog
        self.fraction = fraction
        self.last_elevation = last_elevation

    @discord.ui.button(label="🔄 Calculate again", style=discord.ButtonStyle.primary)
    async def calculate_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MilCalculatorModal(self.cog, self.fraction, self.last_elevation)
        await interaction.response.send_modal(modal)


class ArtilleryCalculator(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def calculate_Mils(self, distance, min_distance, max_distance, min_mils, max_mils):
        mil = (((distance - min_distance) / (max_distance - min_distance)) * (min_mils - max_mils) + max_mils)
        logger.debug(f"Calculated Mil value for distance {distance} = {mil}")
        return round(mil)

    async def calculate(self, distance, fraction):
        try:
            mil_value = None

            if distance >= 100 and distance <= 1600:
                if fraction == "DE":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                elif fraction == "US":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 622, 978)

                elif fraction == "USSR":
                    mil_value = await self.calculate_Mils(distance, 100, 1600, 800, 1120)

                elif fraction == "GB":
                    if (distance >= 200 and distance <= 800) or (distance >= 1100 and distance <= 1200):
                        dis = distance - 5
                    else:
                        dis = distance
                    mil_value = await self.calculate_Mils(dis, 100, 1600, 267, 533)
                else:
                    logger.info(f"Unknown fraction: {fraction}")

            return mil_value

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    async def calculate_Intervall(self, distance: int, fraction: str, intervall: int, elevation: int = 0):
        try:
            half_interval = intervall / 2
            lower_bound = max(100, distance - half_interval)
            upper_bound = min(1600, distance + half_interval)

            if lower_bound == 100:
                upper_bound = min(100 + intervall, 1600)
            elif upper_bound == 1600:
                lower_bound = max(1600 - intervall, 100)

            meters = np.linspace(lower_bound, upper_bound, num=9)
            meters = sorted(set(map(lambda x: int(round(x)), meters)), reverse=True)

            if distance not in meters:
                meters.append(distance)
                meters = sorted(meters, reverse=True)

            MILs = [await self.calculate(m, fraction) for m in meters]

            if elevation != 0:
                MILs = [m - elevation if m is not None else None for m in MILs]

            return await self.create_Table(meters, MILs, distance, elevation)

        except Exception:
            logger.exception("Unexpected error in calculate_Intervall")
            return None

    async def create_Table(self, meters: list, MILs: list, distance: int, elevation: int = 0):
        try:
            FS   = "\u2007"  # FIGURE SPACE
            NBSP = "\u00A0"  # NO-BREAK SPACE

            digits_tab = str.maketrans("0123456789", "０１２３４５６７８９")

            header = f"{FS*4}METER{FS*2}{FS*4}MILS"
            if elevation != 0:
                header += f"{FS*2}(elev {elevation:+d})"
            sep   = f"{FS*4}" + "─" * 18
            lines = [header, sep]

            for m, mil in zip(meters, MILs):
                is_sel = (m == distance)

                mark_left  = f"{FS}-->{NBSP}" if is_sel else FS * 4
                mark_right = f"{NBSP}<--" if is_sel else ""

                m_str   = f"{m:04}".translate(digits_tab)
                mil_str = f"{mil:04}".translate(digits_tab) if mil is not None else "----"

                line = f"{mark_left}{m_str}{FS*2}|{FS*2}{mil_str}{mark_right}"
                lines.append(line)

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Unexpected error in create_Table: {e}")
            return None

    async def _send_ingame(self, interaction: discord.Interaction, distance: int, fraction: str, elevation: int = 0):
        """Sendet die Interval-Tabelle als In-Game-Nachricht, wenn der Spieler online ist."""
        if not config.get("rcon", 0, "artillery_calculator", 0, "in_game_messages", default=False):
            return

        player_id, _, _, _, _ = self.select_T17_Voter_Registration(interaction.user.id)
        ingame = await rcon.get_In_Game_Players()

        if ingame.is_Player_Ingame(player_id):
            table = await self.calculate_Intervall(
                distance, fraction,
                config.get("rcon", 0, "artillery_calculator", 0, "interval", default=100),
                elevation=elevation,
            )
            if table:
                logger.info(f"Send message to player {player_id}: distance={distance}m elevation={elevation}")
                await rcon.send_Player_Message({"player_id": str(player_id), "message": table})
        else:
            logger.debug(f"Player {player_id} not ingame — no message sent.")

    # --- Slash Command ---

    @app_commands.command(name="mil_calculator", description="Calculate mils from distance in meters")
    @app_commands.describe(fraction="Choose a fraction")
    @app_commands.choices(
        fraction=[
            app_commands.Choice(name="Germany", value="DE"),
            app_commands.Choice(name="USA",     value="US"),
            app_commands.Choice(name="USSR",    value="USSR"),
            app_commands.Choice(name="England", value="GB"),
        ],
    )
    async def mil_calculator(self, interaction: discord.Interaction,
                             fraction: app_commands.Choice[str]):
        logger.info(f"Mil Calculator used by {interaction.user.name} — fraction={fraction.name}")
        modal = MilCalculatorModal(self, fraction)
        await interaction.response.send_modal(modal)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)
