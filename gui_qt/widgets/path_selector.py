"""Path and storage target configuration widget with vertical form layout, dual backup and storage bars."""

from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from core.config import AppConfig
from .storage_bar import StorageBarWidget


class PathSelectorWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # 1. Source Dir Section
        lbl_source = QLabel("\U0001F4C1 Quellordner / SD-Karte:")
        lbl_source.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_source)

        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Pfad zum Quellordner oder DCIM...")
        self.edit_source.textChanged.connect(self._on_source_text_changed)
        source_row.addWidget(self.edit_source, stretch=1)

        btn_browse_source = QPushButton("\U0001F4C2 Durchsuchen")
        btn_browse_source.setObjectName("secondaryBtn")
        btn_browse_source.clicked.connect(self._browse_source)
        source_row.addWidget(btn_browse_source)
        layout.addLayout(source_row)

        self.source_storage_bar = StorageBarWidget("Speicherplatz Quelle (SD-Karte / Ordner)")
        layout.addWidget(self.source_storage_bar)

        layout.addSpacing(4)

        # 2. Target Dir Section
        lbl_target = QLabel("\U0001F3AF Zielordner Fotos:")
        lbl_target.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_target)

        target_row = QHBoxLayout()
        target_row.setSpacing(6)
        self.edit_target = QLineEdit()
        self.edit_target.setPlaceholderText("Zielverzeichnis für sortierte Fotos...")
        self.edit_target.textChanged.connect(self._on_target_text_changed)
        target_row.addWidget(self.edit_target, stretch=1)

        btn_browse_target = QPushButton("\U0001F4C2 Durchsuchen")
        btn_browse_target.setObjectName("secondaryBtn")
        btn_browse_target.clicked.connect(self._browse_target)
        target_row.addWidget(btn_browse_target)
        layout.addLayout(target_row)

        self.target_storage_bar = StorageBarWidget("Speicherplatz Ziel-Festplatte")
        layout.addWidget(self.target_storage_bar)

        layout.addSpacing(4)

        # 3. Dual-Backup Target Section (Parallel Backup)
        self.chk_dual_backup = QCheckBox("\U0001F6E1 Gleichzeitig 2. Backup erstellen (NAS/Festplatte)")
        self.chk_dual_backup.setToolTip("Gleichzeitige Sicherung auf ein zweites Ziel (z.B. NAS oder externe Festplatte)")
        self.chk_dual_backup.toggled.connect(self._on_dual_backup_toggled)
        layout.addWidget(self.chk_dual_backup)

        backup_row = QHBoxLayout()
        backup_row.setSpacing(6)
        self.edit_backup_target = QLineEdit()
        self.edit_backup_target.setPlaceholderText("Pfad zum 2. Sicherungsziel (z.B. NAS)...")
        self.edit_backup_target.setEnabled(False)
        self.edit_backup_target.textChanged.connect(self._on_backup_text_changed)
        backup_row.addWidget(self.edit_backup_target, stretch=1)

        self.btn_browse_backup = QPushButton("\U0001F4C2 Durchsuchen")
        self.btn_browse_backup.setObjectName("secondaryBtn")
        self.btn_browse_backup.setEnabled(False)
        self.btn_browse_backup.clicked.connect(self._browse_backup)
        backup_row.addWidget(self.btn_browse_backup)
        layout.addLayout(backup_row)

        self.backup_storage_bar = StorageBarWidget("Speicherplatz 2. Backup-Ziel")
        self.backup_storage_bar.setVisible(False)
        layout.addWidget(self.backup_storage_bar)

        layout.addSpacing(4)

        # 4. Video Target Dir Section
        self.chk_video = QCheckBox("Separater Zielordner für Videos")
        self.chk_video.toggled.connect(self._on_video_toggled)
        layout.addWidget(self.chk_video)

        video_row = QHBoxLayout()
        video_row.setSpacing(6)
        self.edit_video_target = QLineEdit()
        self.edit_video_target.setPlaceholderText("Zielverzeichnis für Videos...")
        self.edit_video_target.setEnabled(False)
        video_row.addWidget(self.edit_video_target, stretch=1)

        self.btn_browse_video = QPushButton("\U0001F4C2 Durchsuchen")
        self.btn_browse_video.setObjectName("secondaryBtn")
        self.btn_browse_video.setEnabled(False)
        self.btn_browse_video.clicked.connect(self._browse_video)
        video_row.addWidget(self.btn_browse_video)
        layout.addLayout(video_row)

    def _on_source_text_changed(self, text: str):
        self.source_storage_bar.set_path(text)
        self.changed.emit()

    def _on_target_text_changed(self, text: str):
        self.target_storage_bar.set_path(text)
        self.changed.emit()

    def _on_backup_text_changed(self, text: str):
        self.backup_storage_bar.set_path(text)
        self.changed.emit()

    def _on_dual_backup_toggled(self, checked: bool):
        self.edit_backup_target.setEnabled(checked)
        self.btn_browse_backup.setEnabled(checked)
        self.backup_storage_bar.setVisible(checked)
        if checked:
            self.backup_storage_bar.set_path(self.edit_backup_target.text().strip())
        self.changed.emit()

    def check_capacity(self, required_bytes: int) -> Tuple[bool, str]:
        """Validates if primary target (and optional backup) have sufficient space for import items."""
        ok_prim, msg_prim = self.target_storage_bar.check_capacity(required_bytes)
        if not ok_prim:
            return False, f"Hauptziel: {msg_prim}"

        if self.chk_dual_backup.isChecked():
            ok_bk, msg_bk = self.backup_storage_bar.check_capacity(required_bytes)
            if not ok_bk:
                return False, f"Backup-Ziel: {msg_bk}"

        return True, msg_prim

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

    def _browse_backup(self):
        curr = self.edit_backup_target.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "2. Sicherungsziel (Backup) wählen", curr)
        if folder:
            self.edit_backup_target.setText(folder)

    def _browse_video(self):
        curr = self.edit_video_target.text().strip() or self.edit_target.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Video-Zielordner wählen", curr)
        if folder:
            self.edit_video_target.setText(folder)

    def _on_video_toggled(self, checked: bool):
        self.edit_video_target.setEnabled(checked)
        self.btn_browse_video.setEnabled(checked)
        self.changed.emit()

    def load_config(self, config: AppConfig):
        self.edit_source.blockSignals(True)
        self.edit_target.blockSignals(True)
        self.chk_dual_backup.blockSignals(True)
        self.edit_backup_target.blockSignals(True)
        self.chk_video.blockSignals(True)
        self.edit_video_target.blockSignals(True)
        try:
            self.edit_source.setText(config.source_dir)
            self.edit_target.setText(config.target_dir)
            self.chk_dual_backup.setChecked(config.enable_dual_backup)
            self.edit_backup_target.setText(config.backup_target_dir)
            self.edit_backup_target.setEnabled(config.enable_dual_backup)
            self.btn_browse_backup.setEnabled(config.enable_dual_backup)
            self.backup_storage_bar.setVisible(config.enable_dual_backup)
            self.chk_video.setChecked(config.separate_video_dir)
            self.edit_video_target.setText(config.video_target_dir)
            # Update storage bars
            self.source_storage_bar.set_path(config.source_dir)
            self.target_storage_bar.set_path(config.target_dir)
            if config.enable_dual_backup:
                self.backup_storage_bar.set_path(config.backup_target_dir)
        finally:
            self.edit_source.blockSignals(False)
            self.edit_target.blockSignals(False)
            self.chk_dual_backup.blockSignals(False)
            self.edit_backup_target.blockSignals(False)
            self.chk_video.blockSignals(False)
            self.edit_video_target.blockSignals(False)

    def sync_to_config(self, config: AppConfig):
        config.source_dir = self.edit_source.text().strip()
        config.target_dir = self.edit_target.text().strip()
        config.enable_dual_backup = self.chk_dual_backup.isChecked()
        config.backup_target_dir = self.edit_backup_target.text().strip()
        config.separate_video_dir = self.chk_video.isChecked()
        config.video_target_dir = self.edit_video_target.text().strip()
