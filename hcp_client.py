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
            file_generator = self.handler.list_objects()
            files = []
            
            def format_size(size_val):
                try:
                    s = float(size_val)
                    if s > 1024 * 1024: return f"{s / (1024 * 1024):.2f} MB"
                    if s > 1024: return f"{s / 1024:.2f} KB"
                    return f"{int(s)} B"
                except (ValueError, TypeError):
                    return "0 B"

            for i, obj in enumerate(file_generator):
                # 1. Capture the Raw Key (The Source of Truth)
                raw_key = obj.get('key') or obj.get('name') or obj.get('Key') or "Unknown"
                
                # 2. Prepare Display Data
                # (You can use os.path.basename(raw_key) here if you only want to see filenames in the table)
                display_name = raw_key 
                
                raw_size = obj.get('size') or obj.get('Size') or 0
                size = format_size(raw_size)
                ftype = display_name.split('.')[-1].upper() if '.' in display_name else "File"
                date = obj.get('last_modified') or obj.get('LastModified') or str(obj.get('ingest_time', ''))
                
                # 3. Append TUPLE with 5 items: (Name, Size, Type, Date, RAW_KEY)
                files.append((display_name, size, ftype, str(date), raw_key))

            print(f"✅ Found {len(files)} objects.")
            return files
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return []

    def download_object(self, bucket_name, file_key, destination_folder):
        """ 
        Downloads a single object by spinning up a FRESH handler instance.
        Matches the user's working script EXACTLY (arguments and behavior).
        """
        if not self.credentials_path:
            print("❌ No credentials path saved. Cannot start fresh connection.")
            return False

        try:
            # 0. Sanitize Inputs (Remove accidental whitespace)
            bucket_name = str(bucket_name).strip()
            file_key = str(file_key).strip()

            print(f"🔧 DEBUG: Using Creds File: {self.credentials_path}")
            print(f"🔧 DEBUG: Mounting '{bucket_name}', Downloading '{file_key}'")

            # 1. Create a FRESH connection (Exact match to script)
            temp_handler = HCPHandler(self.credentials_path)
            
            # 2. Mount Bucket
            temp_handler.mount_bucket(bucket_name)

            # 3. Construct Local Path (Windows Safe)
            unsafe_path = os.path.join(destination_folder, file_key)
            full_local_path = os.path.normpath(unsafe_path)

            # 4. Ensure Directory Exists
            local_parent_dir = os.path.dirname(full_local_path)
            if not os.path.exists(local_parent_dir):
                os.makedirs(local_parent_dir, exist_ok=True)

            print(f"⬇ Downloading to: {full_local_path}")
            
            # 5. Execute Download
            temp_handler.download_file(file_key, full_local_path)
            
            return True

        except Exception as e:
            print(f"❌ Download failed for {file_key}: {e}")
            return False