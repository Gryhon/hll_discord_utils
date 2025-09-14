import logging
import asyncio
import signal
import sys
import threading
from lib.config import config
from lib.configupdater import ConfigUpdater
from lib.logging import setup_logger
from lib.rconV2 import RconV2
from rcon.discord.bot import start_bot, shutdown_bot

config_name = "config.json"
template_name = "template.json"

config.load_Config (config_name)

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True

async def update_Config ():

    config_updater = ConfigUpdater(template_name, config_name)
    config_updater.update()

    if config_updater.updated_config:
        config_updater.save_Config(config_name)
        config.load_Config (config_name, True)

async def main():
    
    setup_logger(config.get("rcon", 0, "log_level"))
    
    logger = logging.getLogger(__name__)

    #await update_Config ()
    logger.warning(f"Note to myself: Update Config is disabled for now.")

    await RconV2.Connect()

    killer = GracefulKiller()
    logger.info("Program started. Press Ctrl+C to exit the program.")
  
    try:        
        start_bot ()
        
        while not killer.kill_now:
           threading.Event().wait(1)

        shutdown_bot()
    
        logger.info ("Halt")

    except Exception as e:
        logger.error(f"An unexpected error has occurred: {e}")
    
    finally:
        logger.info("All threads have been closed cleanly.")
    
    logger.info("Program is terminated.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())