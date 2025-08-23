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
    def load_Config(cls, filename: str = "config.json", reload: bool = False):
        # Load configuration from JSON file.
        if reload or not cls._config_data:
            with open(filename, 'r') as file:
                cls._config_data = json.load(file)

    @classmethod
    def save_Config(cls, filename: str = "config.json",):
        with open(filename, 'w') as file:
            json.dump(cls._config_data, file, indent=4)

    @classmethod
    def get(cls, *keys: Union[str, int], default: Any = None) -> Any:
        # Retrieve a nested configuration value using keys.
        if not cls._config_data:
            raise ValueError("Configuration has not been loaded. Call 'load_Config()' first.")

        value = cls._config_data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif isinstance(value, list) and isinstance(key, int) and key < len(value):
                value = value[key]
            else:
                return default
        return copy.deepcopy(value)
    
    @classmethod
    def set(cls, *keys_and_value: Union[str, int, Any]) -> None:
        """
        Set a nested configuration value.
        The last argument is treated as the value, the rest are keys/indices.
        """
        if not cls._config_data:
            raise ValueError("Configuration has not been loaded. Call 'load_Config()' first.")
        if len(keys_and_value) < 2:
            raise ValueError("Need at least one key and a value")

        *keys, value = keys_and_value
        target = cls._config_data
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                # last key -> assign value
                if isinstance(target, dict):
                    target[key] = value
                elif isinstance(target, list) and isinstance(key, int):
                    if key < len(target):
                        target[key] = value
                    else:
                        raise IndexError(f"List index {key} out of range for set()")
                else:
                    raise TypeError(f"Unsupported type {type(target)} for key {key}")
            else:
                # traverse deeper
                if isinstance(target, dict):
                    if key not in target or not isinstance(target[key], (dict, list)):
                        target[key] = {}
                    target = target[key]
                elif isinstance(target, list) and isinstance(key, int):
                    if key < len(target):
                        target = target[key]
                    else:
                        raise IndexError(f"List index {key} out of range for set()")
                else:
                    raise TypeError(f"Unsupported type {type(target)} for key {key}")