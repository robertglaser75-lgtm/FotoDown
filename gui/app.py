"""Modern Tkinter GUI for FotoDown."""

from datetime import datetime
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional

from core.config import AppConfig
from core.drive_detector import detect_drives, DriveInfo
from core.exif_reader import MediaMetadata
from core.history import ImportHistory
from core.importer import ImporterEngine, ScanItem, ImportStats
from core.naming import generate_sample_preview


def set_high_dpi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


class HistoryWindow(tk.Toplevel):
    """Sub-window to inspect and manage import history."""

    def __init__(self, parent, history: ImportHistory, on_cleared=None):
        super().__init__(parent)
        self.title("FotoDown - Download-Historie")
        self.geometry("850x480")
        self.history = history
        self.on_cleared = on_cleared

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_count = ttk.Label(header_frame, text="Einträge geladen...", font=("Segoe UI", 10, "bold"))
        self.lbl_count.pack(side=tk.LEFT)

        btn_clear = ttk.Button(header_frame, text="Historie leeren", command=self._clear_history)
        btn_clear.pack(side=tk.RIGHT)

        # Treeview
        columns = ("orig_name", "date_taken", "destination", "import_date")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("orig_name", text="Originaldatei")
        self.tree.heading("date_taken", text="Aufnahmedatum")
        self.tree.heading("destination", text="Gespeichert unter")
        self.tree.heading("import_date", text="Importiert am")

        self.tree.column("orig_name", width=160, anchor=tk.W)
        self.tree.column("date_taken", width=140, anchor=tk.CENTER)
        self.tree.column("destination", width=360, anchor=tk.W)
        self.tree.column("import_date", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        records = self.history.get_recent_imports(limit=500)
        total_count = self.history.get_count()
        self.lbl_count.config(text=f"Gespeicherte Fotos in Historie: {total_count} (zeigt letzte {len(records)})")

        for r in records:
            dt_taken = r.get("date_taken", "")
            if dt_taken and "T" in dt_taken:
                dt_taken = dt_taken.replace("T", " ")[:19]
            dt_import = r.get("import_timestamp", "")
            if dt_import and "T" in dt_import:
                dt_import = dt_import.replace("T", " ")[:19]

            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.get("orig_filename", ""),
                    dt_taken,
                    r.get("destination_path", ""),
                    dt_import,
                ),
            )

    def _clear_history(self):
        if messagebox.askyesno(
            "Historie leeren",
            "Möchtest du wirklich die gesamte Historie leeren?\n"
            "Dadurch werden alle Fotos bei zukünftigen Scans wieder als 'Neu' erkannt.",
            parent=self
        ):
            self.history.clear_all()
            self._load_data()
            if self.on_cleared:
                self.on_cleared()
            messagebox.showinfo("Erfolg", "Historie wurde erfolgreich geleert.", parent=self)


