import os
from typing import List, Tuple

from .config_manager import ConfigManager
from .hcp_client import HCPClient


class SessionManager:
    """
    Central state coordinator for the application.
    
    Acts as the primary interface between the UI controllers and the underlying 
    HCP/S3 network client, managing active connections, credential persistence, 
    and data routing. The UI should interact exclusively with this manager.
    """
    
    def __init__(self) -> None:
        """Initializes the configuration manager and the HCP client instances."""
        self.config = ConfigManager()
        self.client = HCPClient()

    def has_credentials(self) -> bool:
        """
        Checks if a credential file path is saved in the local configuration.
        
        Returns:
            True if a path exists, False otherwise.
        """
        return self.config.has_credentials()

    def connect_from_saved(self) -> bool:
        """
        Attempts to establish a connection using the persisted credential path.
        
        Returns:
            True if the connection succeeds, False if it fails or no path exists.
        """
        path = self.config.get("credentials_path")
        if not path:
            return False
            
        return self.client.connect(path)

    def link_new_credentials(self, path: str) -> bool:
        """
        Saves a new credential file path to configuration and attempts immediate connection.
        
        Args:
            path: The absolute path to the JSON credentials file.
            
        Returns:
            True if the connection succeeds, False otherwise.
        """
        self.config.set("credentials_path", path)
        return self.client.connect(path)

    def get_tenant_label(self) -> str:
        """
        Generates a formatted string for the UI tenant status label.
        
        Returns:
            A formatted string containing the tenant address or connection status.
        """
        if not self.client.connected:
            return "Connected to Tenant: None"
        
        t_addr = getattr(self.client, 'tenant_address', "Unknown")
        return f"Connected to Tenant: {t_addr}"

    def is_secure_tenant(self) -> bool:
        """
        Evaluates if the current tenant connection utilizes HTTP/HTTPS protocol.
        
        Returns:
            True if 'http' is present in the tenant address string.
        """
        t_addr = getattr(self.client, 'tenant_address', "")
        return "http" in str(t_addr)

    def get_bucket_list(self) -> List[str]:
        """
        Retrieves the list of accessible buckets from the active client.
        
        Returns:
            A list of bucket name strings, or an empty list if disconnected.
        """
        if not self.client.connected:
            return []
            
        return self.client.list_buckets()

    # --- Pass-through Methods ---

    def fetch_files(self, bucket: str) -> List[Tuple[str, str, str, str, str, int]]:
        """
        Routes a file hierarchy fetch request directly to the underlying client.
        
        Args:
            bucket: The target S3 bucket name.
            
        Returns:
            A list of file metadata tuples for UI population.
        """
        return self.client.fetch_files(bucket)

    def upload_file(self, bucket: str, local_path: str, remote_folder: str) -> bool:
        """
        Routes a basic synchronous upload request to the underlying client.
        
        Args:
            bucket: The target S3 bucket name.
            local_path: The absolute path to the local file.
            remote_folder: The destination path within the S3 bucket.
            
        Returns:
            True if the upload was successful, False otherwise.
        """
        return self.client.upload_file(bucket, local_path, remote_folder)
        
    def get_client(self) -> HCPClient:
        """
        Provides direct access to the raw HCPClient instance.
        
        Used as an escape hatch for background worker threads (QThread) that 
        require direct interaction with the network layer to prevent blocking 
        the main GUI event loop.
        
        Returns:
            The active HCPClient instance.
        """
        return self.client