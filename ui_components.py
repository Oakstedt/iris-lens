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

    def populate_files(self, file_data):
        """ Clears table and fills it with new data. """
        self.setRowCount(0)
        self.setSortingEnabled(False) 
        
        for row_idx, (name, size, ftype, date) in enumerate(file_data):
            self.insertRow(row_idx)
            
            # Checkbox Item
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.setItem(row_idx, 0, chk)
            
            # Data Items
            self.setItem(row_idx, 1, QTableWidgetItem(name))
            self.setItem(row_idx, 2, QTableWidgetItem(size))
            self.setItem(row_idx, 3, QTableWidgetItem(ftype))
            self.setItem(row_idx, 4, QTableWidgetItem(date))
            
        self.setSortingEnabled(True)

    def filter_rows(self, query):
        """ Hides rows that don't match the query. """
        query = query.lower()
        for row in range(self.rowCount()):
            item = self.item(row, 1) # Column 1 is Name
            is_visible = query in item.text().lower()
            self.setRowHidden(row, not is_visible)

    def get_selected_filenames(self):
        selected = []
        for row in range(self.rowCount()):
            if self.item(row, 0).checkState() == Qt.CheckState.Checked:
                selected.append(self.item(row, 1).text())
        return selected