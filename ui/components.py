import os
from typing import List, Tuple, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QTreeWidget, 
    QTreeWidgetItem, 
    QHeaderView, 
    QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap, QPaintEvent


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
        # 1. Render the standard tree widget elements
        super().paintEvent(event)

        # 2. Overlay the watermark in the bottom-right corner
        if not self.watermark_pixmap.isNull():
            painter = QPainter(self.viewport())
            painter.setOpacity(self.watermark_opacity)
            
            target_w = 256
            target_h = 256
            
            x_pos = self.viewport().width() - target_w - 20
            y_pos = self.viewport().height() - target_h - 20
            
            # Only draw if the viewport is large enough to contain the watermark
            if x_pos > 0 and y_pos > 0:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(x_pos, y_pos, target_w, target_h, self.watermark_pixmap)
            
            painter.end()

    def format_size(self, size_bytes: int) -> str:
        """
        Converts raw bytes into a human-readable string.
        
        Args:
            size_bytes: The total size in bytes.
            
        Returns:
            A formatted string appending the appropriate unit (B, KB, MB, GB, TB).
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
        
        Calculates cumulative folder sizes bottom-up as it builds the tree.
        
        Args:
            files: A list of tuples containing file metadata. Gracefully handles 
                   both legacy 5-item and modern 6-item tuples.
        """
        self.clear()
        self.setSortingEnabled(False)
        
        self.dir_cache: Dict[str, QTreeWidgetItem] = {} 
        folder_sizes: Dict[str, int] = {}

        for file_data in files:
            # Safely unpack data depending on the payload format
            if len(file_data) == 6:
                name, size_str, ftype, date, raw_key, raw_bytes = file_data
            elif len(file_data) == 5:
                name, size_str, ftype, date, raw_key = file_data
                raw_bytes = 0  # Fallback for legacy data
            else:
                continue

            # Parse the S3 key into folder hierarchy
            parts = raw_key.split('/')
            filename = parts[-1]
            path_parts = parts[:-1]
            
            parent_node = self.invisibleRootItem()
            current_path = ""
            
            # Construct folder nodes
            for folder in path_parts:
                current_path = f"{current_path}/{folder}" if current_path else folder
                
                # Accumulate bytes for the parent folder
                folder_sizes[current_path] = folder_sizes.get(current_path, 0) + raw_bytes
                
                if current_path in self.dir_cache:
                    parent_node = self.dir_cache[current_path]
                else:
                    new_folder = QTreeWidgetItem(parent_node)
                    new_folder.setText(0, folder)
                    new_folder.setText(2, "Folder")
                    new_folder.setFlags(
                        Qt.ItemFlag.ItemIsUserCheckable | 
                        Qt.ItemFlag.ItemIsEnabled | 
                        Qt.ItemFlag.ItemIsAutoTristate
                    )
                    new_folder.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    self.dir_cache[current_path] = new_folder
                    parent_node = new_folder

            # Construct file nodes
            file_item = QTreeWidgetItem(parent_node)
            file_item.setText(0, filename)
            file_item.setText(1, self.format_size(raw_bytes)) 
            file_item.setText(2, ftype)
            file_item.setText(3, date)
            
            # Store hidden metadata for downstream processing (e.g., downloads)
            file_item.setData(0, Qt.ItemDataRole.UserRole, raw_key)
            file_item.setData(1, Qt.ItemDataRole.UserRole, raw_bytes)
            
            file_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            file_item.setCheckState(0, Qt.CheckState.Unchecked)

        # Apply the accumulated sizes back to the folder nodes
        for path, total_bytes in folder_sizes.items():
            if path in self.dir_cache:
                folder_item = self.dir_cache[path]
                folder_item.setText(1, self.format_size(total_bytes))

        self.setSortingEnabled(True)

    def on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handles state changes triggered by user interaction (e.g., checkboxes)."""
        pass

    def get_selected_file_keys(self) -> List[str]:
        """
        Retrieves the raw S3 keys for all explicitly checked file items.
        
        Returns:
            A list of S3 key strings. Ignores folders.
        """
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
        """
        Retrieves the metadata required for download operations.
        
        Returns:
            A list of tuples containing (raw_key, raw_bytes) for checked files.
        """
        selected_files = []
        iterator = QTreeWidgetItemIterator(self, QTreeWidgetItemIterator.IteratorFlag.Checked)
        
        while iterator.value():
            item = iterator.value()
            raw_key = item.data(0, Qt.ItemDataRole.UserRole)
            raw_size = item.data(1, Qt.ItemDataRole.UserRole)
            
            if raw_key and raw_size is not None:
                selected_files.append((raw_key, raw_size))
                
            iterator += 1
            
        return selected_files

    def filter_items(self, text: str) -> None:
        """
        Filters the tree visually based on a search string.
        
        Uses a bottom-up recursive check: a folder remains visible if its name 
        matches, OR if any of its descendants match.
        
        Args:
            text: The search substring to match against file/folder names.
        """
        search_text = text.lower()
        
        def check_node(item: QTreeWidgetItem) -> bool:
            child_matched = False
            
            # Recurse through children first to establish bottom-up visibility
            for i in range(item.childCount()):
                if check_node(item.child(i)):
                    child_matched = True

            name = item.text(0).lower()
            match = search_text in name
            should_show = match or child_matched
            
            item.setHidden(not should_show)
            
            # Automatically expand parent nodes so matching children are visible
            if child_matched:
                item.setExpanded(True)
                
            return should_show

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            check_node(root.child(i))