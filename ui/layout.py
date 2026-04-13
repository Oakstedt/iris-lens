import os
from typing import Any

from PyQt6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout, 
    QComboBox, 
    QPushButton, 
    QLabel, 
    QStatusBar, 
    QProgressBar, 
    QLineEdit
)
from PyQt6.QtGui import QIcon

# Internal component imports
from .components import FileBrowserTree


class MainWindowLayout:
    """
    Handles the visual arrangement of widgets for the Main Window.
    
    Dynamically constructs the UI and injects the widget references directly 
    into the provided main window instance for downstream action routing.
    """

    def setup_ui(self, window: Any) -> None:
        """
        Initializes layout components and attaches them to the window.
        
        Args:
            window: The primary MainWindow instance.
        """
        # 1. Central Widget & Main Layout Hierarchy
        window.central_widget = QWidget()
        window.setCentralWidget(window.central_widget)
        window.layout = QVBoxLayout(window.central_widget)

        # 2. Connection Warning Banner (Hidden by default)
        window.warning_label = QLabel("No Credentials Linked")
        window.warning_label.setStyleSheet(
            "color: red; font-weight: bold; background: #ffe6e6; "
            "padding: 10px; border-radius: 5px;"
        )
        window.layout.addWidget(window.warning_label)

        # 3. Tenant Connection Status
        window.lbl_tenant = QLabel("Connected to Tenant: None")
        window.lbl_tenant.setStyleSheet("color: gray; margin-bottom: 2px;")
        window.layout.addWidget(window.lbl_tenant)

        # 4. Navigation & Bucket Selection Bar
        nav_layout = QHBoxLayout()
        window.bucket_combo = QComboBox()
        window.btn_read = QPushButton("Read Bucket")
        
        nav_layout.addWidget(QLabel("HCP Bucket:"))
        nav_layout.addWidget(window.bucket_combo, 1)  # Stretch factor 1 allows combo box to expand
        nav_layout.addWidget(window.btn_read)
        window.layout.addLayout(nav_layout)

        # 5. Local Search/Filter Bar
        window.search_input = QLineEdit()
        window.search_input.setPlaceholderText("Filter displayed files...")
        window.layout.addWidget(window.search_input)

        # 6. Primary Data View (Custom QTreeWidget)
        window.file_browser = FileBrowserTree()
        window.layout.addWidget(window.file_browser)

        # 7. Bottom Action Bar (Upload/Download)
        action_layout = QHBoxLayout()
        window.btn_upload = QPushButton("Upload File...")
        window.btn_download = QPushButton("Download Selected")
        
        action_layout.addWidget(window.btn_upload)
        action_layout.addWidget(window.btn_download)
        window.layout.addLayout(action_layout)

        # 8. Status Bar & Embedded Progress Indicator
        window.status = QStatusBar()
        window.setStatusBar(window.status)

        window.progress_bar = QProgressBar()
        window.progress_bar.setMaximumWidth(200)
        window.progress_bar.setVisible(False)
        window.status.addPermanentWidget(window.progress_bar)

    def setup_menu(self, window: Any) -> None:
        """
        Initializes the top menu bar and its associated actions.
        
        Args:
            window: The primary MainWindow instance.
        """
        menu = window.menuBar().addMenu("File")
        
        # Credentials linking action
        window.action_link = menu.addAction("Link Credentials File...")
        
        # Application exit action
        window.action_exit = menu.addAction("Exit")
        window.action_exit.triggered.connect(window.close)