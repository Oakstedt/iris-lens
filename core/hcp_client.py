import os
import json
import logging
from typing import List, Tuple, Optional, Callable, Any

from NGPIris.hcp import HCPHandler

logger = logging.getLogger(__name__)

class HCPClient:
    """
    Manages connections and file operations for HCP/S3 storage.
    
    Acts as a robust wrapper around the NGPIris HCPHandler, providing stable 
    file transfers, pagination, and a 'Smart Mount' system to prevent 
    server-side 503 errors during high-volume batch operations.
    """
    
    def __init__(self, credentials_path: str = "credentials.json") -> None:
        """Initializes the HCP Client with a default credentials path."""
        self.handler: Optional[Any] = None
        self.connected: bool = False
        self.credentials_path: str = credentials_path
        self.tenant_address: str = "None"
        self._mounted_bucket: Optional[str] = None 

    def connect(self, credentials_path: str) -> bool:
        """
        Authenticates the session using the provided JSON credentials file.
        
        Args:
            credentials_path: The absolute or relative path to the credentials file.
            
        Returns:
            True if the connection was established successfully, False otherwise.
        """
        if not os.path.exists(credentials_path):
            return False

        try:
            self.credentials_path = credentials_path
            self.handler = HCPHandler(credentials_path)
            self.connected = True
            self._mounted_bucket = None  # Reset mount state on new connection
            
            # Extract Address (Visual Only)
            try:
                with open(credentials_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'hcp' in data and 'endpoint' in data['hcp']:
                        self.tenant_address = data['hcp']['endpoint']
                    else:
                        self.tenant_address = data.get('endpoint', data.get('s3_endpoint_url', "Unknown"))
            except Exception:
                self.tenant_address = "Unknown"

            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            return False

    def _ensure_mount(self, bucket_name: str) -> bool:
        """
        Helper: Mounts the target bucket only if it is not currently mounted.
        
        Repeatedly mounting the same bucket in HCP can trigger 503 Slow Down 
        errors. This tracks state to ensure mount operations are minimal.
        
        Args:
            bucket_name: The target HCP bucket name.
            
        Returns:
            True if mounted successfully or already mounted, False on error.
        """
        if self._mounted_bucket == bucket_name:
            return True
        
        try:
            self.handler.mount_bucket(bucket_name)
            self._mounted_bucket = bucket_name
            return True
        except Exception as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            return False

    def list_buckets(self) -> List[str]:
        """Retrieves a list of all buckets available to the current credentials."""
        if not self.handler: 
            return []
            
        try:
            return self.handler.list_buckets()
        except Exception as e:
            print(f"Error calling handler.list_buckets(): {e}")
            return []

    def fetch_files(self, bucket_name: str) -> List[Tuple[str, str, str, str, str, int]]:
        """
        Retrieves and formats a complete file hierarchy for the target bucket.
        
        Utilizes boto3's paginator to safely fetch large datasets without 
        timeout or memory overflow. Allows 0-byte folder markers through for 
        accurate UI representation and deletion.
        """
        if not self.handler: 
            return []
            
        try:
            self._ensure_mount(bucket_name)
            
            s3 = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3: 
                return []

            files = []
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)

            for page in page_iterator:
                if 'Contents' not in page: 
                    continue
                    
                for obj in page['Contents']:
                    raw_key = obj.get('Key', 'Unknown')
                    
                    # Only filter out system metadata files, let folder markers through
                    if "Zone.Identifier" in raw_key: 
                        continue

                    raw_size = obj.get('Size', 0)
                    
                    if raw_size > 1048576: 
                        s_str = f"{raw_size/1048576:.2f} MB"
                    elif raw_size > 1024: 
                        s_str = f"{raw_size/1024:.2f} KB"
                    else: 
                        s_str = f"{raw_size} B"
                    
                    ftype = raw_key.split('.')[-1].upper() if '.' in raw_key else "File"
                    date = obj.get('LastModified', '')
                    
                    files.append((raw_key, s_str, ftype, str(date), raw_key, raw_size))

            return files
        except Exception as e:
            print(f"Fetch error: {e}")
            return []

    def download_object(self, bucket_name: str, file_key: str, destination_folder: str, flatten: bool = False, callback: Optional[Callable] = None) -> bool:
        """
        Downloads a specific file from the S3 bucket to the local machine.
        
        Args:
            bucket_name: The target bucket name.
            file_key: The strict S3 object key.
            destination_folder: The root directory to save the file.
            flatten: If True, dumps the file into the root destination folder, 
                     ignoring the native S3 folder structure.
            callback: Optional function to emit progress tracking data.
            
        Returns:
            True if the download succeeded, False otherwise.
        """
        if not self.handler: 
            return False

        try:
            # 1. Determine local path architecture
            if flatten:
                filename = os.path.basename(file_key)
                full_local_path = os.path.join(destination_folder, filename)
            else:
                safe_key = file_key.replace('/', os.sep)
                full_local_path = os.path.join(destination_folder, safe_key)

            full_local_path = os.path.normpath(full_local_path)
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)
            
            # 2. Smart Mount (Prevents 503)
            self._ensure_mount(bucket_name)
            
            # 3. Download via native boto3
            s3 = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if s3:
                s3.download_file(
                    Bucket=bucket_name, 
                    Key=file_key, 
                    Filename=full_local_path, 
                    Callback=callback
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Download failed for {file_key}: {e}")
            return False

    def upload_file(self, bucket_name: str, local_file_path: str, object_key: str, callback: Optional[Callable] = None) -> bool:
        """
        Uploads a local file to the designated HCP S3 bucket.
        
        Leverages s3_client.upload_file directly to support callback tracking 
        for smooth UI progress bars, bypassing the basic put_object method.
        
        Args:
            bucket_name: The target S3 bucket.
            local_file_path: The absolute path to the local file.
            object_key: The complete destination path (folder + filename) in the bucket.
            callback: Optional function for tracking chunk progress.
            
        Returns:
            True on success, False on failure.
        """
        try:
            if not self.handler: 
                return False
                
            self._ensure_mount(bucket_name)
            
            s3_client = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3_client: 
                return False

            # Using upload_file instead of put_object to support Callback
            s3_client.upload_file(
                Filename=local_file_path, 
                Bucket=bucket_name, 
                Key=object_key, 
                Callback=callback
            )
            
            return True
        except Exception as e:
            print(f"Upload failed: {e}")
            return False

    def get_existing_folders(self, bucket_name: str) -> List[str]:
        """
        Parses existing bucket items to dynamically generate a list of folders.
        
        Args:
            bucket_name: The S3 bucket to scan.
            
        Returns:
            A sorted list of unique folder paths.
        """
        if not self.handler: 
            return []
            
        try:
            self._ensure_mount(bucket_name)
            folders = set()
            
            items = []
            if hasattr(self.handler, 'list_objects'):
                items = self.handler.list_objects()

            # Safely parse keys whether list_objects returns dicts or attribute objects
            for obj in items:
                if isinstance(obj, dict):
                    key = obj.get('key') or obj.get('name') or obj.get('Key') or ""
                else:
                    key = getattr(obj, 'key', getattr(obj, 'name', ""))
                
                if "/" in key:
                    folder_path = key.rsplit("/", 1)[0] + "/"
                    folders.add(folder_path)
                    
            return sorted(list(folders))
        except Exception:
            return []
        
    def delete_object(self, bucket_name: str, file_key: str) -> bool:
        """
        Permanently deletes a specific object from the S3 bucket.
        
        Args:
            bucket_name: The target S3 bucket.
            file_key: The exact key of the file to delete.
            
        Returns:
            True if the deletion was successful, False otherwise.
        """
        try:
            if not self.handler: 
                return False
                
            self._ensure_mount(bucket_name)
            
            s3_client = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3_client: 
                return False

            s3_client.delete_object(Bucket=bucket_name, Key=file_key)
            return True
            
        except Exception as e:
            logger.error("Delete failed for %s: %s", file_key, e)
            return False