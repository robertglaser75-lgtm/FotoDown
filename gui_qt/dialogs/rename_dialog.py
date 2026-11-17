"""Batch Rename Dialog for FotoDown (Transfer & Archiving Tab).

Allows renaming marked files on either Source or Destination side
using configurable patterns with EXIF placeholders, companion sidecar synchronization,
collision safety, and real-time preview table.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.exif_reader import MediaMetadata, extract_metadata
from core.naming import format_filename, sanitize_filename
from gui_qt.styles.icons import get_search_icon, get_tag_icon
from gui_qt.widgets.paired_header import PairedHeaderView


@dataclass
class RenamePlanItem:
    """Represents a planned file rename operation."""
    original_path: Path
    new_filename: str
    new_path: Path
    metadata: MediaMetadata
    companions: List[Tuple[Path, Path]]  # [(old_path, new_path)]
    status_text: str


class BatchRenameDialog(QDialog):
    """Interactive modal dialog for batch renaming marked files with pattern tags and live preview."""

    renaming_finished = Signal(list)  # Emits list of newly renamed Path objects

    TAGS = [
        ("{YYYY}", "Aufnahmejahr (4-stellig, z. B. 2026)"),
        ("{MM}", "Aufnahmemonat (01-12)"),
        ("{DD}", "Aufnahmetag (01-31)"),
        ("{hh}", "Aufnahmestunde (00-23)"),
        ("{mm}", "Aufnahmeminute (00-59)"),
        ("{ss}", "Aufnahmesekunde (00-59)"),
        ("{camera}", "Kameramodell (z. B. Canon_EOS_R5)"),
        ("{orig_name}", "Bisheriger Dateiname ohne Endung"),
        ("{num:04d}", "Laufende Nummerierung (0001, 0002...)"),
        ("{ext}", "Originale Dateiendung"),
    ]

    def __init__(
        self,
        items: List[Any],
        folder_path: Path,
        config: AppConfig,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.items = items
        self.folder_path = folder_path
        self.config = config
        self.renamed_paths: List[Path] = []
        self._metadata_cache: Dict[str, MediaMetadata] = {}

        self.setWindowTitle("FotoDown - Dateien umbenennen")
        self.resize(840, 620)
        self.setMinimumSize(680, 480)

        self._setup_ui()
        self._preload_metadata()
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 1. Header Banner
        header = QHBoxLayout()
        header.setSpacing(10)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_tag_icon(size=26).pixmap(26, 26))
        header.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Dateien nach Muster umbenennen")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        title_vbox.addWidget(lbl_title)

        count_text = f"<b>{len(self.items)}</b> Datei{'en' if len(self.items) != 1 else ''} in <i>{self.folder_path.name}</i> markiert"
        lbl_sub = QLabel(count_text)
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_vbox.addWidget(lbl_sub)
        header.addLayout(title_vbox)

        header.addStretch()
        layout.addLayout(header)

        # 2. Pattern Configuration Card
        cfg_frame = QFrame()
        cfg_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        cfg_layout = QVBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(12, 10, 12, 10)
        cfg_layout.setSpacing(8)

        # Pattern Input & Start Index
        row_pat = QHBoxLayout()
        row_pat.setSpacing(10)

        lbl_pat = QLabel("Dateinamen-Muster:")
        lbl_pat.setStyleSheet("font-weight: 600; font-size: 12px; color: #f8fafc;")
        row_pat.addWidget(lbl_pat)

        initial_pat = (
            getattr(self.config, "rename_file_pattern", "")
            or getattr(self.config, "file_pattern", "")
            or "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}"
        )
        self.edit_pattern = QLineEdit(initial_pat)
        self.edit_pattern.setPlaceholderText("{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}")
        self.edit_pattern.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                color: #38bdf8;
                font-family: monospace;
                font-weight: 600;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.edit_pattern.textChanged.connect(self._update_preview)
        row_pat.addWidget(self.edit_pattern, 1)

        lbl_start = QLabel("Startnummer:")
        lbl_start.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        row_pat.addWidget(lbl_start)

        self.spin_start_num = QSpinBox()
        self.spin_start_num.setRange(1, 999999)
        self.spin_start_num.setValue(1)
        self.spin_start_num.setStyleSheet("background-color: #1e293b; color: white; padding: 2px 6px; border: 1px solid #334155; border-radius: 4px;")
        self.spin_start_num.valueChanged.connect(self._update_preview)
        row_pat.addWidget(self.spin_start_num)

        cfg_layout.addLayout(row_pat)

        # Tag Chips Bar (2 rows of clickable chips)
        lbl_chips_title = QLabel("Platzhalter anklicken zum Einfügen:")
        lbl_chips_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 500;")
        cfg_layout.addWidget(lbl_chips_title)

        chips_grid = QGridLayout()
        chips_grid.setSpacing(4)
        chips_grid.setContentsMargins(0, 0, 0, 0)
        for i, (tag, tip) in enumerate(self.TAGS):
            btn = QPushButton(tag)
            btn.setObjectName("tagChip")
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 3px;
                    padding: 3px 6px;
                    color: #cbd5e1;
                    font-size: 10px;
                    font-family: monospace;
                }
                QPushButton:hover {
                    background-color: #0284c7;
                    border-color: #38bdf8;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda chk=False, t=tag: self._insert_tag(t))
            chips_grid.addWidget(btn, i // 5, i % 5)

        cfg_layout.addLayout(chips_grid)

        # Options Checkboxes
        opts_row = QHBoxLayout()
        opts_row.setSpacing(16)

        self.chk_sync_companions = QCheckBox("Zugehörige Begleitdateien (.xmp, RAW/JPG) synchron umbenennen")
        self.chk_sync_companions.setChecked(True)
        self.chk_sync_companions.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        self.chk_sync_companions.toggled.connect(self._update_preview)
        opts_row.addWidget(self.chk_sync_companions)

        self.chk_collision_safe = QCheckBox("Kollisionsschutz (_1, _2 bei Namenskonflikten anhängen)")
        self.chk_collision_safe.setChecked(True)
        self.chk_collision_safe.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        self.chk_collision_safe.toggled.connect(self._update_preview)
        opts_row.addWidget(self.chk_collision_safe)

        opts_row.addStretch()
        cfg_layout.addLayout(opts_row)

        layout.addWidget(cfg_frame)

        # 3. Live Preview Table
        lbl_tbl_title = QLabel("Vorschau der Umbenennung:")
        lbl_tbl_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #94a3b8; margin-top: 4px;")
        layout.addWidget(lbl_tbl_title)

        self.table_preview = QTableWidget()
        self.table_preview.setHorizontalHeader(PairedHeaderView(Qt.Orientation.Horizontal, self.table_preview))
        self.table_preview.setColumnCount(3)
        self.table_preview.setHorizontalHeaderLabels(["Alter Dateiname", "Neuer Dateiname", "Status"])
        h = self.table_preview.horizontalHeader()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_preview.setColumnWidth(0, 260)
        self.table_preview.setColumnWidth(1, 320)
        self.table_preview.setColumnWidth(2, 200)
        self.table_preview.setAlternatingRowColors(True)
        self.table_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_preview, 1)

        # 4. Bottom Footer & Action Buttons
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        footer.addWidget(self.lbl_status)

        footer.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton(f"🏷️ Jetzt {len(self.items)} Dateien umbenennen")
        self.btn_apply.setObjectName("primaryBtn")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
                border: 1px solid #38bdf8;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_apply.clicked.connect(self._execute_rename)
        footer.addWidget(self.btn_apply)

        layout.addLayout(footer)

    def _insert_tag(self, tag: str):
        self.edit_pattern.insert(tag)
        self.edit_pattern.setFocus()

    def _preload_metadata(self):
        """Pre-extracts EXIF metadata for all items to keep preview snappy."""
        for it in self.items:
            p = it.path if hasattr(it, "path") else Path(it)
            p_str = str(p)
            if p_str not in self._metadata_cache:
                try:
                    self._metadata_cache[p_str] = extract_metadata(p)
                except Exception:
                    self._metadata_cache[p_str] = MediaMetadata(
                        file_path=p,
                        orig_name=p.stem,
                        extension=p.suffix.lower(),
                        file_size=p.stat().st_size if p.exists() else 0
                    )

    def _calculate_plan(self) -> List[RenamePlanItem]:
        pattern = self.edit_pattern.text().strip() or "{orig_name}"
        start_idx = self.spin_start_num.value()
        sync_companions = self.chk_sync_companions.isChecked()
        collision_safe = self.chk_collision_safe.isChecked()

        plan: List[RenamePlanItem] = []
        claimed_names: Set[str] = set()

        for idx, it in enumerate(self.items):
            p = it.path if hasattr(it, "path") else Path(it)
            meta = self._metadata_cache.get(str(p))
            if not meta:
                meta = MediaMetadata(
                    file_path=p,
                    orig_name=p.stem,
                    extension=p.suffix,
                    file_size=p.stat().st_size if p.exists() else 0
                )

            current_num = start_idx + idx
            new_fname = format_filename(pattern, meta, index=current_num)
            clean_new_stem = Path(new_fname).stem
            ext = p.suffix

            target_new_fname = f"{clean_new_stem}{ext}"
            if collision_safe:
                col_counter = 1
                while (target_new_fname in claimed_names or (self.folder_path / target_new_fname).exists()) and target_new_fname != p.name:
                    target_new_fname = f"{clean_new_stem}_{col_counter}{ext}"
                    col_counter += 1

            claimed_names.add(target_new_fname)
            new_path = self.folder_path / target_new_fname

            # Companions check
            companion_pairs: List[Tuple[Path, Path]] = []
            status_text = "Keine Änderung" if p.name == target_new_fname else "Wird umbenannt"

            if sync_companions:
                new_stem = Path(target_new_fname).stem
                # Check for XMP sidecars
                for sc_candidate in [
                    p.with_name(f"{p.name}.xmp"),
                    p.with_suffix(".xmp")
                ]:
                    if sc_candidate.exists() and sc_candidate != p:
                        new_sc_name = f"{target_new_fname}.xmp" if sc_candidate.name.endswith(f"{p.name}.xmp") else f"{new_stem}.xmp"
                        companion_pairs.append((sc_candidate, self.folder_path / new_sc_name))

                # Check for paired RAW or JPG in same directory
                for cand_ext in [".jpg", ".jpeg", ".cr3", ".cr2", ".nef", ".arw", ".dng"]:
                    if cand_ext != ext:
                        paired_file = p.with_suffix(cand_ext)
                        if paired_file.exists() and paired_file != p:
                            companion_pairs.append((paired_file, self.folder_path / f"{new_stem}{cand_ext}"))

            if companion_pairs:
                ext_names = ", ".join(sorted(set(pair[0].suffix for pair in companion_pairs)))
                status_text += f" (+{len(companion_pairs)} Sidecar{'s' if len(companion_pairs) != 1 else ''}: {ext_names})"

            plan.append(RenamePlanItem(
                original_path=p,
                new_filename=target_new_fname,
                new_path=new_path,
                metadata=meta,
                companions=companion_pairs,
                status_text=status_text
            ))

        return plan

    def _update_preview(self):
        plan = self._calculate_plan()
        self.table_preview.blockSignals(True)
        self.table_preview.setRowCount(len(plan))

        for row, item in enumerate(plan):
            item_old = QTableWidgetItem(item.original_path.name)
            item_new = QTableWidgetItem(item.new_filename)
            item_status = QTableWidgetItem(item.status_text)

            if item.original_path.name == item.new_filename:
                item_new.setForeground(QColor("#94a3b8"))
                item_status.setForeground(QColor("#64748b"))
            else:
                item_new.setForeground(QColor("#38bdf8"))
                item_status.setForeground(QColor("#4ade80"))

            self.table_preview.setItem(row, 0, item_old)
            self.table_preview.setItem(row, 1, item_new)
            self.table_preview.setItem(row, 2, item_status)

        self.table_preview.blockSignals(False)

        changed_count = sum(1 for it in plan if it.original_path.name != it.new_filename)
        self.lbl_status.setText(f"{changed_count} von {len(plan)} Dateien ändern ihren Namen.")

    def _execute_rename(self, show_message: bool = True):
        plan = self._calculate_plan()
        changed_items = [it for it in plan if it.original_path.name != it.new_filename or it.companions]

        if not changed_items:
            if show_message and self.isVisible():
                QMessageBox.information(
                    self,
                    "Keine Änderungen",
                    "Alle Dateien haben bereits den gewünschten Namen."
                )
            self.accept()
            return

        renamed_count = 0
        failed_count = 0
        error_msgs = []
        newly_created_paths: List[Path] = []

        for item in changed_items:
            try:
                # 1. Rename main file
                if item.original_path != item.new_path and item.original_path.exists():
                    os.replace(item.original_path, item.new_path)
                    newly_created_paths.append(item.new_path)
                    renamed_count += 1
                else:
                    newly_created_paths.append(item.original_path)

                # 2. Rename companion files
                for comp_src, comp_dst in item.companions:
                    if comp_src.exists() and comp_src != comp_dst:
                        os.replace(comp_src, comp_dst)
            except Exception as e:
                failed_count += 1
                error_msgs.append(f"{item.original_path.name}: {e}")

        # Save pattern to config
        pat = self.edit_pattern.text().strip()
        if pat:
            self.config.rename_file_pattern = pat
            try:
                self.config.save()
            except Exception:
                pass

        self.renamed_paths = newly_created_paths
        self.renaming_finished.emit(newly_created_paths)

        if show_message and self.isVisible():
            if failed_count == 0:
                QMessageBox.information(
                    self,
                    "Umbenennung erfolgreich",
                    f"✓ {renamed_count} Datei{'en' if renamed_count != 1 else ''} wurde{'n' if renamed_count != 1 else ''} erfolgreich umbenannt."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Teilweise umbenannt",
                    f"{renamed_count} Dateien umbenannt, {failed_count} fehlgeschlagen.\n\n" + "\n".join(error_msgs[:5])
                )

        self.accept()
