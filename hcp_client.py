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
    # Fallback if the folder structure varies slightly
    from NGPIris.hcp import HCPHandler

class HCPClient:
    """ minimal wrapper around the native NGP-Iris library. """
    
    def __init__(self):
        self.handler = None
        self.connected = False

    def connect(self, credentials_path):
        """ 
        Strictly mimics your working script: 
        Passes the file path string directly to the Handler. 
        """
        if not os.path.exists(credentials_path):
            raise FileNotFoundError("Credentials file not found.")

        try:
            print(f"🔌 Connecting via HCPHandler with: {credentials_path}")
            
            # THE FIX: Directly pass the path string, exactly like your snippet.
            self.handler = HCPHandler(credentials_path)
            
            self.connected = True
            print("✅ Native HCPHandler initialized.")
            return True
            
        except Exception as e:
            print(f"Connection setup failed: {e}")
            self.connected = False
            raise e

    def list_buckets(self):
        """ Wraps the native .list_buckets() method and extracts names. """
        if not self.handler:
            return []

        try:
            buckets = self.handler.list_buckets()
            clean_list = []
            
            if buckets:
                for b in buckets:
                    # Case A: The library returns a dictionary of stats (Your case)
                    if isinstance(b, dict) and 'Bucket' in b:
                        clean_list.append(b['Bucket'])
                    
                    # Case B: The library returns just a string name
                    elif isinstance(b, str):
                        clean_list.append(b)
                        
                    # Case C: Fallback safety
                    else:
                        clean_list.append(str(b))
                        
            return clean_list

        except Exception as e:
            print(f"❌ Library list_buckets failed: {e}")
            return []

    def fetch_files(self, bucket_name):
        """ Mounts the bucket and iterates through the object generator. """
        if not self.handler:
            return []

        try:
            print(f"📂 Mounting bucket: {bucket_name}...")
            # 1. Mount the bucket (Required by NGP-Iris)
            self.handler.mount_bucket(bucket_name)

            # 2. Get the generator
            file_generator = self.handler.list_objects()
            
            files = []
            
            # Helper for readable sizes
            def format_size(size_val):
                try:
                    s = float(size_val)
                    if s > 1024 * 1024: return f"{s / (1024 * 1024):.2f} MB"
                    if s > 1024: return f"{s / 1024:.2f} KB"
                    return f"{int(s)} B"
                except (ValueError, TypeError):
                    return "0 B"

            # 3. Iterate through the generator
            for i, obj in enumerate(file_generator):
                # DEBUG: Print the structure of the first item so we can see the keys
                if i == 0:
                    print(f"🔎 DEBUG - First Object Data: {obj}")

                # 4. Extract Data (guesses based on standard S3/HCP structure)
                # Adjust these keys after seeing the debug output if the table is empty!
                
                # Try common keys for filename
                name = obj.get('key') or obj.get('name') or obj.get('Key') or "Unknown"
                
                # Try common keys for size
                raw_size = obj.get('size') or obj.get('Size') or 0
                size = format_size(raw_size)
                
                # Deduce type from extension
                ftype = name.split('.')[-1].upper() if '.' in name else "File"
                
                # Try common keys for date
                date = obj.get('last_modified') or obj.get('LastModified') or str(obj.get('ingest_time', ''))
                
                files.append((name, size, ftype, str(date)))

            print(f"✅ Found {len(files)} objects.")
            return files

        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return []