import logging
import json
import shutil
import os
from datetime import datetime

# get Logger for this modul
logger = logging.getLogger(__name__)

class ConfigUpdater:
    protected_attributes = {'probands', 'name_change_registration', 'inappropriate_name'}

    def __init__(self, template_path, production_path):
        self.template_path = template_path
        self.production_path = production_path
        self.config_changed = False  # Flag to track if changes were made
        self.updated_config = ""

    def load_Config(self, file_path):
        # Loads a JSON configuration from a file.
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        return {}    
    
    def update_Config(self, template, production_config):
        def recursive_Update(template_element, production_element):
            # If both elements are dictionaries
            if isinstance(template_element, dict) and isinstance(production_element, dict):
                # Add missing fields
                for key, value in template_element.items():
                    if key not in production_element:
                        production_element[key] = value
                        self.config_changed = True  # Mark that a change was made

                # Remove fields not in the template, except protected attributes
                keys_to_remove = [
                    key for key in production_element.keys() 
                    if key not in template_element and key not in self.protected_attributes
                ]
                for key in keys_to_remove:
                    del production_element[key]
                    self.config_changed = True  # Mark that a change was made

                # Recursively update nested dictionaries
                for key in template_element:
                    if key in production_element:
                        recursive_Update(template_element[key], production_element[key])

            # If both elements are lists
            elif isinstance(template_element, list) and isinstance(production_element, list):
                min_length = min(len(template_element), len(production_element))

                # Recursively update existing elements
                for idx in range(min_length):
                    recursive_Update(template_element[idx], production_element[idx])

                # Add missing elements from the template
                for idx in range(min_length, len(template_element)):
                    production_element.append(template_element[idx])
                    self.config_changed = True  # Mark that a change was made

            # If types mismatch, replace production_element with template_element
            elif type(template_element) != type(production_element):
                return template_element

        # Iterate over all servers in the production configuration
        for server in production_config["rcon"]:
            for template_server in template["rcon"]:
                recursive_Update(template_server, server)

        return production_config

    def create_Backup(self):
        # Creates a backup of the original `config.json` with a timestamp in the filename.
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_path = f"{self.production_path}.{timestamp}"
        shutil.copy(self.production_path, backup_path)
        logger.info(f"Backup of config.json has been created: {backup_path}")

    def save_Config(self, output_path: str):
        # Saves the synchronized `config.json` and creates a backup if necessary.
        if self.config_changed:
            self.create_Backup()  # Create a backup when changes are made.

            with open(output_path, 'w') as config_file:
                json.dump(self.updated_config, config_file, indent=4)
            logger.info(f"The {output_path} has been updated and saved.")
        else:
            logger.info("No changes to the config.json required.")

    def update(self, save_File=False):
        # Load the configurations from the files
        template = self.load_Config(self.template_path)
        production_config = self.load_Config(self.production_path)

        # If both template and production configuration are present
        if template and production_config:
            # Update the configuration
            self.updated_config = self.update_Config(template, production_config)

            # If changes were made, save the updated configuration
            if self.config_changed and save_File:
                self.save_Config(self.production_path)
                logger.info(f"The {self.production_path} has been updated and saved.")
            elif self.config_changed == False:
                logger.info("No changes to the config.json required.")
        else:
            logger.error("Error: Template or production configuration is missing.")

        return self.updated_config

