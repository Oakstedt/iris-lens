import sys
import os
import time
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QPushButton, QLabel, 
                             QStatusBar, QProgressBar, QFileDialog, QInputDialog, QLineEdit,
                             QTreeWidget, QMessageBox)
from PyQt6.QtGui import (QFont, QIcon)

# Import our modular classes
from config_manager import ConfigManager
from hcp_client import HCPClient
from ui_components import FileBrowserTree

class MainWindow(QMainWindow):
    """ The main application controller. Connects UI, Logic, and Config. """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGP-Iris Lens")
        self.setWindowIcon(QIcon(os.path.join("assets", "icon.ico")))
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

        # B. Tenant Info (NEW: Added as requested)
        self.lbl_tenant = QLabel("Connected to Tenant: None")
        self.lbl_tenant.setStyleSheet("color: gray; margin-bottom: 2px;")
        self.layout.addWidget(self.lbl_tenant)

        # C. Top Navigation Bar
        self.nav_bar = QHBoxLayout()
        self.bucket_combo = QComboBox()
        # Removed Refresh Button as requested
        self.btn_read = QPushButton("Read Bucket")
        
        self.nav_bar.addWidget(QLabel("HCP Bucket:"))
        self.nav_bar.addWidget(self.bucket_combo, 1)
        self.nav_bar.addWidget(self.btn_read)
        
        self.btn_read.clicked.connect(self.on_read_bucket)
        
        self.layout.addLayout(self.nav_bar)

        # D. Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter displayed files...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.layout.addWidget(self.search_input)

        # E. File Table (Imported Component)
        self.file_browser = FileBrowserTree()
        self.layout.addWidget(self.file_browser)

        # F. Action Buttons
        self.action_bar = QHBoxLayout()
        self.btn_upload = QPushButton("Upload File...")
        self.btn_download = QPushButton("Download Selected")
        
        self.btn_upload.clicked.connect(self.on_upload)
        self.btn_download.clicked.connect(self.on_download)
        
        self.action_bar.addWidget(self.btn_upload)
        self.action_bar.addWidget(self.btn_download)
        self.layout.addLayout(self.action_bar)
        
        # G. Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # H. Progress bar
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
            # 1. Ensure we are connected
            if not self.client.connected:
                path = self.config.get("credentials_path")
                try:
                    self.client.connect(path)
                except Exception as e:
                    print(f"Startup Connection Error: {e}")
                    self.warning_label.setText(f"⚠️ Connection Failed: {str(e)}")
                    self.warning_label.setVisible(True)
                    return

            # 2. ALWAYS Update Tenant Label (The Fix)
            # We do this outside the 'if not connected' block so it updates on file swaps too.
            if self.client.connected:
                t_addr = getattr(self.client, 'tenant_address', "Unknown")
                self.lbl_tenant.setText(f"Connected to Tenant: {t_addr}")
                
                if "http" in str(t_addr):
                    self.lbl_tenant.setStyleSheet("color: black; font-weight: bold; margin-bottom: 2px;")
                else:
                    self.lbl_tenant.setStyleSheet("color: gray; margin-bottom: 2px;")

            # 3. Enable controls
            self.bucket_combo.setEnabled(True)
            self.btn_read.setEnabled(True)
            
            # 4. Safely refresh buckets
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
                if self.client.connect(fpath):
                    self.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                    
                    # 1. Clear the old file list immediately
                    self.file_browser.clear() 
                    
                    # 2. Refresh the UI state (buckets, labels, etc.)
                    self.refresh_ui_state()
            except Exception as e:
                self.status.showMessage(f"Connection Failed: {str(e)}", 5000)
                self.warning_label.setText(f"⚠️ Error: {str(e)}")
                self.warning_label.setVisible(True)

    def on_refresh_buckets(self):
        # Kept the logic, removed the button
        buckets = self.client.list_buckets()
        self.bucket_combo.clear()
        
        if buckets:
            self.bucket_combo.addItems(buckets)
            self.status.showMessage(f"Ready. {len(buckets)} buckets loaded.", 2000)
        else:
            self.status.showMessage("No buckets found or access denied.", 3000)

    def on_read_bucket(self):
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket: return
        
        self.status.showMessage(f"Reading {current_bucket}...")
        QApplication.processEvents() # Force UI update
        files = self.client.fetch_files(current_bucket)
        self.file_browser.populate_files(files)
        self.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def on_search_text_changed(self, text):
        self.file_browser.filter_items(text)

    def on_upload(self):
        # 1. Check Bucket
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket:
            self.status.showMessage("No bucket selected.", 3000)
            return

        # 2. Select Local Files
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload")
        if not files:
            return 

        # 3. Get Existing Folders (Smart Selection)
        self.status.showMessage("Scanning remote folders...")
        QApplication.processEvents() 
        
        existing_folders = self.client.get_existing_folders(current_bucket)
        
        combo_items = ["(Root / No Folder)"] + existing_folders
        
        remote_folder, ok = QInputDialog.getItem(
            self, 
            "Destination Folder", 
            "Select an existing folder OR type a new one:", 
            combo_items, 
            0,     
            True   
        )
        
        if not ok:
            self.status.showMessage("Upload cancelled.", 3000)
            return
        
        if remote_folder == "(Root / No Folder)":
            remote_folder = ""
        
        remote_folder = remote_folder.strip()

        # 5. Upload Loop
        total_files = len(files)
        self.status.showMessage(f"Starting upload of {total_files} files...")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        
        success_count = 0
        
        for i, file_path in enumerate(files):
            fname = os.path.basename(file_path)
            self.status.showMessage(f"Uploading {i+1}/{total_files}: {fname}...")
            QApplication.processEvents()
            
            if self.client.upload_file(current_bucket, file_path, remote_folder):
                success_count += 1
            
            self.progress_bar.setValue(i + 1)
            
            import time
            time.sleep(0.1)

        # 6. Cleanup & Refresh
        self.progress_bar.setVisible(False)
        self.status.showMessage(f"✅ Upload Complete. {success_count}/{total_files} files uploaded.", 5000)
        
        if hasattr(self, 'on_read_bucket'):
            self.on_read_bucket()

    def on_download(self):
        # 1. Get Selected Keys
        selected_keys = self.file_browser.get_selected_file_keys()
        if not selected_keys:
            self.status.showMessage("No files selected.", 3000)
            return
        
        current_bucket = self.bucket_combo.currentText()
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not dest_dir:
            return 

        # 2. Smart Check: Folders involved?
        has_folders = any("/" in key for key in selected_keys)
        flatten_files = True 

        if has_folders:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Download Preference")
            msg_box.setText(f"You are downloading {len(selected_keys)} file(s).")
            msg_box.setInformativeText("How would you like to handle the folder structure?")
            
            btn_preserve = msg_box.addButton("Download with folder(s)", QMessageBox.ButtonRole.ActionRole)
            btn_flatten = msg_box.addButton("Download file(s) only", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton(QMessageBox.StandardButton.Cancel)
            
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            if clicked_button == btn_preserve:
                flatten_files = False
            elif clicked_button == btn_flatten:
                flatten_files = True
            else:
                return 

        # 3. Download Loop
        total_files = len(selected_keys)
        self.status.showMessage(f"Starting download of {total_files} files...")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        
        success_count = 0
        
        import time
        for i, key in enumerate(selected_keys):
            self.status.showMessage(f"Downloading {i+1}/{total_files}: {key}...")
            QApplication.processEvents()
            
            if self.client.download_object(current_bucket, key, dest_dir, flatten=flatten_files):
                success_count += 1
            
            self.progress_bar.setValue(i + 1)
            time.sleep(0.1)
        
        self.progress_bar.setVisible(False)
        self.status.showMessage(f"✅ Download Complete. {success_count}/{total_files} files.", 5000)

if __name__ == "__main__":
    # 1. The "Taskbar Hack" to show the correct icon
    # This separates your app from the generic Python host process
    myappid = 'mycompany.myproduct.subproduct.version' # Arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 2. Set the App-wide icon (covers dialogs, taskbar, etc.)
    # Make sure 'assets/icon.ico' exists!
    if os.path.exists(os.path.join("assets", "icon.ico")):
        app.setWindowIcon(QIcon(os.path.join("assets", "icon.ico")))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())