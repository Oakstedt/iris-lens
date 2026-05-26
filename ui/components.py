import os
from typing import List, Tuple, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QTreeWidget, 
    QTreeWidgetItem, 
    QHeaderView, 
    QTreeWidgetItemIterator,
    QDialog, 
    QVBoxLayout, 
    QLabel, 
    QInputDialog, 
    QLineEdit, 
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from PyQt6.QtGui import QPainter, QPixmap, QPaintEvent


class FileTreeItem(QTreeWidgetItem):
    """
    Custom tree item that overrides default string sorting.
    
    Allows columns displaying formatted strings (like "2 GB") to be sorted 
    numerically by their underlying raw data (e.g., total bytes).
    """
    
    def __lt__(self, other: QTreeWidgetItem) -> bool:
        column = self.treeWidget().sortColumn()
        
        # Column 1 is the 'Size' column
        if column == 1:
            # Extract the raw bytes stored in the hidden UserRole
            my_size = self.data(1, Qt.ItemDataRole.UserRole)
            other_size = other.data(1, Qt.ItemDataRole.UserRole)
            
            # Fallback to 0 to prevent crashes if data is somehow missing
            my_size = float(my_size) if my_size is not None else 0.0
            other_size = float(other_size) if other_size is not None else 0.0
            
            return my_size < other_size
            
        # Fall back to standard alphabetical sorting for Name, Type, and Date
        return super().__lt__(other)


class FileBrowserTree(QTreeWidget):
    """
    A custom QTreeWidget for displaying S3 file hierarchies.
    
    Handles custom painting for a background watermark, human-readable file 
    size formatting, recursive folder size calculations, and search filtering.
    """

    def __init__(self, parent: Optional[Any] = None) -> None:
        """Initializes the tree widget with headers, settings, and the watermark."""
        super().__init__(parent)
        
        self.setHeaderLabels(["Name", "Size", "Type", "Last Modified"])
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        
        # Configure column resize behavior
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Name stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Date
        
        self.itemChanged.connect(self.on_item_changed)
        self._blocking_signals = False

        # Load the background watermark
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assets_path = os.path.join(base_dir, "assets", "watermark.png")
        
        self.watermark_pixmap = QPixmap(assets_path)
        self.watermark_opacity = 0.10  

        # Force a viewport repaint during scrolling to prevent watermark tearing
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Overrides the default paint event to draw a static watermark 
        behind the tree items.
        """
        super().paintEvent(event)

        if not self.watermark_pixmap.isNull():
            painter = QPainter(self.viewport())
            painter.setOpacity(self.watermark_opacity)
            
            target_w = 256
            target_h = 256
            
            x_pos = self.viewport().width() - target_w - 20
            y_pos = self.viewport().height() - target_h - 20
            
            if x_pos > 0 and y_pos > 0:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(x_pos, y_pos, target_w, target_h, self.watermark_pixmap)
            
            painter.end()

    def format_size(self, size_bytes: int) -> str:
        """
        Converts raw bytes into a human-readable string.
        """
        if size_bytes == 0:
            return "0 B"
        
        tb = 1099511627776
        gb = 1073741824
        mb = 1048576
        kb = 1024
        
        if size_bytes >= tb:
            return f"{size_bytes / tb:.2f} TB"
        elif size_bytes >= gb:
            return f"{size_bytes / gb:.2f} GB"
        elif size_bytes >= mb:
            return f"{size_bytes / mb:.2f} MB"
        elif size_bytes >= kb:
            return f"{size_bytes / kb:.2f} KB"
        else:
            return f"{size_bytes} B"

    def populate_files(self, files: List[Tuple]) -> None:
        """
        Builds the directory tree structure from a flat list of S3 object keys.
        """
        self.clear()
        self.setSortingEnabled(False)
        
        self.dir_cache: Dict[str, FileTreeItem] = {} 
        folder_sizes: Dict[str, int] = {}

        for file_data in files:
            if len(file_data) == 6:
                name, size_str, ftype, date, raw_key, raw_bytes = file_data
            elif len(file_data) == 5:
                name, size_str, ftype, date, raw_key = file_data
                raw_bytes = 0 
            else:
                continue

            # Identify if this item is a 0-byte folder marker
            is_folder_marker = raw_key.endswith('/')

            if is_folder_marker:
                # Safely split without creating an empty filename at the end
                path_parts = [p for p in raw_key.split('/') if p]
                filename = ""
            else:
                parts = raw_key.split('/')
                filename = parts[-1]
                path_parts = parts[:-1]
            
            parent_node = self.invisibleRootItem()
            current_path = ""
            
            # Construct folder nodes using the custom FileTreeItem
            for folder in path_parts:
                current_path = f"{current_path}/{folder}" if current_path else folder
                
                folder_sizes[current_path] = folder_sizes.get(current_path, 0) + raw_bytes
                
                if current_path in self.dir_cache:
                    parent_node = self.dir_cache[current_path]
                else:
                    new_folder = FileTreeItem(parent_node)
                    new_folder.setText(0, folder)
                    new_folder.setText(2, "Folder")
                    
                    # Store the explicit S3 folder marker key
                    new_folder.setData(0, Qt.ItemDataRole.UserRole, current_path + "/")
                    
                    new_folder.setFlags(
                        Qt.ItemFlag.ItemIsUserCheckable | 
                        Qt.ItemFlag.ItemIsEnabled | 
                        Qt.ItemFlag.ItemIsAutoTristate
                    )
                    new_folder.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    self.dir_cache[current_path] = new_folder
                    parent_node = new_folder

            # If this was purely an S3 folder marker, stop here.
            # Do not proceed to build a blank file node underneath it.
            if is_folder_marker:
                continue

            # Construct file nodes using the custom FileTreeItem
            file_item = FileTreeItem(parent_node)
            file_item.setText(0, filename)
            file_item.setText(1, self.format_size(raw_bytes)) 
            file_item.setText(2, ftype)
            file_item.setText(3, date)
            
            file_item.setData(0, Qt.ItemDataRole.UserRole, raw_key)
            file_item.setData(1, Qt.ItemDataRole.UserRole, raw_bytes)
            
            file_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            file_item.setCheckState(0, Qt.CheckState.Unchecked)

        # Apply the accumulated sizes back to the folder nodes
        for path, total_bytes in folder_sizes.items():
            if path in self.dir_cache:
                folder_item = self.dir_cache[path]
                folder_item.setText(1, self.format_size(total_bytes))
                folder_item.setData(1, Qt.ItemDataRole.UserRole, total_bytes)

        self.setSortingEnabled(True)

    def on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handles state changes triggered by user interaction (e.g., checkboxes)."""
        pass

    def get_selected_file_keys(self) -> List[str]:
        """Retrieves the raw S3 keys for all explicitly checked file items."""
        selected_keys = []
        iterator = QTreeWidgetItemIterator(self, QTreeWidgetItemIterator.IteratorFlag.Checked)
        
        while iterator.value():
            item = iterator.value()
            raw_key = item.data(0, Qt.ItemDataRole.UserRole)
            
            if raw_key: 
                selected_keys.append(raw_key)
                
            iterator += 1
            
        return selected_keys

    def get_selected_files_with_size(self) -> List[Tuple[str, int]]:
        """Retrieves the metadata required for download operations."""
        selected_files = []
        iterator = QTreeWidgetItemIterator(self, QTreeWidgetItemIterator.IteratorFlag.Checked)
        
        while iterator.value():
            item = iterator.value()
            raw_key = item.data(0, Qt.ItemDataRole.UserRole)
            raw_size = item.data(1, Qt.ItemDataRole.UserRole)
            
            # [FIX] Explicitly ignore folder markers (keys ending with '/') for downloads
            if raw_key and raw_size is not None and not str(raw_key).endswith('/'):
                selected_files.append((raw_key, raw_size))
                
            iterator += 1
            
        return selected_files

    def filter_items(self, text: str) -> None:
        """Filters the tree visually based on a search string."""
        search_text = text.lower()
        
        def check_node(item: QTreeWidgetItem) -> bool:
            child_matched = False
            
            for i in range(item.childCount()):
                if check_node(item.child(i)):
                    child_matched = True

            name = item.text(0).lower()
            match = search_text in name
            should_show = match or child_matched
            
            item.setHidden(not should_show)
            
            if child_matched:
                item.setExpanded(True)
                
            return should_show

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            check_node(root.child(i))

