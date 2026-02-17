import os
from .config_manager import ConfigManager
from .hcp_client import HCPClient

class SessionManager:
    """
    The Brain 🧠
    Handles the connection state, credentials, and raw data fetching.
    The UI should talk to THIS, not directly to HCPClient.
    """
    def __init__(self):
        self.config = ConfigManager()
        self.client = HCPClient()

    def has_credentials(self) -> bool:
        """ Checks if we have a path saved in config. """
        return self.config.has_credentials()

    def connect_from_saved(self) -> bool:
        """ Attempts to connect using the saved credential path. """
        path = self.config.get("credentials_path")
        if not path:
            return False
        return self.client.connect(path)

    def link_new_credentials(self, path: str) -> bool:
        """ Saves a new path and attempts to connect immediately. """
        self.config.set("credentials_path", path)
        return self.client.connect(path)

    def get_tenant_label(self) -> str:
        """ Returns a formatted string for the UI label. """
        if not self.client.connected:
            return "Connected to Tenant: None"
        
        t_addr = getattr(self.client, 'tenant_address', "Unknown")
        return f"Connected to Tenant: {t_addr}"

    def is_secure_tenant(self) -> bool:
        """ Returns True if the tenant is using HTTPS (for styling). """
        t_addr = getattr(self.client, 'tenant_address', "")
        return "http" in str(t_addr)

    def get_bucket_list(self):
        """ Wraps the client list_buckets method. """
        if not self.client.connected:
            return []
        return self.client.list_buckets()

    # --- Pass-through methods ---
    # Sometimes we just need to let the UI access the muscle directly
    # until we refactor further.
    def fetch_files(self, bucket):
        return self.client.fetch_files(bucket)

    def upload_file(self, bucket, local_path, remote_folder):
        return self.client.upload_file(bucket, local_path, remote_folder)
        
    def get_client(self):
        """ Escape hatch for workers that need the raw client object """
        return self.client