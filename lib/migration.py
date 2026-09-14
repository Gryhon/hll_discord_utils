import logging
import shutil

logger = logging.getLogger(__name__)

CURRENT_VERSION = 3


# ─── Migration functions ───────────────────────────────────────────────────────

def migrate_v1_to_v2(cfg: dict) -> dict:
    """
    template_1.json → current:
    - comfort_functions: add broadcast_message, after_game_message (as messages list), auto_unban
    - add discord_commands
    - add inappropriate_name
    - map_vote: add schedule, map_pool[].profile
    - after_game_message.message (str) → messages (list)
    """
    for server in cfg.get("rcon", []):

        # guild_id: add if missing
        if "guild_id" not in server:
            server["guild_id"] = 0
            logger.info("Migration v1→v2: added guild_id")

        # comfort_functions: add sub-sections if missing
        for comfort in server.get("comfort_functions", []):
            if "broadcast_message" not in comfort:
                comfort["broadcast_message"] = [{"enabled": False}]
                logger.info("Migration v1→v2: added comfort_functions.broadcast_message")

            if "after_game_message" not in comfort:
                comfort["after_game_message"] = [{"enabled": False, "messages": []}]
                logger.info("Migration v1→v2: added comfort_functions.after_game_message")
            else:
                for agm in comfort["after_game_message"]:
                    if "message" in agm and "messages" not in agm:
                        agm["messages"] = [agm.pop("message")]
                        logger.info("Migration v1→v2: after_game_message.message → messages")

            if "auto_unban" not in comfort:
                comfort["auto_unban"] = [{"enabled": False, "VIP": True, "Clan": False, "Clans": [""]}]
                logger.info("Migration v1→v2: added comfort_functions.auto_unban")

        # discord_commands: new section
        if "discord_commands" not in server:
            server["discord_commands"] = [{
                "enabled": False,
                "dryrun": False,
                "admin_always": False,
                "groups": [""],
                "punish_me": [{"enabled": False, "groups": [""]}],
                "switch_me": [{"enabled": False, "groups": [""]}],
                "who_killed_me": [{"enabled": False, "groups": [""]}],
                "whom_i_killed": [{"enabled": False, "groups": [""]}],
                "remove_player_from_squad": [{"enabled": False, "groups": [""]}],
                "vip_management": [{"enabled": False, "dryrun": False, "allow_gift_from_permanent": False, "groups": [""]}]
            }]
            logger.info("Migration v1→v2: added discord_commands")

        # inappropriate_name: new section
        if "inappropriate_name" not in server:
            server["inappropriate_name"] = [{
                "enabled": False,
                "dryrun": False,
                "check_history_once": False,
                "channel_id": 0,
                "threshold": 0.85,
                "kick_message": "Your name or clan tag violates server rules. Please change it before rejoining.",
                "watch_message": "",
                "blacklist_id": 0,
                "temp_ban_duration": 0,
                "temp_ban_message": "",
                "perma_ban_message": "",
                "blacklist": [],
                "whitelist": []
            }]
            logger.info("Migration v1→v2: added inappropriate_name")
        else:
            for ina in server["inappropriate_name"]:
                if "check_history_once" not in ina:
                    ina["check_history_once"] = False
                    logger.info("Migration v1→v2: added inappropriate_name.check_history_once")
                if "kick_message" not in ina:
                    ina["kick_message"] = "Your name violates server rules. Please change it before rejoining."
                    logger.info("Migration v1→v2: added inappropriate_name.kick_message")
                if "temp_ban_duration" not in ina:
                    ina["temp_ban_duration"] = ina.pop("blacklist_duration", 0)
                    logger.info("Migration v1→v2: added inappropriate_name.temp_ban_duration")
                if "temp_ban_message" not in ina:
                    ina["temp_ban_message"] = ina.pop("blacklist_message", "")
                    logger.info("Migration v1→v2: added inappropriate_name.temp_ban_message")
                if "perma_ban_message" not in ina:
                    ina["perma_ban_message"] = "Your name violates server rules (permanent ban)."
                    logger.info("Migration v1→v2: added inappropriate_name.perma_ban_message")
                if "whitelist" not in ina:
                    ina["whitelist"] = []
                    logger.info("Migration v1→v2: added inappropriate_name.whitelist")

        # map_vote: add schedule, map_pool.profile, and audit_webhook
        for mv in server.get("map_vote", []):
            if "schedule" not in mv:
                mv["schedule"] = [{
                    "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "profile": "default",
                    "on": "00:00",
                    "off": None
                }]
                logger.info("Migration v1→v2: added map_vote.schedule")

            if "audit_webhook" not in mv:
                mv["audit_webhook"] = ""
                logger.info("Migration v1→v2: added map_vote.audit_webhook")

            for pool in mv.get("map_pool", []):
                if "profile" not in pool:
                    pool["profile"] = "default"
                    logger.info("Migration v1→v2: added map_pool.profile")

    return cfg


USER_PANEL_COMMAND_KEYS = (
    "gift_vip", "player_stats", "punish_me", "remove_player_from_squad", "switch_me",
    "unlink_me", "vip_management", "vip_status", "who_killed_me", "whom_i_killed",
)


