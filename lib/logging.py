import logging
from logging.handlers import TimedRotatingFileHandler

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[1m\033[94m',   # dark gray / DEBUG
        'INFO': '\033[1m\033[92m',    # green / INFO
        'WARNING': '\033[1m\033[93m', # yellow / WARNING
        'ERROR': '\033[1m\033[91m',   # redt / ERROR
        'CRITICAL': '\033[1m\033[95m' # magenta / CRITICAL
    }
    
    DATE_COLOR = '\033[1m\033[90m'  # dark gray / date time
    MODULE_COLOR = '\033[35m'  # dunkel magenta / module
    LINE_COLOR = '\033[1m\033[90m'  # dark gray / line number
    MESSAGE_COLOR = '\033[0m'  # default / message
    RESET = '\033[0m'  # reset colot

    MAX_LEVEL_LENGTH = len("CRITICAL")

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        date_str = self.formatTime(record, self.datefmt)
        module_name = record.name
        lineno = record.lineno

        level_length = len(record.levelname)
        padding = " " * (self.MAX_LEVEL_LENGTH - level_length)
        
        formatted_message = (
            f"{self.DATE_COLOR}{date_str}{self.RESET} "
            f"{log_color}{record.levelname}{self.RESET}{padding} "
            f"{self.MODULE_COLOR}{module_name}{self.RESET} "
            f"{self.MESSAGE_COLOR}{record.getMessage()}{self.RESET} "
            f"{self.LINE_COLOR}(Line: {lineno}){self.RESET}"
        )
        return formatted_message
    
def setup_logger(log_level=logging.INFO):
    # define formatter
    formatter = ColoredFormatter(
        '%(asctime)s %(levelname)s %(name)s  %(message)s %(lineno)d',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.propagate = False

    # add stream handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s  %(message)s (Line: %(lineno)d)')
    
    file_handler = TimedRotatingFileHandler("HLL_Discord_Helper.log", when="midnight", interval=1, backupCount=7)
    file_handler.setFormatter(formatter)

    # avoid duplicate handler
    if not logger.hasHandlers():
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

def remove_duplicate_handlers():
    # check logger for duplicates
    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        
        if logger.hasHandlers():
            logger.info (logger_name + " has a handler")
            logger.handlers.clear()
