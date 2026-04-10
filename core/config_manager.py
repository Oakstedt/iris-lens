import os
import json
from typing import Any, Dict, Optional


class ConfigManager:
    """
    Manages persistent application settings.
    
    Handles loading, saving, and retrieving configuration states (like linked 
    credentials and last accessed buckets) via a local JSON file.
    """
    
    FILE_PATH: str = "config.json"

    def __init__(self) -> None:
        """Initializes the configuration manager and loads existing settings."""
        self._config: Dict[str, Optional[str]] = {
            "credentials_path": None,
            "last_bucket": None
        }
        self.load()

    def load(self) -> None:
        """
        Reads the configuration from disk into memory.
        
        Fails safely (with a console print) if the file is corrupted or unreadable, 
        retaining the default internal configuration state.
        """
        if os.path.exists(self.FILE_PATH):
            try:
                # Explicit utf-8 encoding prevents Windows default encoding issues
                with open(self.FILE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._config.update(data)
            except Exception as e:
                print(f"Config load error: {e}")

    def save(self) -> None:
        """
        Writes the current internal configuration state to disk.
        
        Serializes the dictionary into a cleanly indented JSON file.
        """
        try:
            with open(self.FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key: str) -> Any:
        """
        Retrieves a configuration value by its key.
        
        Args:
            key: The configuration setting dictionary key.
            
        Returns:
            The associated value, or None if the key does not exist.
        """
        return self._config.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Updates a configuration value and immediately persists the change to disk.
        
        Args:
            key: The configuration setting to update.
            value: The new value to store.
        """
        self._config[key] = value
        self.save()
    
    def has_credentials(self) -> bool:
        """
        Checks if a valid credentials file path has been linked.
        
        Returns:
            True if a credentials path string exists, False otherwise.
        """
        return bool(self._config.get("credentials_path"))