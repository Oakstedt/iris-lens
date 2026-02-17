import sys
import os
import time
import ctypes
from PyQt6.QtGui import (QFont, QIcon)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QPushButton, QLabel, 
                             QStatusBar, QProgressBar, QFileDialog, QInputDialog, 
                             QLineEdit, QMessageBox, QTreeWidgetItemIterator) 

from PyQt6.QtCore import Qt

# --- IMPORTS (Refactored) ---
# We now import the SessionManager from 'core' instead of raw clients
from core.session import SessionManager 
from ui.components import FileBrowserTree
from core.workers import DownloadWorker

class MainWindow(QMainWindow):
    """ 
    The Main Window 
    Now acts purely as a Controller. It handles UI events and delegates logic 
    to the SessionManager.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iris Lens v1.1 - A HCP browser by GM")
        # Ensure assets folder exists or handle gracefully
        icon_path = os.path.join("assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setMinimumSize(1100, 700)
        
        # --- INIT BRAIN ---
        # The SessionManager handles Config + HCPClient internally
        self.session = SessionManager()

        # --- INIT BODY ---
        self._init_ui()
        self._init_menu()
        
        # --- START ENGINE ---
        self.refresh_ui_state()
        self.worker = None 

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # A. Warning Label
        self.warning_label = QLabel("⚠️ No Credentials Linked! Go to File > Link Credentials")
        self.warning_label.setStyleSheet("color: red; font-weight: bold; background: #ffe6e6; padding: 10px; border-radius: 5px;")
        self.layout.addWidget(self.warning_label)

        # B. Tenant Info
        self.lbl_tenant = QLabel("Connected to Tenant: None")
        self.lbl_tenant.setStyleSheet("color: gray; margin-bottom: 2px;")
        self.layout.addWidget(self.lbl_tenant)

        # C. Top Navigation Bar
        self.nav_bar = QHBoxLayout()
        self.bucket_combo = QComboBox()
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

        # E. File Table
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
        
        # G. Status Bar & Progress
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200) 
        self.progress_bar.setVisible(False)    
        self.status.addPermanentWidget(self.progress_bar)

    def _init_menu(self):
        menu = self.menuBar().addMenu("File")
        link_action = menu.addAction("Link Credentials File...")
        link_action.triggered.connect(self.on_link_credentials)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    # --- EVENT HANDLERS ---

    def refresh_ui_state(self):
        """ 
        Refactored: Now asks SessionManager about state instead of checking variables directly.
        """
        has_creds = self.session.has_credentials()
        self.warning_label.setVisible(not has_creds)
        
        if has_creds:
            # 1. Connect if needed
            # We access the internal client check via session
            if not self.session.client.connected:
                try:
                    self.session.connect_from_saved()
                except Exception as e:
                    print(f"Startup Connection Error: {e}")
                    self.warning_label.setText(f"⚠️ Connection Failed: {str(e)}")
                    self.warning_label.setVisible(True)
                    return

            # 2. Update Labels
            if self.session.client.connected:
                self.lbl_tenant.setText(self.session.get_tenant_label())
                
                # Styling
                if self.session.is_secure_tenant():
                    self.lbl_tenant.setStyleSheet("color: black; font-weight: bold; margin-bottom: 2px;")
                else:
                    self.lbl_tenant.setStyleSheet("color: gray; margin-bottom: 2px;")

            # 3. Enable controls
            self.bucket_combo.setEnabled(True)
            self.btn_read.setEnabled(True)
            
            # 4. Refresh buckets
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
            try:
                # REFACTOR: Use session to link and connect
                if self.session.link_new_credentials(fpath):
                    self.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                    self.file_browser.clear() 
                    self.refresh_ui_state()
            except Exception as e:
                self.status.showMessage(f"Connection Failed: {str(e)}", 5000)
                self.warning_label.setText(f"⚠️ Error: {str(e)}")
                self.warning_label.setVisible(True)

    def on_refresh_buckets(self):
        # REFACTOR: Get buckets from session
        buckets = self.session.get_bucket_list()
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
        QApplication.processEvents()
        
        # REFACTOR: Fetch files via session
        files = self.session.fetch_files(current_bucket)
        self.file_browser.populate_files(files)
        self.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def on_search_text_changed(self, text):
        self.file_browser.filter_items(text)

    def on_upload(self):
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket:
            self.status.showMessage("No bucket selected.", 3000)
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload")
        if not files: return 

        self.status.showMessage("Scanning remote folders...")
        QApplication.processEvents() 
        
        # REFACTOR: Access client through session for this specific helper
        existing_folders = self.session.client.get_existing_folders(current_bucket)
        
        combo_items = ["(Root / No Folder)"] + existing_folders
        
        remote_folder, ok = QInputDialog.getItem(
            self, 
            "Destination Folder", 
            "Select an existing folder OR type a new one:", 
            combo_items, 0, True 
        )
        
        if not ok:
            self.status.showMessage("Upload cancelled.", 3000)
            return
        
        if remote_folder == "(Root / No Folder)": remote_folder = ""
        remote_folder = remote_folder.strip()

        # Upload Loop
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
            
            # REFACTOR: Upload via session
            if self.session.upload_file(current_bucket, file_path, remote_folder):
                success_count += 1
            
            self.progress_bar.setValue(i + 1)
            time.sleep(0.05) # Tiny UI breather

        self.progress_bar.setVisible(False)
        self.status.showMessage(f"✅ Upload Complete. {success_count}/{total_files} files uploaded.", 5000)
        
        self.on_read_bucket()

    def on_download(self):
        # 1. Get Files
        # Use the new helper we added to ui_components (Cleaner than the old loop)
        selected_files = self.file_browser.get_selected_files_with_size()
        
        if not selected_files:
            self.status.showMessage("No files selected.")
            return
        
        # 2. Setup Destination
        current_bucket = self.bucket_combo.currentText()
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not dest_dir: return 

        # 3. Folder Structure Popup
        flatten_files = True 
        has_folders = any("/" in f[0] for f in selected_files)

        if has_folders:
            msg = QMessageBox(self)
            msg.setWindowTitle("Download Preference")
            msg.setText(f"Downloading {len(selected_files)} items.")
            msg.setInformativeText("Maintain folder structure?")
            btn_preserve = msg.addButton("Yes (Keep Structure)", QMessageBox.ButtonRole.ActionRole)
            btn_flatten = msg.addButton("No (Flatten Files)", QMessageBox.ButtonRole.ActionRole)
            msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()
            
            if msg.clickedButton() == btn_preserve: flatten_files = False
            elif msg.clickedButton() == btn_flatten: flatten_files = True
            else: return 

        # 4. Lock UI & Start Worker
        self.btn_download.setEnabled(False)
        self.btn_read.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100) 
        self.progress_bar.setValue(0)
        
        total_size_mb = sum(f[1] for f in selected_files) / (1024*1024)
        initial_msg = f"Downloading {len(selected_files)} files ({total_size_mb:.2f} MB)... (Please Wait)"
        self.status.showMessage(initial_msg)

        # REFACTOR: Pass the 'client' from the session to the worker
        # The worker needs the raw client object to do its threading magic
        self.worker = DownloadWorker(self.session.client, current_bucket, selected_files, dest_dir, flatten_files)
        
        self.worker.finished.connect(self.on_download_finished)
        self.worker.error_occurred.connect(self.on_download_error)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        
        self.worker.start()

    def on_download_finished(self, duration_str):
        self.status.showMessage("Download complete.")
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        self.btn_read.setEnabled(True)
        self.worker = None 
        QMessageBox.information(
            self, 
            "Download Complete", 
            f"All files downloaded successfully.\n\nTotal Time: {duration_str}"
        )

    def on_download_error(self, error_msg):
        self.status.showMessage(f"Error: {error_msg}")
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        self.btn_read.setEnabled(True)
        self.worker = None
        QMessageBox.critical(self, "Download Error", f"An error occurred:\n{error_msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Taskbar Hack for Windows
    if os.name == 'nt':
        try:
            myappid = 'mycompany.iris.lens.v1.1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app.setStyle("Fusion") 
    
    # Set the App-wide icon
    icon_path = os.path.join("assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())