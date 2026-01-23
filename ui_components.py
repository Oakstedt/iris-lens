import os
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView, QTreeWidgetItemIterator
from PyQt6.QtCore import Qt
# NEW: Imports for the watermark painting
from PyQt6.QtGui import QPainter, QPixmap

class FileBrowserTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Name", "Size", "Type", "Last Modified"])
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        
        # Configure Header
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          # Name stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Date
        
        # Connect item changed signal for "Select All Children" logic
        self.itemChanged.connect(self.on_item_changed)
        self._blocking_signals = False

        # --- WATERMARK SETUP ---
        # Loading 'watermark.png' from the assets folder
        self.watermark_pixmap = QPixmap(os.path.join("assets", "watermark.png"))
        self.watermark_opacity = 0.10  # 10% Opacity (Subtle)

        # --- THE FIX: Force repaint on scroll ---
        # This prevents the watermark from artifacting/segmenting during scrolling
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)


    # --- PAINT EVENT (UNCHANGED) ---
    def paintEvent(self, event):
        """ 
        Overriding the paint event to draw the watermark 
        BEHIND or ON TOP of the standard tree items.
        """
        # 1. Draw the standard tree widget stuff first
        super().paintEvent(event)

        # 2. Draw the Watermark
        if not self.watermark_pixmap.isNull():
            painter = QPainter(self.viewport())
            painter.setOpacity(self.watermark_opacity)
            
            # Dimensions: Fix it to 256x256 or scale it
            target_w = 256
            target_h = 256
            
            # Position: Bottom Right with 20px padding
            x_pos = self.viewport().width() - target_w - 20
            y_pos = self.viewport().height() - target_h - 20
            
            if x_pos > 0 and y_pos > 0:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(x_pos, y_pos, target_w, target_h, self.watermark_pixmap)
            
            painter.end()

    # ... rest of the class (populate_files, etc.) remains the same ...
    def populate_files(self, files):
        """
        Parses list of tuples: (name, size_str, type, date, raw_key, raw_bytes)
        Builds a directory tree and calculates folder sizes.
        """
        self.clear()
        self.setSortingEnabled(False)
        
        self.dir_cache = {} 
        
        # Helper dictionary to track raw byte totals for folders
        # Key: Folder Path string, Value: Total Bytes (int)
        folder_sizes = {}

        for file_data in files:
            # 1. Unpack Data (Handle both old 5-item and new 6-item tuples safely)
            if len(file_data) == 6:
                name, size_str, ftype, date, raw_key, raw_bytes = file_data
            elif len(file_data) == 5:
                name, size_str, ftype, date, raw_key = file_data
                raw_bytes = 0 # Fallback
            else:
                continue

            # 2. Build Tree Nodes
            parts = raw_key.split('/')
            filename = parts[-1]
            path_parts = parts[:-1]
            
            parent_node = self.invisibleRootItem()
            current_path = ""
            
            for folder in path_parts:
                current_path = f"{current_path}/{folder}" if current_path else folder
                
                # Update Size Accumulator for this folder path
                folder_sizes[current_path] = folder_sizes.get(current_path, 0) + raw_bytes
                
                if current_path in self.dir_cache:
                    parent_node = self.dir_cache[current_path]
                else:
                    new_folder = QTreeWidgetItem(parent_node)
                    new_folder.setText(0, folder)
                    new_folder.setText(2, "Folder")
                    new_folder.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsAutoTristate)
                    new_folder.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    self.dir_cache[current_path] = new_folder
                    parent_node = new_folder

            # 3. Add File Node
            file_item = QTreeWidgetItem(parent_node)
            file_item.setText(0, filename)
            file_item.setText(1, size_str) # File size is already formatted
            file_item.setText(2, ftype)
            file_item.setText(3, date)
            file_item.setData(0, Qt.ItemDataRole.UserRole, raw_key)
            file_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            file_item.setCheckState(0, Qt.CheckState.Unchecked)

        # 4. Update Folder Size Columns
        # Now that the tree is built, go back and set the calculated sizes
        for path, total_bytes in folder_sizes.items():
            if path in self.dir_cache:
                folder_item = self.dir_cache[path]
                
                # Format the size
                if total_bytes > 1024 * 1024: fmt_size = f"{total_bytes / (1024 * 1024):.2f} MB"
                elif total_bytes > 1024: fmt_size = f"{total_bytes / 1024:.2f} KB"
                else: fmt_size = f"{total_bytes} B"
                
                folder_item.setText(1, fmt_size)

        self.setSortingEnabled(True)

    def on_item_changed(self, item, column):
        """ Optional: Logic to handle parent/child checkbox syncing can go here """
        pass

    def get_selected_file_keys(self):
        """ Returns the raw keys of all Checked files (leaves). """
        selected_keys = []
        
        # Iterate all items using an iterator
        iterator = QTreeWidgetItemIterator(self, QTreeWidgetItemIterator.IteratorFlag.Checked)
        while iterator.value():
            item = iterator.value()
            
            # Only collect items that have a raw_key (Files), ignore Folders
            raw_key = item.data(0, Qt.ItemDataRole.UserRole)
            if raw_key: 
                selected_keys.append(raw_key)
                
            iterator += 1
            
        return selected_keys

    def filter_items(self, text):
        """ 
        Hides nodes that don't match the text. 
        Shows parents if a child matches.
        """
        search_text = text.lower()
        
        # Helper to recursively check items
        def check_node(item):
            child_matched = False
            
            # Check children first (bottom-up)
            for i in range(item.childCount()):
                if check_node(item.child(i)):
                    child_matched = True

            # Check self
            name = item.text(0).lower()
            match = search_text in name
            
            # Logic: Show if (Self Matches OR Child Matches)
            should_show = match or child_matched
            item.setHidden(not should_show)
            
            # If a child matched, expand this node so user can see it
            if child_matched:
                item.setExpanded(True)
                
            return should_show

        # Run filter on top-level items
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            check_node(root.child(i))