"""Pattern editor widget with clickable tag chips and live preview."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.naming import generate_sample_preview


class PatternEditorWidget(QWidget):
    changed = Signal()

    TAGS = [
        ("{YYYY}", "Jahr (4-stellig)"),
        ("{MM}", "Monat (01-12)"),
        ("{DD}", "Tag (01-31)"),
        ("{hh}", "Stunde (00-23)"),
        ("{mm}", "Minute (00-59)"),
        ("{ss}", "Sekunde (00-59)"),
        ("{camera}", "Kameraname"),
        ("{orig_name}", "Originalname"),
        ("{num:04d}", "Nummer (0001...)"),
        ("{ext}", "Dateiendung"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_focused_edit = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # Folder Pattern
        lbl_folder = QLabel("Ordnerstruktur-Muster:")
        self.edit_folder = QLineEdit()
        self.edit_folder.setPlaceholderText("{YYYY}/{YYYY}-{MM}-{DD}")
        self.edit_folder.textChanged.connect(self._on_pattern_changed)
        self.edit_folder.installEventFilter(self)

        grid.addWidget(lbl_folder, 0, 0)
        grid.addWidget(self.edit_folder, 0, 1)

        # File Pattern
        lbl_file = QLabel("Dateinamen-Muster:")
        self.edit_file = QLineEdit()
        self.edit_file.setPlaceholderText("{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}")
        self.edit_file.textChanged.connect(self._on_pattern_changed)
        self.edit_file.installEventFilter(self)

        grid.addWidget(lbl_file, 1, 0)
        grid.addWidget(self.edit_file, 1, 1)

        layout.addLayout(grid)

        # Tag Chips Bar (Organized in compact 2-row grid to maintain responsive sidebar width)
        lbl_tags = QLabel("Platzhalter:")
        lbl_tags.setObjectName("subtleLabel")
        layout.addWidget(lbl_tags)

        tag_grid = QGridLayout()
        tag_grid.setSpacing(4)
        tag_grid.setContentsMargins(0, 0, 0, 0)

        for i, (tag, tip) in enumerate(self.TAGS):
            btn = QPushButton(tag)
            btn.setObjectName("tagChip")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked=False, t=tag: self._insert_tag(t))
            tag_grid.addWidget(btn, i // 5, i % 5)

        layout.addLayout(tag_grid)

        # Live Preview Box
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewBox")
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(12, 8, 12, 8)
        preview_layout.setSpacing(4)

        lbl_prev_title = QLabel("🔍 Live-Vorschau der Umbenennung:")
        lbl_prev_title.setObjectName("previewTitle")
        self.lbl_preview_text = QLabel("")
        self.lbl_preview_text.setObjectName("previewText")
        self.lbl_preview_text.setTextInteractionFlags(self.lbl_preview_text.textInteractionFlags() | self.lbl_preview_text.textInteractionFlags().TextSelectableByMouse)

        preview_layout.addWidget(lbl_prev_title)
        preview_layout.addWidget(self.lbl_preview_text)
        layout.addWidget(self.preview_frame)

        self._last_focused_edit = self.edit_file

    def eventFilter(self, watched, event):
        if event.type() == event.Type.FocusIn:
            if watched in (self.edit_folder, self.edit_file):
                self._last_focused_edit = watched
        return super().eventFilter(watched, event)

    def _insert_tag(self, tag: str):
        target = self._last_focused_edit or self.edit_file
        target.insert(tag)
        target.setFocus()

    def _on_pattern_changed(self, *args):
        self.update_preview()
        self.changed.emit()

    def update_preview(self, type_org: str = "same"):
        f_pat = self.edit_folder.text().strip() or "{YYYY}/{YYYY}-{MM}-{DD}"
        n_pat = self.edit_file.text().strip() or "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}"
        prev_folder, prev_file = generate_sample_preview(
            file_pattern=n_pat,
            folder_pattern=f_pat,
            type_folder_organization=type_org
        )
        self.lbl_preview_text.setText(f"{prev_folder} / {prev_file}")

    def load_config(self, config: AppConfig):
        self.edit_folder.blockSignals(True)
        self.edit_file.blockSignals(True)
        self.edit_folder.setText(config.folder_pattern or "{YYYY}/{YYYY}-{MM}-{DD}")
        self.edit_file.setText(config.file_pattern or "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}")
        self.edit_folder.blockSignals(False)
        self.edit_file.blockSignals(False)
        self.update_preview(config.type_folder_organization)

    def sync_to_config(self, config: AppConfig):
        config.folder_pattern = self.edit_folder.text().strip() or "{YYYY}/{YYYY}-{MM}-{DD}"
        config.file_pattern = self.edit_file.text().strip() or "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}"
