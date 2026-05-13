import logging
import asyncio
import signal
import sys
import threading
from lib.config import config
from lib.migration import run_migrations
from lib.logging import setup_logger
from rcon.discord.bot import start_bot, shutdown_bot

config_name = "config.json"

setup_logger()

config.load_Config(config_name)
old_version = config._config_data.get("config_version", 1)
migrated = run_migrations(config._config_data, config_name)
if migrated.get("config_version", 1) > old_version:
    config.save_Config(config_name)
    config.load_Config(config_name, reload=True)

setup_logger(config.get("rcon", 0, "log_level"))

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True

async def main():

    logger = logging.getLogger(__name__)

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