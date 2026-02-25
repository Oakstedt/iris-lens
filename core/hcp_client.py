import os
import json
import logging
from NGPIris.hcp import HCPHandler
import inspect

logger = logging.getLogger(__name__)

class HCPClient:
    """
    Manages connections and file operations for HCP/S3 storage.
    Includes 'Smart Mount' to prevent 503 errors during batch operations.
    """
    def __init__(self, credentials_path="credentials.json"):
        self.handler = None
        self.connected = False
        self.credentials_path = credentials_path
        self.tenant_address = "None"
        self._mounted_bucket = None 

    def connect(self, credentials_path):
        """Authenticates using the provided credentials file."""
        if not os.path.exists(credentials_path):
            return False

        try:
            self.credentials_path = credentials_path
            self.handler = HCPHandler(credentials_path)
            # Extract Address (Visual Only)
            try:
                with open(credentials_path, 'r') as f:
                    data = json.load(f)
                    if 'hcp' in data and 'endpoint' in data['hcp']:
                        self.tenant_address = data['hcp']['endpoint']
                    else:
                        self.tenant_address = data.get('endpoint', data.get('s3_endpoint_url', "Unknown"))
            except:
                self.tenant_address = "Unknown"

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            return False

    def _ensure_mount(self, bucket_name):
        """Helper: Only mount if we haven't already. Prevents 503s."""
        if self._mounted_bucket == bucket_name:
            return True
        
        try:
            self.handler.mount_bucket(bucket_name)
            self._mounted_bucket = bucket_name
            return True
        except Exception as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            return False

    def list_buckets(self):
        if not self.handler: return []
        try:
            return self.handler.list_buckets()
        except Exception as e:
            print(f"Error calling handler.list_buckets(): {e}")
            return []

    def fetch_files(self, bucket_name):
        if not self.handler: return []
        try:
            self._ensure_mount(bucket_name)
            
            s3 = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3: return []

            files = []
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)

            for page in page_iterator:
                if 'Contents' not in page: continue
                    
                for obj in page['Contents']:
                    raw_key = obj.get('Key', 'Unknown')
                    if raw_key.endswith('/') or "Zone.Identifier" in raw_key: continue

                    raw_size = obj.get('Size', 0)
                    if raw_size > 1048576: s_str = f"{raw_size/1048576:.2f} MB"
                    elif raw_size > 1024: s_str = f"{raw_size/1024:.2f} KB"
                    else: s_str = f"{raw_size} B"
                    
                    ftype = raw_key.split('.')[-1].upper() if '.' in raw_key else "File"
                    date = obj.get('LastModified', '')
                    files.append((raw_key, s_str, ftype, str(date), raw_key, raw_size))

            return files
        except Exception as e:
            print(f"Fetch error: {e}")
            return []

    def download_object(self, bucket_name, file_key, destination_folder, flatten=False, callback=None):
        if not self.handler: return False

        try:
            # 1. Determine local path
            # [FIX 1] Strip leading slashes so Linux doesn't treat it as a root absolute path
            clean_file_key = file_key.lstrip('/')
            
            if flatten:
                filename = os.path.basename(clean_file_key)
                full_local_path = os.path.join(destination_folder, filename)
            else:
                safe_key = clean_file_key.replace('/', os.sep)
                full_local_path = os.path.join(destination_folder, safe_key)

            full_local_path = os.path.normpath(full_local_path)
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)
            
            # 2. Smart Mount (Prevents 503)
            self._ensure_mount(bucket_name)
            
            # 3. Download
            s3 = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if s3:
                # [FIX 2] Import TransferConfig and disable threads to prevent HCP 503 errors
                from boto3.s3.transfer import TransferConfig
                config = TransferConfig(use_threads=False)
                
                s3.download_file(
                    Bucket=bucket_name, 
                    Key=file_key, # Keep original key for the remote fetch
                    Filename=full_local_path, 
                    Callback=callback,
                    Config=config
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Download failed for {file_key}: {e}")
            return False

    def upload_file(self, bucket_name, local_file_path, object_key, callback=None):
        """
        Uploads a file.
        Now uses s3.upload_file to support the callback progress bar.
        Arguments:
            bucket_name: The target bucket
            local_file_path: The absolute path to the local file
            object_key: The full destination path (folder + filename) in the bucket
            callback: Optional function for progress tracking
        """
        try:
            if not self.handler: return False
            self._ensure_mount(bucket_name)
            
            s3_client = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3_client: return False

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

    def get_existing_folders(self, bucket_name):
        if not self.handler: return []
        try:
            self._ensure_mount(bucket_name)
            folders = set()
            
            items = []
            if hasattr(self.handler, 'list_objects'):
                items = self.handler.list_objects()

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