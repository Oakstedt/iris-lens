# main.py
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QPushButton, QLabel, 
                             QStatusBar, QFileDialog, QLineEdit)

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
        
        # Initial State Check
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

    def _init_menu(self):
        menu = self.menuBar().addMenu("File")
        link_action = menu.addAction("Link Credentials File...")
        link_action.triggered.connect(self.on_link_credentials)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    # --- EVENT HANDLERS ---

    def refresh_ui_state(self):
        has_creds = self.config.has_credentials()
        self.warning_label.setVisible(not has_creds)
        self.bucket_combo.setEnabled(has_creds)
        self.btn_read.setEnabled(has_creds)
        
        if has_creds and self.bucket_combo.count() == 0:
            self.on_refresh_buckets()

    def on_link_credentials(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select Credentials", "", "All Files (*)")
        if fpath:
            self.config.set("credentials_path", fpath)
            self.status.showMessage(f"Linked: {fpath}", 3000)
            self.refresh_ui_state()

    def on_refresh_buckets(self):
        self.status.showMessage("Refreshing buckets...")
        buckets = self.client.list_buckets()
        self.bucket_combo.clear()
        self.bucket_combo.addItems(buckets)
        self.status.showMessage("Ready", 2000)

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
        selected = self.file_browser.get_selected_filenames()
        if not selected:
            self.status.showMessage("No files selected.", 3000)
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Destination")
        if dest_dir:
            self.status.showMessage(f"Downloading {len(selected)} files to {dest_dir}...")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())