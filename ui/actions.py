import os
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QApplication

from core.workers import DownloadWorker, UploadWorker

from ui.components import AboutDialog


class ActionManager:
    """
    Handles all button clicks and logic flows for the Main Window.
    
    Acts as the bridge between the UI components and the underlying S3 session,
    managing state updates, file dialogues, and background worker threads.
    """
    
    def __init__(self, window: Any) -> None:
        """Initializes the ActionManager with a reference to the main window."""
        self.window = window
        self.session = window.session
        self.worker = None  # Retains a reference to active QThread workers to prevent garbage collection

    def refresh_state(self) -> None:
        """Evaluates the current connection status and toggles UI elements accordingly."""
        has_creds = self.session.has_credentials()
        self.window.warning_label.setVisible(not has_creds)
        
        if has_creds:
            # Attempt to establish a connection if one does not exist
            if not self.session.client.connected:
                try:
                    self.session.connect_from_saved()
                except Exception as e:
                    self.window.warning_label.setText(f"Connection Failed: {str(e)}")
                    self.window.warning_label.setVisible(True)
                    return

            # Update tenant UI labels upon successful connection
            if self.session.client.connected:
                self.window.lbl_tenant.setText(self.session.get_tenant_label())
                
                # Visually distinguish secure vs. non-secure tenants
                style = "color: black; font-weight: bold;" if self.session.is_secure_tenant() else "color: gray;"
                self.window.lbl_tenant.setStyleSheet(f"{style} margin-bottom: 2px;")

            # Enable bucket interactions
            self.window.bucket_combo.setEnabled(True)
            self.window.btn_read.setEnabled(True)
            self.refresh_buckets()
        else:
            # Lock UI if no credentials exist
            self.window.bucket_combo.setEnabled(False)
            self.window.btn_read.setEnabled(False)

    def link_credentials(self) -> None:
        """Opens a file dialog to link a new JSON credential file to the session."""
        fpath, _ = QFileDialog.getOpenFileName(
            self.window, "Select Credentials", "", "JSON (*.json);;All Files (*)"
        )
        
        if fpath:
            try:
                if self.session.link_new_credentials(fpath):
                    self.window.status.showMessage(f"Connected: {os.path.basename(fpath)}", 3000)
                    self.window.file_browser.clear() 
                    self.refresh_state()
            except Exception as e:
                self.window.status.showMessage(f"Connection Failed: {str(e)}", 5000)

    def refresh_buckets(self) -> None:
        """Fetches the list of available S3 buckets and populates the dropdown menu."""
        buckets = self.session.get_bucket_list()
        self.window.bucket_combo.clear()
        
        if buckets:
            self.window.bucket_combo.addItems(buckets)
            self.window.status.showMessage(f"Ready. {len(buckets)} buckets loaded.", 2000)

    def read_bucket(self) -> None:
        """Fetches and displays the file hierarchy for the currently selected bucket."""
        current_bucket = self.window.bucket_combo.currentText()
        if not current_bucket: 
            return
        
        self.window.status.showMessage(f"Reading {current_bucket}...")
        QApplication.processEvents()  # Force UI update before blocking operation
        
        files = self.session.fetch_files(current_bucket)
        self.window.file_browser.populate_files(files)
        self.window.status.showMessage(f"Loaded {len(files)} files.", 3000)

    def search(self, text: str) -> None:
        """Filters the file browser items based on the search input."""
        self.window.file_browser.filter_items(text)

    def upload(self) -> None:
        """Handles the UI flow for selecting files and starting the UploadWorker."""
        current_bucket = self.window.bucket_combo.currentText()
        if not current_bucket: 
            return

        # 1. Select files
        files, _ = QFileDialog.getOpenFileNames(self.window, "Select Files to Upload")
        if not files: 
            return 

        self.window.status.showMessage("Scanning remote folders...")
        QApplication.processEvents() 
        
        # 2. Determine destination folder
        existing_folders = self.session.client.get_existing_folders(current_bucket)
        combo_items = ["(Root / No Folder)"] + existing_folders
        
        remote_folder, ok = QInputDialog.getItem(
            self.window, "Destination", "Select Folder:", combo_items, 0, True
        )
        
        if not ok: 
            return
        if remote_folder == "(Root / No Folder)": 
            remote_folder = ""
        
        # 3. Configure progress UI
        self.window.progress_bar.setVisible(True)
        self.window.progress_bar.setRange(0, 100)
        self.window.progress_bar.setValue(0)
        self.window.status.showMessage(f"Uploading {len(files)} file(s)...")
        
        # 4. Instantiate and start the worker thread
        self.worker = UploadWorker(self.session.client, current_bucket, files, remote_folder.strip())
        self.worker.finished.connect(self._on_upload_finished)
        self.worker.error_occurred.connect(self._on_upload_error)
        self.worker.progress_updated.connect(self.window.progress_bar.setValue)
        self.worker.start()

    def _on_upload_finished(self, duration_str: str) -> None:
        """Callback triggered upon successful completion of the UploadWorker."""
        self.window.status.showMessage("Upload Complete.", 5000)
        self.window.progress_bar.setVisible(False)
        self.worker = None
        
        self.read_bucket()  # Auto-refresh the view to show new files
        QMessageBox.information(self.window, "Complete", f"Upload finished in {duration_str}")

    def _on_upload_error(self, error_msg: str) -> None:
        """Callback triggered if the UploadWorker encounters an exception."""
        self.window.status.showMessage(f"Error: {error_msg}")
        self.window.progress_bar.setVisible(False)
        self.worker = None
        
        QMessageBox.critical(self.window, "Error", error_msg)

    def download(self) -> None:
        """Handles the UI flow for selecting files, setting options, and starting the DownloadWorker."""
        selected_files = self.window.file_browser.get_selected_files_with_size()
        if not selected_files:
            self.window.status.showMessage("No files selected.")
            return
        
        current_bucket = self.window.bucket_combo.currentText()
        
        # 1. Select destination directory
        dest_dir = QFileDialog.getExistingDirectory(self.window, "Select Download Folder")
        if not dest_dir: 
            return 

        # 2. Prompt for folder flattening if applicable
        flatten_files = True
        if any("/" in f[0] for f in selected_files):
            msg = QMessageBox(self.window)
            msg.setWindowTitle("Download Preference")
            msg.setText("Maintain folder structure?")
            
            btn_preserve = msg.addButton("Yes (download with folder(s))", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("No (download file(s) only)", QMessageBox.ButtonRole.ActionRole)
            
            msg.exec()
            if msg.clickedButton() == btn_preserve: 
                flatten_files = False

        # 3. Configure progress UI
        self.window.btn_download.setEnabled(False)
        self.window.progress_bar.setVisible(True)
        self.window.progress_bar.setValue(0)
        self.window.status.showMessage("Downloading file(s) - Please wait...")
        
        # 4. Instantiate and start the worker thread
        self.worker = DownloadWorker(
            self.session.client, current_bucket, selected_files, dest_dir, flatten_files
        )
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error_occurred.connect(self._on_download_error)
        self.worker.progress_updated.connect(self.window.progress_bar.setValue)
        self.worker.start()

    def _on_download_finished(self, duration_str: str) -> None:
        """Callback triggered upon successful completion of the DownloadWorker."""
        self.window.status.showMessage("Download complete.")
        self.window.progress_bar.setVisible(False)
        self.window.btn_download.setEnabled(True)
        self.worker = None 
        
        QMessageBox.information(self.window, "Complete", f"Download finished in {duration_str}")

    def _on_download_error(self, error_msg: str) -> None:
        """Callback triggered if the DownloadWorker encounters an exception."""
        self.window.status.showMessage(f"Error: {error_msg}")
        self.window.progress_bar.setVisible(False)
        self.window.btn_download.setEnabled(True)
        self.worker = None
        
        QMessageBox.critical(self.window, "Error", error_msg)

    def show_about(self) -> None:
        """Instantiates and displays the About dialog, listening for the admin unlock signal."""
        from .components import AboutDialog  # Local import prevents circular dependencies
        
        about_dialog = AboutDialog(self.window)
        # Connect the successful password entry to our unlock method
        about_dialog.admin_unlocked.connect(self._enable_admin_mode)
        about_dialog.exec()

    def _enable_admin_mode(self) -> None:
        """Reveals the deletion UI and updates the session state."""
        self.window.btn_delete.setVisible(True)
        self.window.status.showMessage("Admin Mode Unlocked: Deletion enabled.", 4000)
        
    def delete_selected(self) -> None:
        """Placeholder for the deletion logic. Verifies intent before routing to S3."""
        selected_files = self.window.file_browser.get_selected_files_with_size()
        if not selected_files:
            self.window.status.showMessage("No files selected for deletion.")
            return
            
        reply = QMessageBox.warning(
            self.window, 
            "Confirm Deletion", 
            f"Are you sure you want to permanently delete {len(selected_files)} file(s)?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # We will build the DeleteWorker next!
            self.window.status.showMessage("Deletion feature pending worker implementation...")