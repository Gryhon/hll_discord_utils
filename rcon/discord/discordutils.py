import discord
import logging
import random
import rcon.rcon as rcon
from discord import app_commands
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

def require_Role(item: str):
    """Decorator that checks guild membership and role permission before a command runs.
    Checks config for item-specific groups first, falls back to global groups.
    Raises CheckFailure with a user-facing message on failure."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command only works on the server.")
        if not has_Allowed_Role(interaction.user, item):
            raise app_commands.CheckFailure("You do not have permission for this command.")
        return True
    return app_commands.check(predicate)

class VerifyIngameNumber(discord.ui.Modal, title="Verify your identity"):
    """Modal for in-game number verification. Shows a 2-digit number input."""

    def __init__(self, expected_number: int):
        super().__init__()
        self.expected_number = expected_number
        self.result = False
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
                await interaction.response.send_message("✅ Verified!", ephemeral=True)
            else:
                self.result = False
                await interaction.response.send_message("❌ Wrong number. Please try again.", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.result = False


async def verify_And_Register(interaction: discord.Interaction, player_id: str, db, verify_ingame: bool = None):
    """Verifies a player's identity via in-game number and registers them in the DB.

    If verify_ingame is None, reads from config (register_player.verify_ingame).
    Must be called before any interaction response has been sent (uses send_modal).
    Raises CommandError if verification fails."""
    if verify_ingame is None:
        verify_ingame = config.get("rcon", 0, "register_player", 0, "verify_ingame", default=False)

    if verify_ingame:
        number = random.randint(10, 99)
        data = {
            "player_id": str(player_id),
            "message": f"Enter this number in Discord\nto verify your account:\n\n{number}"
        }
        logger.info(f"Send verification message to player_id={player_id} with number={number}")
        await rcon.send_Player_Message(data)

        modal = VerifyIngameNumber(number)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.result:
            raise CommandError("Verification failed. Please try again.")

    nick = interaction.guild.get_member(interaction.user.id).nick if interaction.guild else None
    db.insert_Voter_Registration(interaction.user.name, interaction.user.id, nick, player_id, 0, 0)
    logger.info(f"User {interaction.user.name} (ID={interaction.user.id}) registered with T17 ID {player_id}")


def has_Allowed_Role(member: discord.Member, item: str) -> bool:
    ret = False

    try:
        allowed_names = (config.get("rcon", 0, "discord_commands", 0, f"{item}", 0, "groups") or
                         config.get("rcon", 0, "discord_commands", 0, "groups") or [])
        
        if config.get("rcon", 0, "discord_commands", 0, "admin_always") and member.guild_permissions.administrator:
            ret = True
        else:
            ret = any(role.name in allowed_names for role in member.roles)

        return ret
    
    except Exception as e:
        logger.error(f"Error in has_Allowed_Role: {e}", exc_info=True)
        return False