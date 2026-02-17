import os
import time
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QApplication
from core.workers import DownloadWorker

class ActionManager:
    """Handles all button clicks and logic flows for the Main Window."""
    
    def __init__(self, window):
        self.window = window
        self.session = window.session
        self.worker = None # We keep the worker reference here now

    def refresh_state(self):
        """Checks connection status and updates labels/buttons accordingly."""
        has_creds = self.session.has_credentials()
        self.window.warning_label.setVisible(not has_creds)
        
        if has_creds:
            if not self.session.client.connected:
                try:
                    self.session.connect_from_saved()
                except Exception as e:
                    self.window.warning_label.setText(f"Connection Failed: {str(e)}")
                    self.window.warning_label.setVisible(True)
                    return

            if self.session.client.connected:
                self.window.lbl_tenant.setText(self.session.get_tenant_label())
                style = "color: black; font-weight: bold;" if self.session.is_secure_tenant() else "color: gray;"
                self.window.lbl_tenant.setStyleSheet(f"{style} margin-bottom: 2px;")

            self.window.bucket_combo.setEnabled(True)
            self.window.btn_read.setEnabled(True)
            self.refresh_buckets()
        else:
            self.window.bucket_combo.setEnabled(False)
            self.window.btn_read.setEnabled(False)

    def link_credentials(self):
        fpath, _ = QFileDialog.getOpenFileName(self.window, "Select Credentials", "", "JSON (*.json);;All Files (*)")
        if fpath:
            try:
                if self.session.link_new_credentials(fpath):
                    self.window.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                    self.window.file_browser.clear() 
                    self.refresh_state()
            except Exception as e:
                self.window.status.showMessage(f"Connection Failed: {str(e)}", 5000)

    def refresh_buckets(self):
        buckets = self.session.get_bucket_list()
        self.window.bucket_combo.clear()
        if buckets:
            self.window.bucket_combo.addItems(buckets)
            self.window.status.showMessage(f"Ready. {len(buckets)} buckets loaded.", 2000)

    def read_bucket(self):
        current_bucket = self.window.bucket_combo.currentText()
        if not current_bucket: return
        
        self.window.status.showMessage(f"Reading {current_bucket}...")
        QApplication.processEvents()
        
        files = self.session.fetch_files(current_bucket)
        self.window.file_browser.populate_files(files)
        self.window.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def search(self, text):
        self.window.file_browser.filter_items(text)

    def upload(self):
        current_bucket = self.window.bucket_combo.currentText()
        if not current_bucket: return

        files, _ = QFileDialog.getOpenFileNames(self.window, "Select Files to Upload")
        if not files: return 

        self.window.status.showMessage("Scanning remote folders...")
        QApplication.processEvents() 
        
        existing_folders = self.session.client.get_existing_folders(current_bucket)
        combo_items = ["(Root / No Folder)"] + existing_folders
        
        remote_folder, ok = QInputDialog.getItem(self.window, "Destination", "Select Folder:", combo_items, 0, True)
        if not ok: return
        
        if remote_folder == "(Root / No Folder)": remote_folder = ""
        
        total_files = len(files)
        self.window.progress_bar.setVisible(True)
        self.window.progress_bar.setRange(0, total_files)
        self.window.progress_bar.setValue(0)
        
        for i, file_path in enumerate(files):
            self.window.status.showMessage(f"Uploading {i+1}/{total_files}...")
            QApplication.processEvents()
            self.session.upload_file(current_bucket, file_path, remote_folder.strip())
            self.window.progress_bar.setValue(i + 1)
            time.sleep(0.05)

        self.window.progress_bar.setVisible(False)
        self.window.status.showMessage("Upload Complete.", 5000)
        self.read_bucket()

    def download(self):
        selected_files = self.window.file_browser.get_selected_files_with_size()
        if not selected_files:
            self.window.status.showMessage("No files selected.")
            return
        
        current_bucket = self.window.bucket_combo.currentText()
        dest_dir = QFileDialog.getExistingDirectory(self.window, "Select Download Folder")
        if not dest_dir: return 

        flatten_files = True
        if any("/" in f[0] for f in selected_files):
            msg = QMessageBox(self.window)
            msg.setWindowTitle("Download Preference")
            msg.setText("Maintain folder structure?")
            btn_preserve = msg.addButton("Yes", QMessageBox.ButtonRole.ActionRole)
            btn_flatten = msg.addButton("No", QMessageBox.ButtonRole.ActionRole)
            msg.exec()
            if msg.clickedButton() == btn_preserve: flatten_files = False

        self.window.btn_download.setEnabled(False)
        self.window.progress_bar.setVisible(True)
        self.window.progress_bar.setValue(0)
        
        self.worker = DownloadWorker(self.session.client, current_bucket, selected_files, dest_dir, flatten_files)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error_occurred.connect(self._on_download_error)
        self.worker.progress_updated.connect(self.window.progress_bar.setValue)
        self.worker.start()

    def _on_download_finished(self, duration_str):
        self.window.status.showMessage("Download complete.")
        self.window.progress_bar.setVisible(False)
        self.window.btn_download.setEnabled(True)
        self.worker = None 
        QMessageBox.information(self.window, "Complete", f"Download finished in {duration_str}")

    def _on_download_error(self, error_msg):
        self.window.status.showMessage(f"Error: {error_msg}")
        self.window.progress_bar.setVisible(False)
        self.window.btn_download.setEnabled(True)
        self.worker = None
        QMessageBox.critical(self.window, "Error", error_msg)