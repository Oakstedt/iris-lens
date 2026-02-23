import logging
import time
import os
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class DownloadWorker(QThread):
    finished = pyqtSignal(str) 
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, client, bucket, files_data, dest_folder, flatten=False):
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.files_data = files_data
        self.dest_folder = dest_folder
        self.flatten = flatten
        self._is_running = True
        
        self.total_bytes_job = sum(item[1] for item in self.files_data)
        self.bytes_transferred_so_far = 0
        self._last_emitted_percent = -1

    def run(self):
        start_time = time.time()
        logger.info(f"Starting worker. Job size: {self.total_bytes_job} bytes.")

        try:
            for key, size in self.files_data:
                if not self._is_running: break
                
                def _progress_callback(chunk_size):
                    if not self._is_running: return
                    self.bytes_transferred_so_far += chunk_size
                    
                    if self.total_bytes_job > 0:
                        current_percent = int((self.bytes_transferred_so_far / self.total_bytes_job) * 100)
                        if current_percent > self._last_emitted_percent:
                            self.progress_updated.emit(current_percent)
                            self._last_emitted_percent = current_percent

                self.client.download_object(
                    self.bucket, 
                    key, 
                    self.dest_folder, 
                    flatten=self.flatten,
                    callback=_progress_callback
                )
            
            end_time = time.time()
            elapsed_seconds = int(end_time - start_time)
            
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            self.finished.emit(duration_str)

        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False

class UploadWorker(QThread):
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, client, bucket, files_list, remote_folder):
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.files_list = files_list
        self.remote_folder = remote_folder
        self._is_running = True
        
        self.total_bytes_job = sum(os.path.getsize(f) for f in self.files_list)
        self.bytes_transferred_so_far = 0
        self._last_emitted_percent = -1

    def run(self):
        start_time = time.time()
        logger.info(f"Starting upload worker. Job size: {self.total_bytes_job} bytes.")

        try:
            for local_path in self.files_list:
                if not self._is_running: break

                filename = os.path.basename(local_path)
                
                # [FIX] Sanitize the folder path to avoid double slashes
                clean_folder = self.remote_folder.strip().replace("\\", "/")
                clean_folder = clean_folder.rstrip('/') # Remove trailing slash if present
                
                if clean_folder:
                    remote_key = f"{clean_folder}/{filename}"
                else:
                    remote_key = filename
                
                def _progress_callback(chunk_size):
                    if not self._is_running: return
                    self.bytes_transferred_so_far += chunk_size
                    
                    if self.total_bytes_job > 0:
                        current_percent = int((self.bytes_transferred_so_far / self.total_bytes_job) * 100)
                        if current_percent > self._last_emitted_percent:
                            self.progress_updated.emit(current_percent)
                            self._last_emitted_percent = current_percent

                success = self.client.upload_file(
                    self.bucket,
                    local_path,
                    remote_key,
                    callback=_progress_callback
                )
                
                if not success:
                    raise Exception(f"Failed to upload '{filename}'. The connection was rejected or the path is invalid.")

            end_time = time.time()
            elapsed_seconds = int(end_time - start_time)
            
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            self.finished.emit(duration_str)

        except Exception as e:
            logger.error(f"Upload Worker crashed: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False