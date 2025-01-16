import logging
from datetime import datetime
import discord
from lib.config import config
from typing import Optional

logger = logging.getLogger(__name__)

async def send_success_embed(
    guild: discord.Guild,
    user: discord.User,
    action: str,
    old_name: str,
    new_name: str
):
    """Send a success embed to the configured channel."""
    try:
        # Get channel ID from config
        channel_id = config.get("rcon", 0, "name_change_registration", "log_channel_id")
        if not channel_id:
            logger.warning("No log channel ID configured for name change notifications")
            return

        # Get the channel
        channel = guild.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Could not find channel with ID {channel_id}")
            return

        # Create embed
        embed = discord.Embed(
            title="Name Change Registration",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="User",
            value=f"{user.mention} ({user.name})",
            inline=False
        )
        
        embed.add_field(
            name="Action",
            value=action.title(),
            inline=False
        )
        
        if old_name:
            embed.add_field(
                name="Old Name",
                value=old_name,
                inline=True
            )
        
        embed.add_field(
            name="New Name",
            value=new_name,
            inline=True
        )

        # Send the embed
        await channel.send(embed=embed)
        logger.info(f"Sent success embed for {user.name}'s {action}")

    except Exception as e:
        logger.error(f"Error sending success embed: {e}", exc_info=True)

async def handle_name_update_response(
    interaction: discord.Interaction,
    member: discord.Member,
    formatted_name: str,
    components: dict,
    role_error: Optional[str] = None
) -> None:
    """Handle the response message for name updates"""
    try:
        # Send success embed
        await send_success_embed(
            interaction.guild,
            interaction.user,
            'name_changed',
            formatted_name,
            None,  # t17_id
            components
        )
        
        # Send response to user
        if role_error:
            await interaction.response.send_message(
                f"Successfully updated your nickname!\nNote: {role_error}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Successfully updated your nickname!",
                ephemeral=True
            )
            
    except Exception as e:
        logger.error(f"Error handling name update response: {e}")
        await interaction.response.send_message(
            "Nickname updated but there was an error sending the confirmation message.",
            ephemeral=True
        ) 