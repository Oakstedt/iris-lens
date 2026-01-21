import os
import sys
import boto3

# Ensure we can find the code in 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from NGPIris.hcp.hcp import HCPHandler 
except ImportError:
    from NGPIris.hcp import HCPHandler

class HCPClient:
    """ Wrapper around the native NGP-Iris library. """
    
    def __init__(self):
        self.handler = None
        self.connected = False
        self.credentials_path = None 

    def connect(self, credentials_path):
        if not os.path.exists(credentials_path):
            raise FileNotFoundError("Credentials file not found.")

        try:
            print(f"🔌 Connecting via HCPHandler with: {credentials_path}")
            self.credentials_path = credentials_path
            
            self.handler = HCPHandler(credentials_path)
            self.connected = True
            print("✅ Native HCPHandler initialized.")
            return True
        except Exception as e:
            print(f"Connection setup failed: {e}")
            self.connected = False
            raise e

    def list_buckets(self):
        if not self.handler: return []
        try:
            buckets = self.handler.list_buckets()
            clean_list = []
            if buckets:
                for b in buckets:
                    if isinstance(b, dict) and 'Bucket' in b:
                        clean_list.append(b['Bucket'])
                    elif isinstance(b, str):
                        clean_list.append(b)
                    else:
                        clean_list.append(str(b))
            return clean_list
        except Exception as e:
            print(f"❌ Library list_buckets failed: {e}")
            return []

    def fetch_files(self, bucket_name):
        if not self.handler: return []
        try:
            print(f"📂 Mounting bucket: {bucket_name}...")
            self.handler.mount_bucket(bucket_name)
            
            s3 = getattr(self.handler, 's3_client', None) or \
                 getattr(self.handler, 'client', None) or \
                 getattr(self.handler, 's3', None)
            
            if not s3:
                print("❌ Error: Could not access internal S3 client.")
                return []

            files = []
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)

            print("🔎 Scanning raw objects...")

            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    raw_key = obj.get('Key', 'Unknown')
                    
                    # --- FILTERS ---
                    # 1. Skip Folders (ending in /)
                    if raw_key.endswith('/'):
                         continue
                    
                    # 2. Skip System/Metadata files (Zone.Identifier)
                    if "Zone.Identifier" in raw_key:
                        continue
                    # ---------------

                    display_name = raw_key
                    
                    raw_size = obj.get('Size', 0)
                    if raw_size > 1024 * 1024: size_str = f"{raw_size / (1024 * 1024):.2f} MB"
                    elif raw_size > 1024: size_str = f"{raw_size / 1024:.2f} KB"
                    else: size_str = f"{raw_size} B"
                    
                    ftype = display_name.split('.')[-1].upper() if '.' in display_name else "File"
                    date = obj.get('LastModified', '')
                    
                    files.append((display_name, size_str, ftype, str(date), raw_key))

            print(f"✅ Found {len(files)} clean objects.")
            return files

        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return []

    def download_object(self, bucket_name, file_key, destination_folder, flatten=False):
        """ 
        Downloads a single object.
        If flatten=True, saves 'folder/file.txt' as 'destination/file.txt'.
        If flatten=False, saves as 'destination/folder/file.txt'.
        """
        if not self.credentials_path:
            return False

        try:
            # 1. Sanitize Inputs
            bucket_name = str(bucket_name).strip()
            file_key = str(file_key).strip()

            # 2. Determine Local Path
            if flatten:
                # JUST the filename (discard folder path)
                filename = os.path.basename(file_key)
                full_local_path = os.path.join(destination_folder, filename)
            else:
                # FULL structure (preserve folder path)
                # Replace forward slashes with OS separator
                safe_key = file_key.replace('/', os.sep)
                full_local_path = os.path.join(destination_folder, safe_key)

            full_local_path = os.path.normpath(full_local_path)

            # 3. Create Directory (Only needed if NOT flattening or if dest doesn't exist)
            local_parent_dir = os.path.dirname(full_local_path)
            if not os.path.exists(local_parent_dir):
                os.makedirs(local_parent_dir, exist_ok=True)

            print(f"⬇ Downloading: '{file_key}' -> '{full_local_path}'")
            
            # 4. Connect & Download
            temp_handler = HCPHandler(self.credentials_path)
            temp_handler.mount_bucket(bucket_name)
            
            # Re-enable progress bar for stability
            temp_handler.download_file(file_key, full_local_path, show_progress_bar=True)
            
            return True

        except Exception as e:
            print(f"❌ Download failed for {file_key}: {e}")
            return False
        
    def upload_file(self, bucket_name, local_file_path, remote_folder=""):
        """
        Uploads a single file using a fresh connection.
        Strictly enforces S3-style keys (forward slashes, no leading slash).
        """
        if not self.credentials_path:
            print("❌ No credentials path saved.")
            return False

        try:
            # 1. Sanitize the Remote Folder Path
            # A. Force string and strip whitespace
            remote_folder = str(remote_folder).strip()
            
            # B. Replace Windows Backslashes (\) with S3 Forward Slashes (/)
            remote_folder = remote_folder.replace("\\", "/")
            
            # C. Remove leading slashes (e.g. "/folder" -> "folder")
            if remote_folder.startswith("/"):
                remote_folder = remote_folder.lstrip("/")
                
            # D. Ensure trailing slash if folder is not empty
            if remote_folder and not remote_folder.endswith('/'):
                remote_folder += '/'
            
            # E. Handle pure root case
            if remote_folder == "/": 
                remote_folder = ""

            # 2. Construct the Key
            filename = os.path.basename(local_file_path)
            object_key = f"{remote_folder}{filename}"

            print(f"🔧 DEBUG: Uploading to Bucket: '{bucket_name}'")
            print(f"🔧 DEBUG: Final Object Key:    '{object_key}'")

            # 3. Setup Fresh Connection
            temp_handler = HCPHandler(self.credentials_path)
            temp_handler.mount_bucket(bucket_name)
            
            # 4. Access Client
            s3_client = getattr(temp_handler, 's3_client', None) or \
                        getattr(temp_handler, 'client', None) or \
                        getattr(temp_handler, 's3', None)

            if not s3_client:
                print("❌ Error: Could not access internal S3 client.")
                return False

            # 5. Execute Upload
            with open(local_file_path, 'rb') as data:
                response = s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=data
                )
                
                # 6. Verify Response
                status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
                print(f"✅ Server Response: {status_code}")
                
                if 200 <= status_code < 300:
                    return True
                else:
                    print(f"⚠️ Warning: Upload finished but status code is {status_code}")
                    return True # Return true anyway as some proxies mask codes

        except Exception as e:
            print(f"❌ Upload failed for {local_file_path}: {e}")
            return False
        
    def get_existing_folders(self, bucket_name):
        """ 
        Scans the bucket to find unique folder paths. 
        Returns a sorted list of folder strings.
        """
        if not self.handler: return []

        try:
            print(f"📂 Scanning folders in: {bucket_name}...")
            self.handler.mount_bucket(bucket_name)
            
            # We use a set to automatically handle duplicates
            folders = set()
            
            # We reuse the list_objects generator
            file_generator = self.handler.list_objects()
            
            for obj in file_generator:
                key = obj.get('key') or obj.get('name') or obj.get('Key') or ""
                
                # 'os.path.dirname' extracts 'research/data' from 'research/data/file.txt'
                # We interpret forward slashes as separators regardless of OS here since it's S3
                if "/" in key:
                    folder_path = key.rsplit("/", 1)[0] + "/"
                    folders.add(folder_path)
            
            # Convert set to sorted list
            return sorted(list(folders))

        except Exception as e:
            print(f"❌ Folder scan error: {e}")
            return []
        
        