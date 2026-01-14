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
        """ 
        Attempts to list files. 
        Note: Since I don't know the exact method name in your library 
        (e.g., .list_objects() vs .ls()), I am using the s3_resource 
        that HCPHandler usually exposes, or falling back to a standard s3 call.
        """
        if not self.handler:
            return []

        try:
            # We try to access the underlying boto3 resource/client if exposed
            # This is common in these types of wrappers
            s3 = getattr(self.handler, 's3', None) or getattr(self.handler, 'client', None)
            
            # If the handler doesn't expose the client publically, we might need 
            # to check your library docs, but let's try the standard Boto3 list for now
            # utilizing the credentials the handler just loaded.
            if hasattr(self.handler, 'list_objects'):
                return self.handler.list_objects(bucket_name)

            # Fallback: We assume the handler set up the connection, 
            # so we try to grab the client to list files manually.
            # If this part fails, let me know the method name for listing files in your lib.
            if s3:
                 # Logic to format response for the UI table
                if hasattr(s3, 'list_objects_v2'):
                    response = s3.list_objects_v2(Bucket=bucket_name)
                elif hasattr(s3, 'Bucket'): # If it's a resource
                    response = s3.meta.client.list_objects_v2(Bucket=bucket_name)
                else:
                    return []

                files = []
                for obj in response.get('Contents', []):
                    name = obj['Key']
                    size = obj['Size']
                    # Simple size formatting
                    if size > 1024*1024: size_str = f"{size/(1024*1024):.2f} MB"
                    elif size > 1024: size_str = f"{size/1024:.2f} KB"
                    else: size_str = f"{size} B"
                    
                    ftype = name.split('.')[-1].upper() if '.' in name else "File"
                    date = obj['LastModified'].strftime("%Y-%m-%d %H:%M")
                    files.append((name, size_str, ftype, date))
                return files

            return []

        except Exception as e:
            print(f"Fetch error: {e}")
            return []