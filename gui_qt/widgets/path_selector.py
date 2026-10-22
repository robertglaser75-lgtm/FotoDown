"""Path and organization configuration widget."""

from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from core.config import AppConfig


class PathSelectorWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # 1. Source Dir
        lbl_source = QLabel("Quellordner / SD-Karte:")
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Pfad zum Quellordner oder DCIM...")
        self.edit_source.textChanged.connect(lambda *args: self.changed.emit())

        btn_browse_source = QPushButton("Durchsuchen...")
        btn_browse_source.setObjectName("secondaryBtn")
        btn_browse_source.clicked.connect(self._browse_source)

        grid.addWidget(lbl_source, 0, 0)
        grid.addWidget(self.edit_source, 0, 1)
        grid.addWidget(btn_browse_source, 0, 2)

        # 2. Target Dir
        lbl_target = QLabel("Zielordner Fotos:")
        self.edit_target = QLineEdit()
        self.edit_target.setPlaceholderText("Zielverzeichnis für sortierte Fotos...")
        self.edit_target.textChanged.connect(lambda *args: self.changed.emit())

        btn_browse_target = QPushButton("Durchsuchen...")
        btn_browse_target.setObjectName("secondaryBtn")
        btn_browse_target.clicked.connect(self._browse_target)

        grid.addWidget(lbl_target, 1, 0)
        grid.addWidget(self.edit_target, 1, 1)
        grid.addWidget(btn_browse_target, 1, 2)

        # 3. Video Target Dir
        self.chk_video = QCheckBox("Separater Zielordner für Videos:")
        self.chk_video.toggled.connect(self._on_video_toggled)

        self.edit_video_target = QLineEdit()
        self.edit_video_target.setPlaceholderText("Zielverzeichnis für Videos...")
        self.edit_video_target.setEnabled(False)
        self.edit_video_target.textChanged.connect(lambda *args: self.changed.emit())

        self.btn_browse_video = QPushButton("Durchsuchen...")
        self.btn_browse_video.setObjectName("secondaryBtn")
        self.btn_browse_video.setEnabled(False)
        self.btn_browse_video.clicked.connect(self._browse_video)

        grid.addWidget(self.chk_video, 2, 0)
        grid.addWidget(self.edit_video_target, 2, 1)
        grid.addWidget(self.btn_browse_video, 2, 2)

        layout.addLayout(grid)

        # 4. JPG & RAW Organization mode
        org_box = QHBoxLayout()
        org_box.setSpacing(16)
        lbl_org = QLabel("JPG/RAW-Ablage:")
        org_box.addWidget(lbl_org)

        self.btn_group_org = QButtonGroup(self)
        self.rb_same = QRadioButton("Alle gemeinsam in einem Ordner")
        self.rb_sub = QRadioButton("Unterordner (.../JPG und .../RAW)")
        self.rb_parent = QRadioButton("Hauptordner (JPG/... und RAW/...)")

        self.btn_group_org.addButton(self.rb_same, 0)
        self.btn_group_org.addButton(self.rb_sub, 1)
        self.btn_group_org.addButton(self.rb_parent, 2)
        self.rb_same.setChecked(True)

        self.btn_group_org.idToggled.connect(lambda *args: self.changed.emit())

        org_box.addWidget(self.rb_same)
        org_box.addWidget(self.rb_sub)
        org_box.addWidget(self.rb_parent)
        org_box.addStretch()

        layout.addLayout(org_box)

        # 5. Only new files check (use && to prevent mnemonic stripping of &)
        self.chk_only_new = QCheckBox("Nur neue Fotos && Videos importieren (Duplikate automatisch überspringen)")
        self.chk_only_new.setChecked(True)
        self.chk_only_new.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_only_new)

    def _browse_source(self):
        curr = self.edit_source.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Quellordner wählen", curr)
        if folder:
            self.edit_source.setText(folder)

    def _browse_target(self):
        curr = self.edit_target.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Zielordner wählen", curr)
        if folder:
            self.edit_target.setText(folder)

    def _browse_video(self):
        curr = self.edit_video_target.text().strip() or self.edit_target.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Video-Zielordner wählen", curr)
        if folder:
            self.edit_video_target.setText(folder)

    def _on_video_toggled(self, checked: bool):
        self.edit_video_target.setEnabled(checked)
        self.btn_browse_video.setEnabled(checked)
        self.changed.emit()

    def get_type_org(self) -> str:
        sel_id = self.btn_group_org.checkedId()
        if sel_id == 1:
            return "subfolders"
        elif sel_id == 2:
            return "parent_folders"
        return "same"

    def set_type_org(self, val: str):
        if val == "subfolders":
            self.rb_sub.setChecked(True)
        elif val == "parent_folders":
            self.rb_parent.setChecked(True)
        else:
            self.rb_same.setChecked(True)

    def load_config(self, config: AppConfig):
        self.edit_source.setText(config.source_dir)
        self.edit_target.setText(config.target_dir)
        self.chk_video.setChecked(config.separate_video_dir)
        self.edit_video_target.setText(config.video_target_dir)
        self.set_type_org(config.type_folder_organization)
        self.chk_only_new.setChecked(config.only_new_files)

    def sync_to_config(self, config: AppConfig):
        config.source_dir = self.edit_source.text().strip()
        config.target_dir = self.edit_target.text().strip()
        config.separate_video_dir = self.chk_video.isChecked()
        config.video_target_dir = self.edit_video_target.text().strip()
        config.type_folder_organization = self.get_type_org()
        config.only_new_files = self.chk_only_new.isChecked()
