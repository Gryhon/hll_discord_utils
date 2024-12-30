import logging
import json
import copy
from typing import Any, Dict, Union
from configparser import ConfigParser

# get Logger for this modul
logger = logging.getLogger(__name__)

class config:
    _config_data: Dict[str, Any] = {}

    @classmethod
    def load_config(cls, filename: str = "config.json"):
        # Load configuration from JSON file.
        if not cls._config_data:
            with open(filename, 'r') as file:
                cls._config_data = json.load(file)

    @classmethod
    def get(cls, *keys: Union[str, int], default: Any = None) -> Any:
        # Retrieve a nested configuration value using keys.
        if not cls._config_data:
            raise ValueError("Configuration has not been loaded. Call 'load()' first.")

        value = cls._config_data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif isinstance(value, list) and isinstance(key, int) and key < len(value):
                value = value[key]
            else:
                return default
        return copy.deepcopy(value)
