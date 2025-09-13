import logging
import asyncio
from hllrcon import Rcon
from lib.config import config

# get Logger for this modul
logger = logging.getLogger(__name__)

class RconV2:
    _rcon = None

    @classmethod
    async def  Connect(cls):
        try:
            cls._rcon = Rcon(host=config.get("rcon", 0, "gameserver", 0, "host"), 
                             port=config.get("rcon", 0, "gameserver", 0, "port"), 
                             password=config.get("rcon", 0, "gameserver", 0, "password"))
            logger.info(f"Connected to RCON server {config.get('rcon', 0, 'gameserver', 0, 'host')}:{config.get('rcon', 0, 'gameserver', 0, 'port')}")

            #await rcon.broadcast("Hello, HLL!")
            #await rcon.change_map(Layer.STALINGRAD_WARFARE_DAY)
            #players = await rcon.get_players()

            #rcon.disconnect()

            #await rcon.broadcast("Hello, HLL!")

            #cls._rcon.remove_player_from_squad ("75712ffe5094adfb3d45fa9d9b6a3040", "Test")

        except Exception as e:   
            logger.error(f"Failed to connect to RCON server: {e}")
            cls._rcon = None

        return cls._rcon
    
    @classmethod
    async def get(cls):
        """Gibt die Rcon-Instanz zurück (falls verbunden)."""
        if cls._rcon is None:
            logger.warning("RCON not connected. Call Connect() first.")
        return cls._rcon