class FotoDownApp:
    TYPE_ORG_OPTIONS = {
        "same": "Alle Fotos gemeinsam in einem Ordner speichern",
        "subfolders": "Getrennte Unterordner für JPG und RAW (z.B. .../JPG/ und .../RAW/)",
        "parent_folders": "Getrennte Hauptordner für JPG und RAW (z.B. JPG/... und RAW/...)",
    }
    TYPE_ORG_REVERSE = {v: k for k, v in TYPE_ORG_OPTIONS.items()}

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FotoDown - Foto-Importeur & EXIF-Manager")
        self.root.geometry("1150x820")
        self.root.minsize(950, 650)

        # Apply clean styling
        self._setup_styles()

        self.config = AppConfig.load()
        self.history = ImportHistory()
        self.engine = ImporterEngine(self.history)

        self.scan_items: List[ScanItem] = []
        self.cancel_event = threading.Event()
        self.is_busy = False

        self._build_ui()
        self._refresh_drives()
        self._on_toggle_video_dir()
        self._update_preview()
        self._update_history_status_bar()

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except Exception:
            pass

        # Generous Treeview rowheight to ensure characters with descenders ('j', 'g', 'p', 'q', 'y') are fully visible
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=36)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Preview.TLabel", font=("Consolas", 10), foreground="#0055aa")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Top Section: Source and Destination
        self._build_path_section(main_frame)

        # 2. Config Section: Pattern & Options
        self._build_pattern_section(main_frame)

        # 3. Action & Progress Section
        self._build_action_section(main_frame)

        # 4. Table of scanned files
        self._build_table_section(main_frame)

        # 5. Status bar at bottom
        self._build_status_bar(main_frame)

    def _build_path_section(self, parent: ttk.Frame):
        grp = ttk.LabelFrame(parent, text=" 1. Speicherkarte & Zielordner ", padding="10")
        grp.pack(fill=tk.X, pady=(0, 8))

        # Drive detection row
        row0 = ttk.Frame(grp)
        row0.pack(fill=tk.X, pady=2)
        ttk.Label(row0, text="Erkannte Speicherkarten:", width=24, anchor=tk.W).pack(side=tk.LEFT)
        self.cbo_drives = ttk.Combobox(row0, state="readonly", width=50)
        self.cbo_drives.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.cbo_drives.bind("<<ComboboxSelected>>", self._on_drive_selected)

        btn_refresh_drives = ttk.Button(row0, text="🔄 Neu suchen", width=12, command=self._refresh_drives)
        btn_refresh_drives.pack(side=tk.LEFT)

        # Source folder row
        row1 = ttk.Frame(grp)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="Quellordner (Fotos):", width=24, anchor=tk.W).pack(side=tk.LEFT)
        self.var_source = tk.StringVar(value=self.config.source_dir)
        self.ent_source = ttk.Entry(row1, textvariable=self.var_source)
        self.ent_source.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row1, text="Ordner wählen...", width=15, command=self._browse_source).pack(side=tk.LEFT)

        # Photo Target folder row
        row2 = ttk.Frame(grp)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="Zielordner Fotos (Basis):", width=24, anchor=tk.W).pack(side=tk.LEFT)
        self.var_target = tk.StringVar(value=self.config.target_dir)
        self.ent_target = ttk.Entry(row2, textvariable=self.var_target)
        self.ent_target.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row2, text="Durchsuchen...", width=15, command=self._browse_target).pack(side=tk.LEFT)

        # Video Target folder row
        row3 = ttk.Frame(grp)
        row3.pack(fill=tk.X, pady=3)
        self.var_separate_video = tk.BooleanVar(value=self.config.separate_video_dir)
        chk_vid = ttk.Checkbutton(
            row3,
            text="Eigener Ordner für Videos:",
            variable=self.var_separate_video,
            command=self._on_toggle_video_dir,
            width=24,
        )
        chk_vid.pack(side=tk.LEFT)

        self.var_video_target = tk.StringVar(value=self.config.video_target_dir)
        self.ent_video_target = ttk.Entry(row3, textvariable=self.var_video_target)
        self.ent_video_target.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.btn_browse_video = ttk.Button(row3, text="Durchsuchen...", width=15, command=self._browse_video_target)
        self.btn_browse_video.pack(side=tk.LEFT)

    def _on_toggle_video_dir(self):
        is_sep = self.var_separate_video.get()
        state = tk.NORMAL if is_sep else tk.DISABLED
        self.ent_video_target.config(state=state)
        self.btn_browse_video.config(state=state)
        self._update_preview()

    def _build_pattern_section(self, parent: ttk.Frame):
        grp = ttk.LabelFrame(parent, text=" 2. Umbenennung & Ordnerstruktur ", padding="10")
        grp.pack(fill=tk.X, pady=(0, 8))

        # Folder structure pattern
        f_row = ttk.Frame(grp)
        f_row.pack(fill=tk.X, pady=2)
        ttk.Label(f_row, text="Ordner-Schema:", width=24, anchor=tk.W).pack(side=tk.LEFT)
        self.var_folder_pattern = tk.StringVar(value=self.config.folder_pattern)
        self.ent_folder = ttk.Entry(f_row, textvariable=self.var_folder_pattern)
        self.ent_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.var_folder_pattern.trace_add("write", lambda *_: self._update_preview())

        # Folder Quick chips
        chip_f = ttk.Frame(f_row)
        chip_f.pack(side=tk.LEFT)
        for tag in ["{YYYY}", "{YYYY}-{MM}-{DD}", "{MONTH_NAME}", "{camera}", "{type}"]:
            ttk.Button(chip_f, text=tag, width=len(tag) + 1, command=lambda t=tag: self._insert_tag(self.ent_folder, t)).pack(side=tk.LEFT, padx=1)

        # File naming pattern
        n_row = ttk.Frame(grp)
        n_row.pack(fill=tk.X, pady=3)
        ttk.Label(n_row, text="Dateiname-Schema:", width=24, anchor=tk.W).pack(side=tk.LEFT)
        self.var_file_pattern = tk.StringVar(value=self.config.file_pattern)
        self.ent_file = ttk.Entry(n_row, textvariable=self.var_file_pattern)
        self.ent_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.var_file_pattern.trace_add("write", lambda *_: self._update_preview())

        # File Quick chips
        chip_n = ttk.Frame(n_row)
        chip_n.pack(side=tk.LEFT)
        for tag in ["{YYYY}-{MM}-{DD}", "{hh}-{mm}-{ss}", "{camera}", "{orig_name}", "{num:04d}"]:
            ttk.Button(chip_n, text=tag, width=len(tag) + 1, command=lambda t=tag: self._insert_tag(self.ent_file, t)).pack(side=tk.LEFT, padx=1)

        # RAW & JPG Organization Dropdown
        org_row = ttk.Frame(grp)
        org_row.pack(fill=tk.X, pady=3)
        ttk.Label(org_row, text="RAW- & JPG-Ablage:", width=24, anchor=tk.W).pack(side=tk.LEFT)

        current_org_label = self.TYPE_ORG_OPTIONS.get(self.config.type_folder_organization, self.TYPE_ORG_OPTIONS["same"])
        self.var_type_org_display = tk.StringVar(value=current_org_label)
        self.cbo_type_org = ttk.Combobox(
            org_row,
            textvariable=self.var_type_org_display,
            values=list(self.TYPE_ORG_OPTIONS.values()),
            state="readonly",
        )
        self.cbo_type_org.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.cbo_type_org.bind("<<ComboboxSelected>>", lambda _: self._update_preview())

        # Live Preview Row
        p_row = ttk.Frame(grp)
        p_row.pack(fill=tk.X, pady=4)
        ttk.Label(p_row, text="Beispiel-Vorschau:", width=24, anchor=tk.NW).pack(side=tk.LEFT)

        prev_box = ttk.Frame(p_row)
        prev_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_preview_jpg = ttk.Label(prev_box, text="", style="Preview.TLabel")
        self.lbl_preview_jpg.pack(anchor=tk.W)

        self.lbl_preview_raw = ttk.Label(prev_box, text="", style="Preview.TLabel")
        self.lbl_preview_raw.pack(anchor=tk.W)

        self.lbl_preview_vid = ttk.Label(prev_box, text="", style="Preview.TLabel")
        self.lbl_preview_vid.pack(anchor=tk.W)

        # Options Row
        opt_row = ttk.Frame(grp)
        opt_row.pack(fill=tk.X, pady=(6, 0))

        self.var_only_new = tk.BooleanVar(value=self.config.only_new_files)
        ttk.Checkbutton(opt_row, text="Nur neue Fotos (bereits importierte überspringen)", variable=self.var_only_new).pack(side=tk.LEFT, padx=(0, 15))

        self.var_recursive = tk.BooleanVar(value=self.config.recursive_scan)
        ttk.Checkbutton(opt_row, text="Unterordner durchsuchen", variable=self.var_recursive).pack(side=tk.LEFT, padx=(0, 15))

        self.var_videos = tk.BooleanVar(value=self.config.include_videos)
        ttk.Checkbutton(opt_row, text="Videos einbeziehen", variable=self.var_videos).pack(side=tk.LEFT, padx=(0, 15))

    def _build_action_section(self, parent: ttk.Frame):
        act_frame = ttk.Frame(parent)
        act_frame.pack(fill=tk.X, pady=(0, 8))

        self.btn_scan = ttk.Button(act_frame, text="🔍 1. Karte / Ordner scannen", width=28, command=self._start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_import = ttk.Button(act_frame, text="⬇️ 2. Fotos herunterladen", width=28, style="Accent.TButton", command=self._start_import)
        self.btn_import.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_import.config(state=tk.DISABLED)

        self.btn_cancel = ttk.Button(act_frame, text="Abbrechen", width=14, command=self._cancel_task)
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_cancel.config(state=tk.DISABLED)

        btn_hist = ttk.Button(act_frame, text="📋 Historie", width=14, command=self._open_history)
        btn_hist.pack(side=tk.RIGHT)

        btn_save_cfg = ttk.Button(act_frame, text="💾 Einstellungen merken", width=22, command=self._save_config)
        btn_save_cfg.pack(side=tk.RIGHT, padx=(0, 8))

        # Progress bar
        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.lbl_status = ttk.Label(prog_frame, text="Bereit.", width=35, anchor=tk.E)
        self.lbl_status.pack(side=tk.RIGHT)

    def _build_table_section(self, parent: ttk.Frame):
        table_frame = ttk.LabelFrame(parent, text=" 3. Gefundene Fotos & Vorschau ", padding="6")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        columns = ("status", "type", "orig_name", "date_taken", "camera", "target_folder", "target_filename", "size")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("status", text="Status")
        self.tree.heading("type", text="Typ")
        self.tree.heading("orig_name", text="Original")
        self.tree.heading("date_taken", text="Aufnahmedatum")
        self.tree.heading("camera", text="Kamera")
        self.tree.heading("target_folder", text="Zielordner")
        self.tree.heading("target_filename", text="Neuer Dateiname")
        self.tree.heading("size", text="Größe")

        self.tree.column("status", width=120, anchor=tk.CENTER)
        self.tree.column("type", width=60, anchor=tk.CENTER)
        self.tree.column("orig_name", width=130, anchor=tk.W)
        self.tree.column("date_taken", width=140, anchor=tk.CENTER)
        self.tree.column("camera", width=130, anchor=tk.W)
        self.tree.column("target_folder", width=220, anchor=tk.W)
        self.tree.column("target_filename", width=240, anchor=tk.W)
        self.tree.column("size", width=80, anchor=tk.E)

        # Tags for colored rows
        self.tree.tag_configure("new", background="#e8f5e9", foreground="#2e7d32")
        self.tree.tag_configure("dup", background="#f5f5f5", foreground="#888888")
        self.tree.tag_configure("exists", background="#fffde7", foreground="#f57f17")
        self.tree.tag_configure("error", background="#ffebee", foreground="#c62828")

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

    def _build_status_bar(self, parent: ttk.Frame):
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X)

        self.lbl_stats = ttk.Label(status_frame, text="Keine Dateien gescannt.")
        self.lbl_stats.pack(side=tk.LEFT)

        self.lbl_hist_count = ttk.Label(status_frame, text="Historie: 0 Fotos")
        self.lbl_hist_count.pack(side=tk.RIGHT)

    def _insert_tag(self, entry: ttk.Entry, tag: str):
        entry.insert(tk.INSERT, tag)
        self._update_preview()

    def _get_current_type_org(self) -> str:
        disp = self.var_type_org_display.get()
        return self.TYPE_ORG_REVERSE.get(disp, "same")

    def _update_preview(self):
        f_patt = self.var_file_pattern.get().strip() or "{orig_name}"
        d_patt = self.var_folder_pattern.get().strip() or "."
        type_org = self._get_current_type_org()
        is_sep_vid = self.var_separate_video.get()

        try:
            # JPG sample
            jpg_meta = MediaMetadata(
                file_path=Path("DSC_0123.JPG"),
                orig_name="DSC_0123",
                extension=".jpg",
                file_size=8000000,
                date_taken=datetime(2026, 8, 15, 14, 30, 45),
                date_source="EXIF",
                camera_make="Sony",
                camera_model="ILCE-7M4",
                camera_name="Sony ILCE-7M4",
            )
            rel_jpg, name_jpg = generate_sample_preview(f_patt, d_patt, sample_meta=jpg_meta, sample_index=1, type_folder_organization=type_org)
            self.lbl_preview_jpg.config(text=f"📷 JPG:  📁 {rel_jpg} / 📄 {name_jpg}")

            # RAW sample
            raw_meta = MediaMetadata(
                file_path=Path("DSC_0123.ARW"),
                orig_name="DSC_0123",
                extension=".arw",
                file_size=28000000,
                date_taken=datetime(2026, 8, 15, 14, 30, 45),
                date_source="EXIF",
                camera_make="Sony",
                camera_model="ILCE-7M4",
                camera_name="Sony ILCE-7M4",
            )
            rel_raw, name_raw = generate_sample_preview(f_patt, d_patt, sample_meta=raw_meta, sample_index=1, type_folder_organization=type_org)
            self.lbl_preview_raw.config(text=f"🎞️ RAW:  📁 {rel_raw} / 📄 {name_raw}")

            # Video sample
            vid_meta = MediaMetadata(
                file_path=Path("C0001.MP4"),
                orig_name="C0001",
                extension=".mp4",
                file_size=120000000,
                date_taken=datetime(2026, 8, 15, 14, 35, 10),
                date_source="Video",
                camera_make="Sony",
                camera_model="ILCE-7M4",
                camera_name="Sony ILCE-7M4",
            )
            rel_vid, name_vid = generate_sample_preview(f_patt, d_patt, sample_meta=vid_meta, sample_index=1, type_folder_organization="same")
            vid_target_prefix = "[Video-Ordner]" if is_sep_vid else "[Foto-Ordner]"
            self.lbl_preview_vid.config(text=f"🎥 Video: {vid_target_prefix} 📁 {rel_vid} / 📄 {name_vid}")
        except Exception as e:
            self.lbl_preview_jpg.config(text=f"[Fehler im Muster: {e}]")
            self.lbl_preview_raw.config(text="")
            self.lbl_preview_vid.config(text="")

    def _refresh_drives(self):
        drives = detect_drives()
        self.drive_list = drives
        display_values = []
        best_idx = 0

        for idx, d in enumerate(drives):
            display_values.append(d.display_name)
            if d.has_dcim:
                best_idx = idx

        self.cbo_drives["values"] = display_values
        if display_values:
            self.cbo_drives.current(best_idx)
            self._on_drive_selected()
        else:
            self.cbo_drives.set("Keine Wechseldatenträger gefunden")

    def _on_drive_selected(self, event=None):
        idx = self.cbo_drives.current()
        if 0 <= idx < len(self.drive_list):
            drive = self.drive_list[idx]
            selected_path = drive.dcim_path if drive.has_dcim else drive.path
            self.var_source.set(selected_path)

    def _browse_source(self):
        path = filedialog.askdirectory(title="Quellordner / Speicherkarte auswählen", initialdir=self.var_source.get())
        if path:
            self.var_source.set(path)

    def _browse_target(self):
        path = filedialog.askdirectory(title="Zielordner für Fotos auswählen", initialdir=self.var_target.get())
        if path:
            self.var_target.set(path)

    def _browse_video_target(self):
        path = filedialog.askdirectory(title="Zielordner für Videos auswählen", initialdir=self.var_video_target.get())
        if path:
            self.var_video_target.set(path)

    def _update_history_status_bar(self):
        count = self.history.get_count()
        self.lbl_hist_count.config(text=f"Historie: {count} Fotos erfasst")

    def _open_history(self):
        HistoryWindow(self.root, self.history, on_cleared=self._on_history_cleared)

    def _on_history_cleared(self):
        self._update_history_status_bar()
        if self.scan_items:
            for item in self.scan_items:
                item.is_duplicate = False
                item.status = "Neu"
            self._render_table_items()

    def _save_config(self):
        self._sync_config_from_ui()
        self.config.save()
        messagebox.showinfo("Gespeichert", "Einstellungen wurden erfolgreich gespeichert!")

    def _sync_config_from_ui(self):
        self.config.source_dir = self.var_source.get()
        self.config.target_dir = self.var_target.get()
        self.config.separate_video_dir = self.var_separate_video.get()
        self.config.video_target_dir = self.var_video_target.get()
        self.config.type_folder_organization = self._get_current_type_org()
        self.config.file_pattern = self.var_file_pattern.get()
        self.config.folder_pattern = self.var_folder_pattern.get()
        self.config.only_new_files = self.var_only_new.get()
        self.config.recursive_scan = self.var_recursive.get()
        self.config.include_videos = self.var_videos.get()

    def _set_ui_busy(self, busy: bool):
        self.is_busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_scan.config(state=state)
        self.btn_import.config(state=tk.DISABLED if busy or not self.scan_items else tk.NORMAL)
        self.btn_cancel.config(state=tk.NORMAL if busy else tk.DISABLED)
        self.ent_source.config(state=state)
        self.ent_target.config(state=state)
        if self.var_separate_video.get():
            self.ent_video_target.config(state=state)

    def _cancel_task(self):
        self.cancel_event.set()
        self.lbl_status.config(text="Vorgang wird abgebrochen...")

    def _start_scan(self):
        src = self.var_source.get().strip()
        if not src or not Path(src).exists():
            messagebox.showwarning("Fehler", "Bitte wähle einen gültigen Quellordner aus.")
            return

        self._sync_config_from_ui()
        self.cancel_event.clear()
        self._set_ui_busy(True)
        self.progress_bar["value"] = 0
        self.lbl_status.config(text="Suche Dateien...")

        def scan_worker():
            try:
                def on_progress(current, total, msg):
                    percent = (current / total) * 100 if total > 0 else 0
                    self.root.after(0, lambda: self._update_progress_ui(percent, msg))

                items = self.engine.scan(
                    Path(self.config.source_dir),
                    self.config,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event
                )
                self.root.after(0, lambda: self._on_scan_finished(items))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Fehler beim Scannen", str(e)))
                self.root.after(0, lambda: self._set_ui_busy(False))

        threading.Thread(target=scan_worker, daemon=True).start()

    def _update_progress_ui(self, percent: float, msg: str):
        self.progress_bar["value"] = percent
        self.lbl_status.config(text=msg)

    def _on_scan_finished(self, items: List[ScanItem]):
        self.scan_items = items
        self._set_ui_busy(False)
        self.btn_import.config(state=tk.NORMAL if items else tk.DISABLED)
        self.progress_bar["value"] = 100
        self.lbl_status.config(text="Scan abgeschlossen.")
        self._render_table_items()

    def _render_table_items(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        new_count = 0
        dup_count = 0
        total_size = 0

        for item in self.scan_items:
            tag = "new"
            if item.status == "Bereits importiert":
                tag = "dup"
                dup_count += 1
            elif item.status == "Existiert im Ziel":
                tag = "exists"
            elif item.status == "Fehler":
                tag = "error"
            else:
                new_count += 1

            total_size += item.metadata.file_size
            dt_str = item.metadata.date_taken.strftime("%Y-%m-%d %H:%M:%S") if item.metadata.date_taken else "-"
            size_mb = f"{item.metadata.file_size / (1024 * 1024):.1f} MB"

            # Clean display of destination relative to respective root
            base_dir = Path(self.config.video_target_dir) if (item.metadata.is_video and self.config.separate_video_dir) else Path(self.config.target_dir)
            try:
                rel_dest_folder = str(item.target_path.parent.relative_to(base_dir))
                if item.metadata.is_video and self.config.separate_video_dir:
                    rel_dest_folder = f"[Videos] {rel_dest_folder}"
            except Exception:
                rel_dest_folder = str(item.target_path.parent)

            target_name = item.target_path.name

            self.tree.insert(
                "",
                tk.END,
                values=(
                    item.status,
                    item.metadata.media_type,
                    item.source_path.name,
                    dt_str,
                    item.metadata.formatted_camera or "-",
                    rel_dest_folder,
                    target_name,
                    size_mb,
                ),
                tags=(tag,),
            )

        total_mb = total_size / (1024 * 1024)
        size_label = f"{total_mb:.1f} MB" if total_mb < 1024 else f"{total_mb / 1024:.2f} GB"
        self.lbl_stats.config(
            text=f"Gesamt: {len(self.scan_items)} Dateien ({size_label}) | Neu: {new_count} | Bereits importiert: {dup_count}"
        )

    def _start_import(self):
        if not self.scan_items:
            messagebox.showinfo("Hinweis", "Keine Dateien zum Importieren vorhanden.")
            return

        to_import = [it for it in self.scan_items if not (self.config.only_new_files and it.is_duplicate)]
        if not to_import:
            messagebox.showinfo("Hinweis", "Alle gefundenen Fotos wurden bereits importiert.")
            return

        target_dir = Path(self.var_target.get().strip())
        if not target_dir.exists():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Fehler", f"Zielordner für Fotos konnte nicht erstellt werden: {e}")
                return

        if self.var_separate_video.get():
            vid_dir = Path(self.var_video_target.get().strip())
            if not vid_dir.exists():
                try:
                    vid_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Fehler", f"Zielordner für Videos konnte nicht erstellt werden: {e}")
                    return

        self._sync_config_from_ui()
        self.cancel_event.clear()
        self._set_ui_busy(True)
        self.progress_bar["value"] = 0

        def import_worker():
            try:
                def on_progress(current, total, msg):
                    percent = (current / total) * 100 if total > 0 else 0
                    self.root.after(0, lambda: self._update_progress_ui(percent, msg))

                stats = self.engine.execute_import(
                    self.scan_items,
                    self.config,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event
                )
                self.root.after(0, lambda: self._on_import_finished(stats))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Fehler beim Import", str(e)))
                self.root.after(0, lambda: self._set_ui_busy(False))

        threading.Thread(target=import_worker, daemon=True).start()

    def _on_import_finished(self, stats: ImportStats):
        self._set_ui_busy(False)
        self.progress_bar["value"] = 100
        self.lbl_status.config(text=f"Import abgeschlossen ({stats.copied_success} kopiert).")
        self._update_history_status_bar()

        # Update table items status
        for item in self.scan_items:
            if self.history.is_imported(item.source_path, item.file_hash):
                item.is_duplicate = True
                item.status = "Bereits importiert"
        self._render_table_items()

        mb_copied = stats.bytes_copied / (1024 * 1024)
        size_str = f"{mb_copied:.1f} MB" if mb_copied < 1024 else f"{mb_copied / 1024:.2f} GB"

        msg = (
            f"Import erfolgreich abgeschlossen!\n\n"
            f"• Neu kopiert: {stats.copied_success} Datei(en) ({size_str})\n"
            f"• Übersprungen (Duplikate): {stats.duplicates_skipped}\n"
        )
        if stats.failed > 0:
            msg += f"• Fehler: {stats.failed}\n"

        messagebox.showinfo("Import abgeschlossen", msg)


def run_gui():
    set_high_dpi()
    root = tk.Tk()
    app = FotoDownApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
