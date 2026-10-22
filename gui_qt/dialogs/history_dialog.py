"""History dialog to inspect and clear previous imports stored in SQLite."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout
)

from core.history import ImportHistory


class HistoryDialog(QDialog):
    def __init__(self, history: ImportHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.setWindowTitle("FotoDown - Import-Historie")
        self.resize(850, 520)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header bar with search and stats
        top_bar = QHBoxLayout()
        self.lbl_stats = QLabel("Lade Historie...")
        self.lbl_stats.setObjectName("subtleLabel")

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("\U0001F50D Historie durchsuchen (Name, Hash)...")
        self.edit_search.textChanged.connect(self._filter_rows)

        top_bar.addWidget(self.lbl_stats)
        top_bar.addStretch()
        top_bar.addWidget(self.edit_search)
        layout.addLayout(top_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Importiert am", "Dateiname", "Originalpfad", "Größe", "SHA256-Hash"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Footer Buttons
        btn_box = QHBoxLayout()
        self.btn_clear = QPushButton("\u2715 Historie leeren")
        self.btn_clear.setObjectName("dangerBtn")
        self.btn_clear.clicked.connect(self._clear_history)

        self.btn_close = QPushButton("Schließen")
        self.btn_close.setObjectName("secondaryBtn")
        self.btn_close.clicked.connect(self.accept)

        btn_box.addWidget(self.btn_clear)
        btn_box.addStretch()
        btn_box.addWidget(self.btn_close)
        layout.addLayout(btn_box)

    def _load_data(self):
        records = self.history.get_all_records()
        self.lbl_stats.setText(f"{len(records)} Einträge in der Duplikat-Datenbank")
        self.table.setRowCount(len(records))

        for row, rec in enumerate(records):
            dt_str = str(rec[4]) if len(rec) > 4 else ""
            fname = str(rec[2]) if len(rec) > 2 else ""
            orig_p = str(rec[5]) if len(rec) > 5 else ""
            fsize = rec[3] if len(rec) > 3 else 0
            fhash = str(rec[1]) if len(rec) > 1 else ""

            size_mb = (fsize or 0) / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB" if size_mb >= 1.0 else f"{(fsize or 0) / 1024:.0f} KB"

            self.table.setItem(row, 0, QTableWidgetItem(dt_str))
            self.table.setItem(row, 1, QTableWidgetItem(fname))
            self.table.setItem(row, 2, QTableWidgetItem(orig_p))
            self.table.setItem(row, 3, QTableWidgetItem(size_str))
            self.table.setItem(row, 4, QTableWidgetItem(fhash[:16] + "..."))

    def _filter_rows(self, text: str):
        query = text.strip().lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and query in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _clear_history(self):
        ret = QMessageBox.question(
            self,
            "Historie leeren?",
            "Möchten Sie die Import-Historie wirklich unwiderruflich löschen?\n"
            "Dadurch werden zuvor importierte Fotos beim nächsten Mal wieder als 'Neu' erkannt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.history.clear_all()
            self._load_data()
            QMessageBox.information(self, "Erfolg", "Die Import-Historie wurde vollständig geleert.")
