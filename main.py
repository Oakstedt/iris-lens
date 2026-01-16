import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QPushButton, QLabel, 
                             QStatusBar, QProgressBar, QFileDialog, QLineEdit)

# Import our modular classes
from config_manager import ConfigManager
from hcp_client import HCPClient
from ui_components import FileBrowserTable

class MainWindow(QMainWindow):
    """ The main application controller. Connects UI, Logic, and Config. """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGP-Iris Lens")
        self.setMinimumSize(1100, 700)
        
        # Initialize Core Logic modules
        self.config = ConfigManager()
        self.client = HCPClient()

        # Build UI
        self._init_ui()
        self._init_menu()
        
        # Initial State Check (Safe Startup)
        self.refresh_ui_state()

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # A. Warning Label
        self.warning_label = QLabel("⚠️ No Credentials Linked! Go to File > Link Credentials")
        self.warning_label.setStyleSheet("color: red; font-weight: bold; background: #ffe6e6; padding: 10px; border-radius: 5px;")
        self.layout.addWidget(self.warning_label)

        # B. Top Navigation Bar
        self.nav_bar = QHBoxLayout()
        self.bucket_combo = QComboBox()
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_read = QPushButton("Read Bucket")
        
        self.nav_bar.addWidget(QLabel("HCP Bucket:"))
        self.nav_bar.addWidget(self.bucket_combo, 1)
        self.nav_bar.addWidget(self.btn_read)
        self.nav_bar.addWidget(self.btn_refresh)
        
        self.btn_refresh.clicked.connect(self.on_refresh_buckets)
        self.btn_read.clicked.connect(self.on_read_bucket)
        
        self.layout.addLayout(self.nav_bar)

        # C. Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter displayed files...")
        self.search_input.textChanged.connect(self.on_search_changed)
        self.layout.addWidget(self.search_input)

        # D. File Table (Imported Component)
        self.file_browser = FileBrowserTable()
        self.layout.addWidget(self.file_browser)

        # E. Action Buttons
        self.action_bar = QHBoxLayout()
        self.btn_upload = QPushButton("Upload File...")
        self.btn_download = QPushButton("Download Selected")
        
        self.btn_upload.clicked.connect(self.on_upload)
        self.btn_download.clicked.connect(self.on_download)
        
        self.action_bar.addWidget(self.btn_upload)
        self.action_bar.addWidget(self.btn_download)
        self.layout.addLayout(self.action_bar)
        
        # F. Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # G. Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200) # Keep it small
        self.progress_bar.setVisible(False)    # Hide initially
        self.status.addPermanentWidget(self.progress_bar)

    def _init_menu(self):
        menu = self.menuBar().addMenu("File")
        link_action = menu.addAction("Link Credentials File...")
        link_action.triggered.connect(self.on_link_credentials)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    # --- EVENT HANDLERS ---

    def refresh_ui_state(self):
        """ Checks credentials and updates UI. Does NOT crash on failure. """
        has_creds = self.config.has_credentials()
        self.warning_label.setVisible(not has_creds)
        
        if has_creds:
            # Try to connect if not already connected
            if not self.client.connected:
                path = self.config.get("credentials_path")
                try:
                    self.client.connect(path)
                except Exception as e:
                    print(f"Startup Connection Error: {e}")
                    self.warning_label.setText(f"⚠️ Connection Failed: {str(e)}")
                    self.warning_label.setVisible(True)
                    return

            # Enable controls
            self.bucket_combo.setEnabled(True)
            self.btn_read.setEnabled(True)
            
            # Safely refresh buckets
            if self.bucket_combo.count() == 0:
                try:
                    self.on_refresh_buckets()
                except Exception as e:
                    print(f"Bucket refresh failed: {e}")
        else:
            self.bucket_combo.setEnabled(False)
            self.btn_read.setEnabled(False)

    def on_link_credentials(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select Credentials", "", "JSON (*.json);;All Files (*)")
        if fpath:
            self.config.set("credentials_path", fpath)
            try:
                self.client.connect(fpath)
                self.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                self.refresh_ui_state()
            except Exception as e:
                self.status.showMessage(f"Connection Failed: {str(e)}", 5000)
                self.warning_label.setText(f"⚠️ Error: {str(e)}")
                self.warning_label.setVisible(True)

    def on_refresh_buckets(self):
        self.status.showMessage("Refreshing buckets...")
        buckets = self.client.list_buckets()
        self.bucket_combo.clear()
        
        if buckets:
            self.bucket_combo.addItems(buckets)
            self.status.showMessage("Ready", 2000)
        else:
            self.status.showMessage("No buckets found or access denied.", 3000)

    def on_read_bucket(self):
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket: return
        
        self.status.showMessage(f"Reading {current_bucket}...")
        files = self.client.fetch_files(current_bucket)
        self.file_browser.populate_files(files)
        self.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def on_search_changed(self, text):
        self.file_browser.filter_rows(text)

    def on_upload(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Upload File")
        if fpath:
            self.status.showMessage(f"Uploading {os.path.basename(fpath)}...")

    def on_download(self):
        # 1. Get Keys
        selected_keys = self.file_browser.get_selected_file_keys()
        if not selected_keys:
            self.status.showMessage("No files selected.", 3000)
            return
        
        current_bucket = self.bucket_combo.currentText()
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not dest_dir:
            return 

        # 2. Setup Progress Bar
        total_files = len(selected_keys)
        self.status.showMessage(f"Starting download of {total_files} files...")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        
        success_count = 0
        
        # 3. Download Loop
        for i, key in enumerate(selected_keys):
            self.status.showMessage(f"Downloading {i+1}/{total_files}: {key}...")
            QApplication.processEvents() 
            
            # Try to download
            if self.client.download_object(current_bucket, key, dest_dir):
                success_count += 1
            
            # Update Progress Bar
            self.progress_bar.setValue(i + 1)
            
            # THROTTLE: Sleep for 0.5 seconds to prevent server rate-limiting
            time.sleep(0.5)
        
        # 4. Cleanup
        self.progress_bar.setVisible(False)
        
        if success_count == total_files:
            self.status.showMessage(f"✅ Success! All {success_count} files downloaded.", 5000)
        else:
            self.status.showMessage(f"⚠️ Finished. {success_count}/{total_files} successful.", 8000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())