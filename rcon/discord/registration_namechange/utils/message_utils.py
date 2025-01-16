import logging
from datetime import datetime
import discord
from lib.config import config
from typing import Optional

logger = logging.getLogger(__name__)

async def send_success_embed(
    guild: discord.Guild,
    user: discord.Member,
    action_type: str,
    new_name: str,
    t17_id: str = None,
    components: dict = None
) -> None:
    """
    Send a success embed message to the configured channel.
    action_type can be 'registered' or 'name_changed'
    """
    try:
        # Check if message sending is enabled and get channel ID
        if not config.get("rcon", 0, "name_change_registration", "notifications", "enabled", default=True):
            return
            
        channel_id = config.get("rcon", 0, "name_change_registration", "notifications", "channel_id")
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
            if components:
                component_text = []
                if components.get('clan_tag'): component_text.append(f"Clan: {components['clan_tag']}")
                if components.get('t17_number'): component_text.append(f"T17#: {components['t17_number']}")
                if components.get('emojis'): component_text.append(f"Emojis: {components['emojis']}")
                if component_text:
                    embed.add_field(
                        name="Components",
                        value='\n'.join(component_text),
                        inline=True
                    )

        embed.add_field(
            name="New Nickname",
            value=new_name,
            inline=True
        )

        # Send the embed
        await channel.send(embed=embed)

    except Exception as e:
        logger.error(f"Error sending success embed: {e}") 

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