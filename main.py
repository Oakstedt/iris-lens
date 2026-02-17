import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QIcon

# Imports
from core.session import SessionManager 
from ui.layout import MainWindowLayout
from ui.actions import ActionManager

class MainWindow(QMainWindow):
    """ Controller class. Initializes modules and connects signals. """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iris Lens v1.2 - A HCP browser by GM")
        self.setMinimumSize(1100, 700)
        
        icon_path = os.path.join("assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 1. Logic & UI Setup
        self.session = SessionManager()
        self.ui_manager = MainWindowLayout()
        self.ui_manager.setup_ui(self)
        self.ui_manager.setup_menu(self)

        # 2. Handlers Setup (The ActionManager takes over logic)
        self.actions = ActionManager(self)

        # 3. Connect Signals
        self._connect_signals()

        # 4. Start
        self.actions.refresh_state()

    def _connect_signals(self):
        """ Maps UI events to the ActionManager. """
        self.btn_read.clicked.connect(self.actions.read_bucket)
        self.btn_upload.clicked.connect(self.actions.upload)
        self.btn_download.clicked.connect(self.actions.download)
        self.search_input.textChanged.connect(self.actions.search)
        self.action_link.triggered.connect(self.actions.link_credentials)

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