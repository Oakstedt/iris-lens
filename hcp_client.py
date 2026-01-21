import os
import json
from NGPIris.hcp import HCPHandler

class HCPClient:
    def __init__(self, credentials_path="credentials.json"):
        self.handler = None
        self.connected = False
        self.credentials_path = credentials_path
        self.tenant_address = "None" 

    def connect(self, credentials_path):
        if not os.path.exists(credentials_path):
            return False

        try:
            self.credentials_path = credentials_path
            
            # 1. Initialize NGP-Iris Handler
            self.handler = HCPHandler(credentials_path)
            self.connected = True
            
            # 2. Extract Address (Visual Only - Does not affect connection)
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
            self.tenant_address = "Not Connected"
            return False

    def list_buckets(self):
        """ Uses the native ngp-iris handler to list buckets. """
        if not self.handler: 
            return []
        
        try:
            # DIRECT CALL: Relies on the library's implementation
            return self.handler.list_buckets()
        except Exception as e:
            print(f"Error calling handler.list_buckets(): {e}")
            return []

    def fetch_files(self, bucket_name):
        if not self.handler: return []
        try:
            self.handler.mount_bucket(bucket_name)
            
            # Use internal client for detailed metadata (Size, Date)
            s3 = getattr(self.handler, 's3_client', getattr(self.handler, 'client', None))
            if not s3: return []

            files = []
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)

            for page in page_iterator:
                if 'Contents' not in page: continue
                    
                for obj in page['Contents']:
                    raw_key = obj.get('Key', 'Unknown')
                    
                    if raw_key.endswith('/') or "Zone.Identifier" in raw_key:
                        continue

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

    def download_object(self, bucket_name, file_key, destination_folder, flatten=False):
        try:
            if flatten:
                filename = os.path.basename(file_key)
                full_local_path = os.path.join(destination_folder, filename)
            else:
                safe_key = file_key.replace('/', os.sep)
                full_local_path = os.path.join(destination_folder, safe_key)

            full_local_path = os.path.normpath(full_local_path)
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)
            
            # New handler instance for thread safety
            temp_handler = HCPHandler(self.credentials_path)
            temp_handler.mount_bucket(bucket_name)
            temp_handler.download_file(file_key, full_local_path, show_progress_bar=False) 
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def upload_file(self, bucket_name, local_file_path, remote_folder=""):
        try:
            remote_folder = str(remote_folder).strip().replace("\\", "/")
            if remote_folder.startswith("/"): remote_folder = remote_folder.lstrip("/")
            if remote_folder and not remote_folder.endswith('/'): remote_folder += '/'
            if remote_folder == "/": remote_folder = ""

            filename = os.path.basename(local_file_path)
            object_key = f"{remote_folder}{filename}"

            temp_handler = HCPHandler(self.credentials_path)
            temp_handler.mount_bucket(bucket_name)
            
            s3_client = getattr(temp_handler, 's3_client', getattr(temp_handler, 'client', None))
            if not s3_client: return False

            with open(local_file_path, 'rb') as data:
                s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            
            return True
        except Exception as e:
            print(f"Upload failed: {e}")
            return False

    def get_existing_folders(self, bucket_name):
        if not self.handler: return []
        try:
            self.handler.mount_bucket(bucket_name)
            folders = set()
            
            # Using handler's list_objects if available
            items = []
            if hasattr(self.handler, 'list_objects'):
                items = self.handler.list_objects()

            for obj in items:
                # Handle dict or object
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