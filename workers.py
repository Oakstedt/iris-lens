import os
import logging
from PyQt6.QtCore import QThread, pyqtSignal

# Setup logging
logger = logging.getLogger(__name__)

class DownloadWorker(QThread):
    """
    Runs the download operation in a separate thread to prevent UI freezing.
    Emits signals when finished or if an error occurs.
    """
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, client, bucket, keys, dest_folder, flatten=False):
        super().__init__()
        self.client = client
        self.bucket = bucket
        self.keys = keys
        self.dest_folder = dest_folder
        self.flatten = flatten
        self._is_running = True

    def run(self):
        """ The main logic that runs in the background. """
        try:
            total_files = len(self.keys)
            logger.info(f"Starting background download for {total_files} items.")

            for i, key in enumerate(self.keys):
                if not self._is_running:
                    break
                
                # Perform the blocking download call here
                success = self.client.download_object(
                    self.bucket, 
                    key, 
                    self.dest_folder, 
                    flatten=self.flatten
                )
                
                if not success:
                    # We continue trying other files even if one fails, 
                    # but you could choose to break here.
                    logger.warning(f"Failed to download: {key}")

            self.finished.emit()

        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            self.error_occurred.emit(str(e))

    def stop(self):
        """ Allows the user to cancel the download cleanly. """
        self._is_running = False