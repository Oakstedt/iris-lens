import logging
import time
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class DownloadWorker(QThread):
    # CHANGED: 'finished' now carries a string (the duration)
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
        # 1. Capture Start Time
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
            
            # 2. Calculate Duration
            end_time = time.time()
            elapsed_seconds = int(end_time - start_time)
            
            # Format nicely (Hours:Minutes:Seconds)
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            # 3. Emit the duration string
            self.finished.emit(duration_str)

        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False