# config_manager.py
import os
import json

class ConfigManager:
    """ Manages persistent application settings. """
    FILE_PATH = "config.json"

    def __init__(self):
        self._config = {
            "credentials_path": None,
            "last_bucket": None
        }
        self.load()

    def load(self):
        if os.path.exists(self.FILE_PATH):
            try:
                with open(self.FILE_PATH, 'r') as f:
                    data = json.load(f)
                    self._config.update(data)
            except Exception as e:
                print(f"Config load error: {e}")

    def save(self):
        try:
            with open(self.FILE_PATH, 'w') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key):
        return self._config.get(key)

    def set(self, key, value):
        self._config[key] = value
        self.save()
    
    def has_credentials(self):
        return bool(self._config.get("credentials_path"))