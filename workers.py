import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class DownloadWorker(QThread):
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int) # Emits 0-100 percentage
    
    def __init__(self, client, bucket, files_data, dest_folder, flatten=False):
        """
        files_data: List of tuples (key, size_in_bytes)
        """
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.files_data = files_data
        self.dest_folder = dest_folder
        self.flatten = flatten
        self._is_running = True
        
        # Calculate Grand Total Size for the job
        self.total_bytes_job = sum(item[1] for item in self.files_data)
        self.bytes_transferred_so_far = 0

    def run(self):
        try:
            for key, size in self.files_data:
                if not self._is_running: break
                
                # Callback function for boto3
                def _progress_callback(chunk_size):
                    if not self._is_running: return
                    
                    self.bytes_transferred_so_far += chunk_size
                    
                    if self.total_bytes_job > 0:
                        current_percent = int((self.bytes_transferred_so_far / self.total_bytes_job) * 100)
                        
                        # OPTIMIZATION: Only emit if the number changed (e.g., went from 4% to 5%)
                        if current_percent > self._last_emitted_percent:
                            self.progress_updated.emit(current_percent)
                            self._last_emitted_percent = current_percent
                            
                # Call the client download with the callback
                # (Make sure you updated hcp_client.py to accept 'callback' as discussed!)
                self.client.download_object(
                    self.bucket, 
                    key, 
                    self.dest_folder, 
                    flatten=self.flatten,
                    callback=_progress_callback
                )
                
            self.finished.emit()

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False