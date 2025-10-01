"""Utility helpers for applying TQE role permissions."""
from __future__ import annotations

from typing import Dict, Optional

import discord


def get_tqe_role(bot, guild: discord.Guild) -> Optional[discord.Role]:
    """Return the configured TQE role for the guild if one exists."""
    if guild is None:
        return None

    result = bot.db.execute_query(
        "SELECT tqe_role_id FROM server_config WHERE guild_id = %s",
        (guild.id,),
        fetch="one",
    )

    if not result or not result[0]:
        return None

    role = guild.get_role(int(result[0]))
    if role is None:
        # Stored role no longer exists – clear it from the database to prevent repeated lookups
        bot.db.execute_query(
            """UPDATE server_config SET tqe_role_id = NULL, updated_at = NOW() WHERE guild_id = %s""",
            (guild.id,),
        )
    return role


def build_tqe_overwrites(
    bot,
    guild: discord.Guild,
    *,
    base_overwrites: Optional[Dict[discord.abc.Snowflake, discord.PermissionOverwrite]] = None,
    channel_type: str = "text",
    grant_role: bool = True,
) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    """Return permission overwrites with TQE role visibility applied.

    Parameters
    ----------
    bot: commands.Bot
        Bot instance (used for database access).
    guild: discord.Guild
        Guild where the channel/category exists.
    base_overwrites: Optional[Dict]
        Existing overwrites to start from.
    channel_type: str
        One of ``"text"``, ``"category"`` or ``"voice"`` to determine which
        permission flags to adjust.
    grant_role: bool
        When ``False``, the base overwrites are returned untouched. This is
        useful for private channels that should not be visible to every TQE
        member.
    """

    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite] = dict(base_overwrites or {})

    if not grant_role:
        return overwrites

    tqe_role = get_tqe_role(bot, guild)
    if tqe_role is None:
        return overwrites

    # Ensure @everyone is hidden
    default_overwrite = overwrites.get(guild.default_role, discord.PermissionOverwrite())
    if channel_type == "category":
        default_overwrite.view_channel = False
    elif channel_type == "voice":
        default_overwrite.view_channel = False
        default_overwrite.connect = False
        default_overwrite.speak = False
    else:  # text channel
        default_overwrite.view_channel = False
        default_overwrite.read_messages = False
        default_overwrite.send_messages = False
    overwrites[guild.default_role] = default_overwrite

    # Allow the TQE role to access the channel/category
    role_overwrite = overwrites.get(tqe_role, discord.PermissionOverwrite())
    if channel_type == "category":
        role_overwrite.view_channel = True
    elif channel_type == "voice":
        role_overwrite.view_channel = True
        role_overwrite.connect = True
        role_overwrite.speak = True
    else:
        role_overwrite.view_channel = True
        role_overwrite.read_messages = True
        role_overwrite.send_messages = True
    overwrites[tqe_role] = role_overwrite

    return overwrites
