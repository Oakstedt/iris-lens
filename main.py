import sys
import os
import time
import ctypes
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QInputDialog, QMessageBox
from PyQt6.QtGui import QIcon

# Core Imports
from core.session import SessionManager 
from core.workers import DownloadWorker

# UI Imports
from ui.layout import MainWindowLayout

class MainWindow(QMainWindow):
    """ Controller class. Manages application state and user interactions. """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iris Lens v1.1")
        self.setMinimumSize(1100, 700)
        
        # Set Icon
        icon_path = os.path.join("assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Initialize Logic
        self.session = SessionManager()
        self.worker = None

        # Initialize UI
        self.ui_manager = MainWindowLayout()
        self.ui_manager.setup_ui(self)
        self.ui_manager.setup_menu(self)

        # Connect Signals (Events)
        self._connect_signals()

        # Startup State Check
        self.refresh_ui_state()

    def _connect_signals(self):
        """ Binds UI elements to class methods. """
        self.btn_read.clicked.connect(self.on_read_bucket)
        self.btn_upload.clicked.connect(self.on_upload)
        self.btn_download.clicked.connect(self.on_download)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.action_link.triggered.connect(self.on_link_credentials)

    # --- LOGIC & STATE MANAGEMENT ---

    def refresh_ui_state(self):
        """ Updates UI elements based on current connection state. """
        has_creds = self.session.has_credentials()
        self.warning_label.setVisible(not has_creds)
        
        if has_creds:
            if not self.session.client.connected:
                try:
                    self.session.connect_from_saved()
                except Exception as e:
                    self.warning_label.setText(f"Connection Failed: {str(e)}")
                    self.warning_label.setVisible(True)
                    return

            if self.session.client.connected:
                self.lbl_tenant.setText(self.session.get_tenant_label())
                style = "color: black; font-weight: bold;" if self.session.is_secure_tenant() else "color: gray;"
                self.lbl_tenant.setStyleSheet(f"{style} margin-bottom: 2px;")

            self.bucket_combo.setEnabled(True)
            self.btn_read.setEnabled(True)
            self.on_refresh_buckets()
        else:
            self.bucket_combo.setEnabled(False)
            self.btn_read.setEnabled(False)

    def on_link_credentials(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select Credentials", "", "JSON (*.json);;All Files (*)")
        if fpath:
            try:
                if self.session.link_new_credentials(fpath):
                    self.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                    self.file_browser.clear() 
                    self.refresh_ui_state()
            except Exception as e:
                self.status.showMessage(f"Connection Failed: {str(e)}", 5000)

    def on_refresh_buckets(self):
        buckets = self.session.get_bucket_list()
        self.bucket_combo.clear()
        if buckets:
            self.bucket_combo.addItems(buckets)
            self.status.showMessage(f"Ready. {len(buckets)} buckets loaded.", 2000)

    def on_read_bucket(self):
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket: return
        
        self.status.showMessage(f"Reading {current_bucket}...")
        QApplication.processEvents()
        
        files = self.session.fetch_files(current_bucket)
        self.file_browser.populate_files(files)
        self.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def on_search_text_changed(self, text):
        self.file_browser.filter_items(text)

    def on_upload(self):
        current_bucket = self.bucket_combo.currentText()
        if not current_bucket: return

        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload")
        if not files: return 

        self.status.showMessage("Scanning remote folders...")
        QApplication.processEvents() 
        
        existing_folders = self.session.client.get_existing_folders(current_bucket)
        combo_items = ["(Root / No Folder)"] + existing_folders
        
        remote_folder, ok = QInputDialog.getItem(self, "Destination", "Select Folder:", combo_items, 0, True)
        if not ok: return
        
        if remote_folder == "(Root / No Folder)": remote_folder = ""
        
        total_files = len(files)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        
        for i, file_path in enumerate(files):
            self.status.showMessage(f"Uploading {i+1}/{total_files}...")
            QApplication.processEvents()
            self.session.upload_file(current_bucket, file_path, remote_folder.strip())
            self.progress_bar.setValue(i + 1)
            time.sleep(0.05)

        self.progress_bar.setVisible(False)
        self.status.showMessage("Upload Complete.", 5000)
        self.on_read_bucket()

    def on_download(self):
        selected_files = self.file_browser.get_selected_files_with_size()
        if not selected_files:
            self.status.showMessage("No files selected.")
            return
        
        current_bucket = self.bucket_combo.currentText()
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not dest_dir: return 

        flatten_files = True
        if any("/" in f[0] for f in selected_files):
            msg = QMessageBox(self)
            msg.setWindowTitle("Download Preference")
            msg.setText("Maintain folder structure?")
            btn_preserve = msg.addButton("Yes", QMessageBox.ButtonRole.ActionRole)
            btn_flatten = msg.addButton("No", QMessageBox.ButtonRole.ActionRole)
            msg.exec()
            if msg.clickedButton() == btn_preserve: flatten_files = False

        self.btn_download.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = DownloadWorker(self.session.client, current_bucket, selected_files, dest_dir, flatten_files)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.error_occurred.connect(self.on_download_error)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.start()

    def on_download_finished(self, duration_str):
        self.status.showMessage("Download complete.")
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        self.worker = None 
        QMessageBox.information(self, "Complete", f"Download finished in {duration_str}")

    def on_download_error(self, error_msg):
        self.status.showMessage(f"Error: {error_msg}")
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        self.worker = None
        QMessageBox.critical(self, "Error", error_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if os.name == 'nt':
        try:
            myappid = 'mycompany.iris.lens.v1.1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception: pass

    app.setStyle("Fusion") 
    window = MainWindow()
    window.show()
    sys.exit(app.exec())