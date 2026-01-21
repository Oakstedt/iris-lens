from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView
from PyQt6.QtCore import Qt

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

    def populate_files(self, files):
        """
        Parses list of tuples: (name, size, type, date, raw_key)
        Builds a directory tree.
        """
        self.clear()
        self.setSortingEnabled(False) # Disable sorting while building for speed
        
        # Map path strings to TreeItems so we can find parents easily
        # Key: "folder/subfolder", Value: QTreeWidgetItem
        self.dir_cache = {} 

        for file_data in files:
            # Unpack
            if len(file_data) == 5:
                name, size, ftype, date, raw_key = file_data
            else:
                continue # Skip malformed data

            # Split the Raw Key into parts (e.g. "research", "data", "file.txt")
            parts = raw_key.split('/')
            
            # The last part is the file, everything before is the path
            filename = parts[-1]
            path_parts = parts[:-1]
            
            # 1. Find or Create the Parent Folder Node
            parent_node = self.invisibleRootItem() # Default to root
            current_path = ""
            
            for folder in path_parts:
                # Build cumulative path: "research" -> "research/data"
                current_path = f"{current_path}/{folder}" if current_path else folder
                
                if current_path in self.dir_cache:
                    parent_node = self.dir_cache[current_path]
                else:
                    # Create new folder node
                    new_folder = QTreeWidgetItem(parent_node)
                    new_folder.setText(0, folder) # Name
                    new_folder.setText(2, "Folder")
                    new_folder.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsAutoTristate)
                    new_folder.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    self.dir_cache[current_path] = new_folder
                    parent_node = new_folder

            # 2. Add the File Node
            file_item = QTreeWidgetItem(parent_node)
            file_item.setText(0, filename)
            file_item.setText(1, size)
            file_item.setText(2, ftype)
            file_item.setText(3, date)
            
            # Store the Full Raw Key hidden in the item
            file_item.setData(0, Qt.ItemDataRole.UserRole, raw_key)
            
            # Setup Checkbox
            file_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            file_item.setCheckState(0, Qt.CheckState.Unchecked)

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

# Helper import needed inside the class
from PyQt6.QtWidgets import QTreeWidgetItemIterator