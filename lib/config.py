import logging
import json
import copy
from typing import Any, Dict, Union

# get Logger for this modul
logger = logging.getLogger(__name__)


def _is_simple_value(v: Any) -> bool:
    """Check if value is a simple scalar (not dict/list)."""
    return not isinstance(v, (dict, list))


def _sort_config_keys(obj: Any) -> Any:
    """Recursively sort config: simple values first, then complex structures alphabetically."""
    if isinstance(obj, dict):
        # Separate simple and complex values
        simple_items = [(k, v) for k, v in obj.items() if _is_simple_value(v)]
        complex_items = [(k, v) for k, v in obj.items() if not _is_simple_value(v)]

        # Sort each group: simple by key (unchanged), complex alphabetically
        simple_items.sort(key=lambda x: x[0])  # Preserve order for simple values
        complex_items.sort(key=lambda x: x[0])  # Alphabetical for complex

        # Merge: simple first, then complex
        sorted_dict = {}
        for k, v in simple_items + complex_items:
            sorted_dict[k] = _sort_config_keys(v)

        return sorted_dict
    elif isinstance(obj, list):
        return [_sort_config_keys(item) for item in obj]
    else:
        return obj

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
        sorted_data = _sort_config_keys(cls._config_data)
        with open(filename, 'w') as file:
            json.dump(sorted_data, file, indent=4)

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
    def get_node(cls, *keys: Union[str, int], default: Any = None) -> Any:
        # Retrieve a whole subtree (dict or list) from the configuration.
        
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