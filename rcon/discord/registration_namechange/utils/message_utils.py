import logging
from datetime import datetime
import discord
from lib.config import config

logger = logging.getLogger(__name__)

async def send_success_embed(
    guild: discord.Guild,
    user: discord.Member,
    action_type: str,
    new_name: str,
    t17_id: str = None
) -> None:
    """
    Send a success embed message to the configured channel.
    action_type can be 'registered' or 'name_changed'
    """
    try:
        # Check if message sending is enabled and get channel ID
        channel_id = config.get("comfort_functions", 0, "name_change_registration", "notifications", "channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Could not find channel with ID {channel_id}")
            return

        # Create embed
        embed = discord.Embed(
            title="✅ Registration Update",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        # Add user info
        embed.add_field(
            name="User",
            value=f"{user.mention} ({user.name})",
            inline=True
        )

        # Add action-specific fields
        if action_type == "registered":
            embed.description = "New User Registration"
            if t17_id:
                embed.add_field(
                    name="T17 ID",
                    value=t17_id,
                    inline=True
                )
        else:  # name_changed
            embed.description = "Nickname Update"

        embed.add_field(
            name="New Nickname",
            value=new_name,
            inline=True
        )

        # Send the embed
        await channel.send(embed=embed)

    except Exception as e:
        logger.error(f"Error sending success embed: {e}") 