# ui_components.py
from PyQt6.QtWidgets import QTableWidget, QHeaderView, QTableWidgetItem
from PyQt6.QtCore import Qt

class CheckBoxHeader(QHeaderView):
    """ Custom Header to allow a 'Select All' checkbox in the first column. """
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.isOn = False

    def mousePressEvent(self, event):
        if self.logicalIndexAt(event.pos()) == 0:
            self.isOn = not self.isOn
            self.model().setHeaderData(0, Qt.Orientation.Horizontal, 
                                       "[X]" if self.isOn else "[ ]")
            self.parent().on_header_clicked(self.isOn)
        super().mousePressEvent(event)

class FileBrowserTable(QTableWidget):
    """ A specialized TableWidget for displaying and filtering files. """
    def __init__(self):
        super().__init__()
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["[ ]", "Name", "Size", "Type", "Last Modified"])
        
        # Setup Custom Header
        self.custom_header = CheckBoxHeader(Qt.Orientation.Horizontal, self)
        self.setHorizontalHeader(self.custom_header)
        
        # Column Resizing
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def on_header_clicked(self, is_checked):
        """ Selects or Deselects all visible rows. """
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        self.horizontalHeaderItem(0).setText("[X]" if is_checked else "[ ]")
        
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                self.item(row, 0).setCheckState(new_state)

    def populate_files(self, files):
        """ 
        Expects a list of tuples: (display_name, size, type, date, raw_key) 
        """
        self.setRowCount(0)
        for row_idx, file_data in enumerate(files):
            # Unpack the 5 items (use a default for key if your list is mixed)
            if len(file_data) == 5:
                name, size, ftype, date, raw_key = file_data
            else:
                # Fallback for old 4-item tuples
                name, size, ftype, date = file_data
                raw_key = name

            self.insertRow(row_idx)
            
            # --- COLUMN 0: Checkbox + Name + HIDDEN KEY ---
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            name_item.setCheckState(Qt.CheckState.Unchecked)
            
            # CRITICAL: Store the raw_key hidden in this item
            name_item.setData(Qt.ItemDataRole.UserRole, raw_key)
            
            self.setItem(row_idx, 0, name_item)
            # ----------------------------------------------

            self.setItem(row_idx, 1, QTableWidgetItem(size))
            self.setItem(row_idx, 2, QTableWidgetItem(ftype))
            self.setItem(row_idx, 3, QTableWidgetItem(date))

    def filter_rows(self, query):
        """ Hides rows that don't match the query. """
        query = query.lower()
        for row in range(self.rowCount()):
            item = self.item(row, 1) # Column 1 is Name
            is_visible = query in item.text().lower()
            self.setRowHidden(row, not is_visible)

    def get_selected_file_keys(self):
        """ Returns the hidden RAW KEYS of selected rows, not the display text. """
        selected_keys = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                # Retrieve the hidden raw key
                raw_key = item.data(Qt.ItemDataRole.UserRole)
                selected_keys.append(raw_key)
        return selected_keys