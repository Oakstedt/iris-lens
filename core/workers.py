import os
import time
import logging
from typing import List, Tuple, Any

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class DownloadWorker(QThread):
    """
    Background thread for downloading files via the HCPClient.
    
    Emits progress updates to keep the main GUI responsive during 
    long-running network operations.
    """
    finished = pyqtSignal(str) 
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, client: Any, bucket: str, files_data: List[Tuple[str, int]], dest_folder: str, flatten: bool = False) -> None:
        """Initializes the worker with the active client and download queue."""
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

    def run(self) -> None:
        """Executes the S3 download queue."""
        start_time = time.time()
        logger.info("Starting worker. Job size: %d bytes.", self.total_bytes_job)

        try:
            for key, size in self.files_data:
                if not self._is_running: 
                    break
                
                def _progress_callback(chunk_size: int) -> None:
                    """Calculates and emits cumulative download progress."""
                    if not self._is_running: 
                        return
                        
                    self.bytes_transferred_so_far += chunk_size
                    
                    if self.total_bytes_job > 0:
                        current_percent = int((self.bytes_transferred_so_far / self.total_bytes_job) * 100)
                        if current_percent > self._last_emitted_percent:
                            self.progress_updated.emit(current_percent)
                            self._last_emitted_percent = current_percent

                # Delegate to the custom HCPClient wrapper
                self.client.download_object(
                    self.bucket, 
                    key, 
                    self.dest_folder, 
                    flatten=self.flatten,
                    callback=_progress_callback
                )
            
            # Format completion duration
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
            logger.error("Worker crashed: %s", e)
            self.error_occurred.emit(str(e))

    def stop(self) -> None:
        """Safely flags the worker to halt operations."""
        self._is_running = False


class UploadWorker(QThread):
    """
    Background thread for uploading local files via the HCPClient.
    
    Handles path sanitation and emits progress updates to the UI.
    """
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, client: Any, bucket: str, files_list: List[str], remote_folder: str) -> None:
        """Initializes the worker with the active client and local file list."""
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.files_list = files_list
        self.remote_folder = remote_folder
        
        self._is_running = True
        self.total_bytes_job = sum(os.path.getsize(f) for f in self.files_list)
        self.bytes_transferred_so_far = 0
        self._last_emitted_percent = -1

    def run(self) -> None:
        """Executes the S3 upload queue."""
        start_time = time.time()
        logger.info("Starting upload worker. Job size: %d bytes.", self.total_bytes_job)

        try:
            for local_path in self.files_list:
                if not self._is_running: 
                    break

                filename = os.path.basename(local_path)
                
                # Sanitize the folder path to avoid double slashes and hidden roots
                clean_folder = self.remote_folder.strip().replace("\\", "/")
                clean_folder = clean_folder.rstrip('/') 
                
                if clean_folder:
                    remote_key = f"{clean_folder}/{filename}"
                else:
                    remote_key = filename
                
                def _progress_callback(chunk_size: int) -> None:
                    """Calculates and emits cumulative upload progress."""
                    if not self._is_running: 
                        return
                        
                    self.bytes_transferred_so_far += chunk_size
                    
                    if self.total_bytes_job > 0:
                        current_percent = int((self.bytes_transferred_so_far / self.total_bytes_job) * 100)
                        if current_percent > self._last_emitted_percent:
                            self.progress_updated.emit(current_percent)
                            self._last_emitted_percent = current_percent

                # Delegate to the custom HCPClient wrapper
                self.client.upload_file(
                    self.bucket,
                    local_path,
                    remote_key,
                    callback=_progress_callback
                )

            # Format completion duration
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
            logger.error("Upload Worker crashed: %s", e)
            self.error_occurred.emit(str(e))

    def stop(self) -> None:
        """Safely flags the worker to halt operations."""
        self._is_running = False

class DeleteWorker(QThread):
    """
    Background thread for deleting files via the HCPClient.
    
    Iterates through a list of file keys and emits progress updates.
    """
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, client: Any, bucket: str, file_keys: List[str]) -> None:
        """Initializes the worker with the active client and target keys."""
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.file_keys = file_keys
        
        self._is_running = True
        self.total_files = len(self.file_keys)

    def run(self) -> None:
        """Executes the S3 deletion queue."""
        logger.info("Starting delete worker. Job size: %d files.", self.total_files)

        try:
            for index, key in enumerate(self.file_keys):
                if not self._is_running: 
                    break

                # Execute the deletion
                success = self.client.delete_object(self.bucket, key)
                if not success:
                    raise Exception(f"Server rejected deletion for: {key}")
                
                # Emit percentage based on file count
                current_percent = int(((index + 1) / self.total_files) * 100)
                self.progress_updated.emit(current_percent)

            # Pass a simple empty string instead of a calculated duration
            self.finished.emit("")

        except Exception as e:
            logger.error("Delete Worker crashed: %s", e)
            self.error_occurred.emit(str(e))

    def stop(self) -> None:
        """Safely flags the worker to halt operations."""
        self._is_running = False