def migrate_v2_to_v3(cfg: dict) -> dict:
    """
    v2 → v3:
    - user_menu renamed to user_panel (matches admin_panel naming)
    - discord_commands merged into user_panel.commands — all of its commands only ever run
      through the user panel, so they belong under the same node, grouped in their own
      sub-node rather than as loose siblings of user_panel's own settings (channel_id,
      enabled, groups, ...). Its own "enabled" flag is dropped: user_panel.enabled is now
      the single switch for both the panel and whether its command cogs load — each
      individual command still has its own "enabled" for per-command granularity.
    - comfort_functions moved into admin_panel.comfort_functions (broadcast_message is
      surfaced in the admin panel UI; after_game_message/auto_unban just travel along with
      it, unchanged, as their own independent "enabled" switch).
    - register_player moved into admin_panel.register_player, unchanged, own "enabled".
    - map_rotation_vote: new section for the automated map-rotation vote feature.
    """
    for server in cfg.get("rcon", []):
        # user_menu/discord_commands → user_panel (+ nested commands sub-node)
        if "user_menu" in server:
            server["user_panel"] = server.pop("user_menu")
            logger.info("Migration v2→v3: renamed user_menu to user_panel")

        if "user_panel" not in server:
            server["user_panel"] = [{"channel_id": 0, "enabled": False}]
            logger.info("Migration v2→v3: added user_panel")

        user_panel = server["user_panel"][0]
        user_panel.pop("commands_enabled", None)

        commands_list = server.pop("discord_commands", None)
        commands_source = commands_list[0] if commands_list else {}

        # Already-flat user_panel (from an earlier, uncommitted v3 shape) — regroup in place.
        commands_source.update({
            key: user_panel.pop(key) for key in USER_PANEL_COMMAND_KEYS if key in user_panel
        })

        commands_source.pop("enabled", None)
        for shared_key in ("admin_always", "dryrun", "groups"):
            if shared_key in commands_source:
                user_panel.setdefault(shared_key, commands_source.pop(shared_key))

        if commands_source:
            target = (user_panel.get("commands") or [{}])[0]
            for key, value in commands_source.items():
                target.setdefault(key, value)
            user_panel["commands"] = [target]
            logger.info("Migration v2→v3: merged discord_commands into user_panel.commands")

        # comfort_functions → admin_panel.comfort_functions (kept as its own, independent
        # sub-node — its "enabled" flag stays distinct from admin_panel's own, since
        # after_game_message/auto_unban run automatically in the background regardless of
        # whether the admin panel UI itself is enabled)
        comfort_list = server.pop("comfort_functions", None)
        if comfort_list:
            if "admin_panel" not in server:
                server["admin_panel"] = [{"channel_id": 0, "enabled": False}]
                logger.info("Migration v2→v3: added admin_panel")
            admin_panel = server["admin_panel"][0]
            admin_panel.setdefault("comfort_functions", comfort_list)
            logger.info("Migration v2→v3: moved comfort_functions into admin_panel")

        # register_player → admin_panel.register_player
        register_player_list = server.pop("register_player", None)
        if register_player_list:
            if "admin_panel" not in server:
                server["admin_panel"] = [{"channel_id": 0, "enabled": False}]
                logger.info("Migration v2→v3: added admin_panel")
            admin_panel = server["admin_panel"][0]
            admin_panel.setdefault("register_player", register_player_list)
            logger.info("Migration v2→v3: moved register_player into admin_panel")

        # map_rotation_vote: new section
        if "map_rotation_vote" not in server:
            server["map_rotation_vote"] = [{
                "enabled": False,
                "dryrun": False,
                "vote_channel_id": 0,
                "duration_days": 7,
                "duration_hours": 0,
                "top_maps_to_set": 10,
                "reminder_interval_hours": 24,
                "max_reminders_per_game": 1,
                "stealth_vote": False,
                "maps_per_poll": 10,
                "map_pool": [{
                    "dusk": 0,
                    "overcast": 0,
                    "night": 0,
                    "battle_mode": [],
                    "enforced_maps": [],
                    "blacklist_maps": []
                }]
            }]
            logger.info("Migration v2→v3: added map_rotation_vote")

    return cfg


# ─── Registry ─────────────────────────────────────────────────────────────────

MIGRATIONS: dict = {
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
}


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_migrations(cfg: dict, config_path: str = "config.json") -> dict:
    version = cfg.get("config_version", 1)

    if version >= CURRENT_VERSION:
        logger.info(f"Config is up to date (v{version})")
        return cfg

    shutil.copy(config_path, f"{config_path}.v{version}.bak")
    logger.info(f"Config backup created: {config_path}.v{version}.bak")

    for v in range(version, CURRENT_VERSION):
        migrate_fn = MIGRATIONS.get(v)
        if migrate_fn:
            cfg = migrate_fn(cfg)
            cfg["config_version"] = v + 1
            logger.info(f"Config migrated: v{v} → v{v + 1}")
        else:
            logger.warning(f"No migration found for v{v} → v{v + 1}, skipping")

    return cfg