class AboutDialog(QDialog):
    """
    Displays application information and contains a hidden admin unlock mechanism.
    
    A user clicking the version label 5 times rapidly will trigger a password 
    prompt. Successful entry emits the admin_unlocked signal.
    """
    
    admin_unlocked = pyqtSignal()

    def __init__(self, parent: Optional[Any] = None) -> None:
        """Initializes the About dialog and the hidden click timer."""
        super().__init__(parent)
        self.setWindowTitle("About Iris Lens")
        self.setFixedSize(300, 150)

        self._click_count = 0
        self._click_timer = QTimer(self)
        self._click_timer.setInterval(2000)  # 2 seconds to complete 5 clicks
        self._click_timer.timeout.connect(self._reset_clicks)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Constructs the visual elements of the dialog."""
        layout = QVBoxLayout(self)

        title_label = QLabel("Iris Lens")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # The secret trigger label
        self.version_label = QLabel("Version 1.3")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.mousePressEvent = self._on_version_clicked

        author_label = QLabel("Developed by GM\nConnected to HCP S3")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(self.version_label)
        layout.addWidget(author_label)

    def _on_version_clicked(self, event: Any) -> None:
        """Handles the hidden click counter logic."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Start the timer on the very first click
            if self._click_count == 0:
                self._click_timer.start()

            self._click_count += 1

            # Trigger the prompt if the threshold is met
            if self._click_count >= 5:
                self._click_timer.stop()
                self._prompt_admin_password()
                self._reset_clicks()

    def _reset_clicks(self) -> None:
        """Resets the hidden click counter and stops the timer."""
        self._click_count = 0
        self._click_timer.stop()

    def _prompt_admin_password(self) -> None:
        """Triggers the password dialog upon successful click sequence."""
        password, ok = QInputDialog.getText(
            self, 
            "Admin Access", 
            "Enter Override Passphrase:", 
            QLineEdit.EchoMode.Password
        )

        if ok and password == "510715": 
            self.admin_unlocked.emit()
            self.accept()  # Close the about dialog on success
        elif ok:
            QMessageBox.warning(self, "Access Denied", "Incorrect passphrase.")