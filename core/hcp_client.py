import boto3
import json
import logging
from botocore.exceptions import NoCredentialsError, ClientError

# Configure module-level logger
logger = logging.getLogger(__name__)

class HCPClient:
    """ Handles AWS S3/HCP interactions including authentication and file operations. """
    
    def __init__(self):
        self.s3_client = None
        self.connected = False
        self.tenant_address = ""

    def connect(self, credentials_path):
        """ Parses credentials file and initializes the boto3 client. """
        try:
            with open(credentials_path, 'r') as f:
                creds = json.load(f)

            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=creds.get('access_key'),
                aws_secret_access_key=creds.get('secret_key'),
                endpoint_url=creds.get('endpoint_url'),
                verify=creds.get('verify_ssl', True)
            )
            
            # Extract tenant for UI display
            endpoint = creds.get('endpoint_url', '')
            self.tenant_address = endpoint.split('//')[-1].split('.')[0] if '//' in endpoint else endpoint
            
            # Simple connection test
            self.s3_client.list_buckets()
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    def list_buckets(self):
        """ Returns a list of available bucket names. """
        if not self.s3_client: return []
        try:
            response = self.s3_client.list_buckets()
            return [b['Name'] for b in response.get('Buckets', [])]
        except ClientError as e:
            logger.error(f"Failed to list buckets: {e}")
            return []

    def fetch_files(self, bucket_name):
        """ 
        Lists all objects in a bucket. 
        Returns list of tuples: (name, size_str, type, last_modified, key, size_bytes) 
        """
        if not self.s3_client: return []
        
        file_list = []
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        size_bytes = obj.get('Size', 0)
                        last_mod = obj['LastModified'].strftime("%Y-%m-%d %H:%M")
                        
                        # Basic type inference
                        ftype = key.split('.')[-1].upper() if '.' in key else "FILE"
                        
                        # Formatting handled by UI, but we provide raw data
                        size_str = f"{size_bytes} B" 
                        
                        file_list.append((key.split('/')[-1], size_str, ftype, last_mod, key, size_bytes))
                        
            return file_list
        except Exception as e:
            logger.error(f"Error fetching files: {e}")
            return []

    def get_existing_folders(self, bucket_name):
        """ Scans bucket for virtual folders (prefixes). """
        if not self.s3_client: return []
        folders = set()
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if '/' in key:
                            # Extract directory path
                            folder = os.path.dirname(key)
                            folders.add(folder)
            return sorted(list(folders))
        except Exception:
            return []

    def upload_file(self, bucket_name, local_path, remote_folder=""):
        """ Uploads a single file to the specified bucket and folder. """
        if not self.s3_client: return False
        try:
            filename = os.path.basename(local_path)
            # Construct key
            key = f"{remote_folder}/{filename}" if remote_folder else filename
            # Remove leading slashes to prevent S3 issues
            if key.startswith("/"): key = key[1:]
            
            self.s3_client.upload_file(local_path, bucket_name, key)
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def download_object(self, bucket_name, file_key, destination_folder, flatten=False, callback=None):
        """ Downloads an object. Supports callbacks for progress bars. """
        if not self.s3_client: return False
        try:
            import os
            
            if flatten:
                filename = os.path.basename(file_key)
                local_path = os.path.join(destination_folder, filename)
            else:
                safe_key = file_key.replace('/', os.sep)
                local_path = os.path.join(destination_folder, safe_key)

            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.s3_client.download_file(
                Bucket=bucket_name, 
                Key=file_key, 
                Filename=local_path,
                Callback=callback
            )
            return True
        except Exception as e:
            logger.error(f"Download failed for {file_key}: {e}")
            return False