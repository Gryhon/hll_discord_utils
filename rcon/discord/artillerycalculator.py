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

    # --- Session-Flows ---

    async def _run_classic_session(self, interaction: discord.Interaction, thread: discord.Thread,
                                   fraction: app_commands.Choice[str], check):
        await thread.send(
            f"Welcome to your exclusive Mil Calculator, {interaction.user.mention}!\n\n"
            "The thread will be automatically deleted if you enter `exit` or after 10 minutes of inactivity.\n\n"
            "Valid input values are between **100** and **1600** meters."
        )

        while True:
            try:
                message = await self.bot.wait_for('message', timeout=600.0, check=check)

                if message.content.lower() == "exit":
                    await thread.send("Exiting the calculator. See you next time!")
                    await asyncio.sleep(2)
                    break

                try:
                    distance = int(message.content)
                    if 100 <= distance <= 1600:
                        mil_value = await self.calculate(distance, fraction.value)
                        await self._send_ingame(interaction, distance, fraction.value)
                        await thread.send(f"Calculated Mil at {distance} meters: **{mil_value} Mils**.")
                    else:
                        await thread.send("Distance must be between 100 and 1600 meters!")
                except ValueError:
                    await thread.send("Invalid input. Please enter a valid number for the distance.")

            except asyncio.TimeoutError:
                await thread.send("Inactive for 10 minutes. The thread will be closed now.")
                await asyncio.sleep(5)
                break

    async def _run_spg_session(self, interaction: discord.Interaction, thread: discord.Thread,
                               fraction: app_commands.Choice[str], check):
        current_elevation: int | None = None
        last_distance: int | None = None

        await thread.send(
            f"Welcome to your exclusive **SPG Mil Calculator**, {interaction.user.mention}!\n\n"
            "**Step 1 — Enter the current elevation of your SPG** (in mils, can be negative).\n\n"
            "Commands:\n"
            "> `<distance>` — calculate mils for a distance (100–1600 m)\n"
            "> `elev <value>` — update elevation after moving (e.g. `elev -30`)\n"
            "> `exit` — close the calculator\n\n"
            "The thread closes automatically after 10 minutes of inactivity."
        )

        while True:
            try:
                message = await self.bot.wait_for('message', timeout=600.0, check=check)
                content = message.content.strip()

                if content.lower() == "exit":
                    await thread.send("Exiting the calculator. See you next time!")
                    await asyncio.sleep(2)
                    break

                # Elevation update command
                if content.lower().startswith("elev"):
                    parts = content.split()
                    if len(parts) == 2:
                        try:
                            current_elevation = int(parts[1])
                            response = f"✅ Elevation updated to **{current_elevation:+d} mils**."

                            if last_distance is not None:
                                raw = await self.calculate(last_distance, fraction.value)
                                adj = raw - current_elevation
                                response += (f"\nLast distance **{last_distance} m** recalculated: "
                                             f"raw {raw} − {current_elevation} = **{adj} mils**.")
                                await self._send_ingame(interaction, last_distance, fraction.value, current_elevation)

                            await thread.send(response)
                        except ValueError:
                            await thread.send("Invalid elevation. Use `elev <number>`, e.g. `elev -30`.")
                    else:
                        await thread.send("Use `elev <number>`, e.g. `elev 45`.")
                    continue

                # First input without elevation set → treat as elevation
                if current_elevation is None:
                    try:
                        current_elevation = int(content)
                        await thread.send(
                            f"✅ Elevation set to **{current_elevation:+d} mils**.\n"
                            "Now enter a target distance (100–1600 m)."
                        )
                    except ValueError:
                        await thread.send(
                            "Please enter the **elevation in mils** first (e.g. `45` or `-30`)."
                        )
                    continue

                # Distance input
                try:
                    distance = int(content)
                    if 100 <= distance <= 1600:
                        last_distance = distance
                        raw_mil = await self.calculate(distance, fraction.value)
                        adj_mil = raw_mil - current_elevation

                        await self._send_ingame(interaction, distance, fraction.value, current_elevation)
                        await thread.send(
                            f"Distance: **{distance} m** | Elevation: **{current_elevation:+d} mils**\n"
                            f"Raw: {raw_mil} − {current_elevation} = **Aim: {adj_mil} mils**"
                        )
                    else:
                        await thread.send("Distance must be between 100 and 1600 meters!")
                except ValueError:
                    await thread.send(
                        "Invalid input. Enter a distance (e.g. `800`) or update elevation (`elev 45`)."
                    )

            except asyncio.TimeoutError:
                await thread.send("Inactive for 10 minutes. The thread will be closed now.")
                await asyncio.sleep(5)
                break

    # --- Slash Command ---

    @app_commands.command(name="mil_calculator", description="Calculate mils from distance in meters")
    @app_commands.describe(
        fraction="Choose a fraction",
        gun_type="Artillery type — Classic or Self-Propelled Gun (SPG)",
    )
    @app_commands.choices(
        fraction=[
            app_commands.Choice(name="Germany", value="DE"),
            app_commands.Choice(name="USA",     value="US"),
            app_commands.Choice(name="USSR",    value="USSR"),
            app_commands.Choice(name="England", value="GB"),
        ],
        gun_type=[
            app_commands.Choice(name="Classic Artillery", value="classic"),
            app_commands.Choice(name="Self-Propelled Gun (SPG)", value="spg"),
        ],
    )
    async def mil_calculator(self, interaction: discord.Interaction,
                             fraction: app_commands.Choice[str],
                             gun_type: app_commands.Choice[str]):
        logger.info(f"Mil Calculator used by {interaction.user.name} — fraction={fraction.name} type={gun_type.value}")

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Threads can only be created in text channels.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "A private thread has been created for your calculation.\n"
            "Type `exit` to leave the calculator.",
            ephemeral=True,
        )

        thread_name = f"{fraction.name} {'SPG' if gun_type.value == 'spg' else 'Artillery'} — {interaction.user}"
        private_thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            auto_archive_duration=60,
        )
        await private_thread.add_user(interaction.user)

        def check(msg):
            return msg.author == interaction.user and msg.channel == private_thread

        if gun_type.value == "spg":
            await self._run_spg_session(interaction, private_thread, fraction, check)
        else:
            await self._run_classic_session(interaction, private_thread, fraction, check)

        await private_thread.delete(reason="Thread cleanup")
        logger.info(f"Closed Mil Calculator for {interaction.user.name}")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started:
            self.loop_started = True
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")

    async def background_task(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep(5)
