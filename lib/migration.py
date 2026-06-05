import logging
import shutil

logger = logging.getLogger(__name__)

CURRENT_VERSION = 2


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


# ─── Registry ─────────────────────────────────────────────────────────────────

MIGRATIONS: dict = {
    1: migrate_v1_to_v2,
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
