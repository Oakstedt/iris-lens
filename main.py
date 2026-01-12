import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QStatusBar, QFileDialog)
from PyQt6.QtCore import Qt

# Ensure the app can find the bundled NGPIris modules in /src
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Attempt to import the HCP logic from the bundled source
try:
    # Adjusting import based on standard NGPIris structure
    from hcp import HCPHandler 
except ImportError:
    HCPHandler = None

class IrisLensApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGP-Iris Lens")
        self.setMinimumSize(1000, 600)

        # UI Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Top Bar: Bucket Selection
        self.nav_bar = QHBoxLayout()
        self.nav_bar.addWidget(QLabel("HCP Bucket:"))
        self.bucket_dropdown = QComboBox()
        self.nav_bar.addWidget(self.bucket_dropdown, 1)
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.load_hcp_data)
        self.nav_bar.addWidget(self.refresh_btn)
        self.layout.addLayout(self.nav_bar)

        # Middle: File Table
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["Name", "Size", "Type", "Last Modified"])
        self.file_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.file_table)

        # Bottom: Actions
        self.btn_layout = QHBoxLayout()
        self.upload_btn = QPushButton("Upload File...")
        self.upload_btn.clicked.connect(self.open_upload_dialog)
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.open_download_dialog)
        
        self.btn_layout.addWidget(self.upload_btn)
        self.btn_layout.addWidget(self.download_btn)
        self.layout.addLayout(self.btn_layout)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def load_hcp_data(self):
        self.status.showMessage("Querying Hitachi Content Platform...")
        # Future connection logic goes here

    def open_upload_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload", "", "All Files (*)")
        if file_path:
            self.status.showMessage(f"Selected: {os.path.basename(file_path)}")

    def open_download_dialog(self):
        save_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if save_dir:
            self.status.showMessage(f"Target: {save_dir}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = IrisLensApp()
    window.show()
    sys.exit(app.exec())