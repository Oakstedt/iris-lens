import sys
import os
import ctypes

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QIcon

# Internal module imports
from core.session import SessionManager 
from ui.layout import MainWindowLayout
from ui.actions import ActionManager


class MainWindow(QMainWindow):
    """
    The primary application controller for Iris Lens.
    
    Responsible for initializing the S3 session, constructing the UI layout, 
    and delegating user interactions to the ActionManager.
    """
    
    def __init__(self) -> None:
        super().__init__()
        
        # 1. Window Configuration
        self.setWindowTitle("Iris Lens v1.4 - A HCP browser by GM")
        self.setMinimumSize(1100, 700)
        
        icon_path = os.path.join("assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 2. Module Initialization
        self.session = SessionManager()
        self.ui_manager = MainWindowLayout()
        self.actions = ActionManager(self)

        # 3. UI Construction & Signal Binding
        # Note: setup_ui dynamically injects UI components (e.g., self.btn_read) into this instance.
        self.ui_manager.setup_ui(self)
        self.ui_manager.setup_menu(self)
        self._connect_signals()

        # 4. Initial Application State
        self.actions.refresh_state()

    def _connect_signals(self) -> None:
        """Binds UI element events directly to their corresponding ActionManager methods."""
        self.btn_read.clicked.connect(self.actions.read_bucket)
        self.btn_upload.clicked.connect(self.actions.upload)
        self.btn_download.clicked.connect(self.actions.download)
        self.btn_delete.clicked.connect(self.actions.delete_selected)
        self.search_input.textChanged.connect(self.actions.search)
        self.action_link.triggered.connect(self.actions.link_credentials)
        self.action_about.triggered.connect(self.actions.show_about)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Isolate the application in the Windows Taskbar to enforce the custom icon
    if os.name == 'nt':
        try:
            myappid = 'mycompany.iris.lens.v1.2'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception: 
            pass

    app.setStyle("Fusion") 
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())