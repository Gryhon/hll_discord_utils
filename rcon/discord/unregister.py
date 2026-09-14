import discord
import logging
import asyncio
from discord.ext import commands
from rcon.discord.discordbase import DiscordBase
from rcon.discord.discordutils import is_User_Panel_Dryrun, add_Provided_By
from lib.config import config

logger = logging.getLogger(__name__)


def build_Result_View(accent_colour: discord.Colour, heading: str, body: str) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_colour=accent_colour)
    container.add_item(discord.ui.TextDisplay(f"### {heading}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    add_Provided_By(container)
    view.add_item(container)
    return view


class Unregister(commands.Cog, DiscordBase):
    def __init__(self, bot):
        super().__init__()
        self.shutdown_event = asyncio.Event()
        self.bot = bot
        self.in_Loop = False
        self.loop_started = False

    async def unregister_me(self, interaction: discord.Interaction):
        try:
            user = interaction.user

            player_id,_,_,_,_ = self.select_T17_Voter_Registration (user.id)

            if player_id is None:
                await interaction.response.send_message (f"{user.name}, you are not registered.", ephemeral=True)
                logger.info(f"User {user.name} (ID: {user.id}) is not registered")
            else:
                if is_User_Panel_Dryrun():
                    logger.info(f"DryRun - User {user.name} (ID: {user.id}) chose to unregister - registration kept.")
                    await interaction.response.send_message(f"{user.name}, you have been successfully unregistered. Hope we will see you again.", ephemeral=True)
                elif self.delete_T17_Voter_Registration(user.id):
                    logger.info(f"User {user.name} (ID: {user.id}) chose to unregister.")
                    await interaction.response.send_message(f"{user.name}, you have been successfully unregistered. Hope we will see you again.", ephemeral=True)
                else:
                    await interaction.response.send_message("Failed to unregister user due to a database error.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in unregister_user: {e}")
            await interaction.response.send_message ("An error occurred while trying to unregister the user.", ephemeral=True)

    async def unregister_user_by_id(self, interaction: discord.Interaction, discord_user_id: int):
        """Removes another user's T17 registration by their Discord user id. Intended for
        the admin panel's search-based unlink flow — access is controlled there via the
        channel's permissions, not a role check here. Uses a raw <@id> mention rather than
        a resolved discord.Member so it also works for users who have left the server."""
        mention = f"<@{discord_user_id}>"
        try:
            # Check if user is registered
            player_id,_,_,_,_ = self.select_T17_Voter_Registration(discord_user_id)

            if player_id is None:
                await interaction.response.send_message(view=build_Result_View(
                    discord.Color.blurple(), "ℹ️ Not Registered",
                    f"{mention} has no linked in-game account — there's nothing to unlink."
                ), ephemeral=True)
                logger.info(f"User ID {discord_user_id} is not registered")
            else:
                display_name = self.select_Voter_Registration_Name(discord_user_id) or str(discord_user_id)
                # Remove from database using DiscordBase method
                if self.delete_T17_Voter_Registration(discord_user_id):
                    logger.info(f"User {display_name} (ID: {discord_user_id}) was unregistered by {interaction.user.name}")
                    await interaction.response.send_message(view=build_Result_View(
                        discord.Color.green(), "✅ Account Unlinked",
                        f"{mention}'s in-game account has been unlinked. They'll need to re-link it "
                        "via the **Ingame Command** menu before using registered features again."
                    ), ephemeral=True)
                else:
                    await interaction.response.send_message(view=build_Result_View(
                        discord.Color.red(), "❌ Unlink Failed",
                        f"Could not unlink {mention} due to a database error. Check the logs for details."
                    ), ephemeral=True)
                    logger.error(f"Failed to unregister user {display_name} (ID: {discord_user_id}) due to database error")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await interaction.response.send_message(view=build_Result_View(
                discord.Color.red(), "❌ Something Went Wrong",
                f"An error occurred while trying to unlink {mention}."
            ), ephemeral=True)

    async def background_task(self):
        while not self.shutdown_event.is_set():
                await asyncio.sleep (5)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_started: 
            self.loop_started = True 
            self.bot.loop.create_task(self.background_task())
            logger.info("Background task started")


    