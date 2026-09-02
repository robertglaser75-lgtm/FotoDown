"""Modern CustomTkinter GUI for FotoDown (Windows 11 Fluent Dark UI) with Non-Stalling Async Gallery & Cache Persistence."""

from datetime import datetime
import io
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional, Dict, Tuple

import customtkinter as ctk
from PIL import Image, ImageOps, ImageDraw

from core.config import AppConfig
from core.drive_detector import detect_drives, DriveInfo, eject_drive
from core.exif_reader import MediaMetadata
from core.history import ImportHistory
from core.importer import ImporterEngine, ScanItem, ImportStats
from core.naming import generate_sample_preview

# Set CustomTkinter Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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


def apply_window_icon(window: ctk.CTk | ctk.CTkToplevel):
    """Sets window icon from assets or Downloads/fotodown.jpg."""
    icon_paths = [
        Path("assets/icon_64.png"),
        Path("assets/icon.png"),
        Path(r"C:\Users\rober\Downloads\fotodown.jpg"),
    ]
    for p in icon_paths:
        if p.exists():
            try:
                if p.suffix.lower() == ".jpg":
                    from PIL import ImageTk
                    pil_img = Image.open(p).resize((64, 64))
                    tk_img = ImageTk.PhotoImage(pil_img)
                    window.iconphoto(True, tk_img)
                    window._icon_ref = tk_img
                else:
                    tk_img = tk.PhotoImage(file=str(p))
                    window.iconphoto(True, tk_img)
                    window._icon_ref = tk_img
                break
            except Exception:
                continue


def load_ctk_image(path_str: str, size: Tuple[int, int] = (40, 40)) -> Optional[ctk.CTkImage]:
    """Loads a CTkImage if file exists."""
    p = Path(path_str)
    if p.exists():
        try:
            pil_img = Image.open(p)
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        except Exception:
            pass
    return None


def create_placeholder_thumb(icon_text: str, bg_color="#1c222b", fg_color="#38bdf8", size=(120, 120)) -> ctk.CTkImage:
    """Creates a clean placeholder tile for Video/RAW/Non-image files."""
    img = Image.new("RGB", size, color=bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, size[0] - 3, size[1] - 3], outline="#334155", width=1)
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


def extract_raw_embedded_jpeg(raw_path: Path) -> Optional[Image.Image]:
    """Extracts embedded JPEG preview thumbnail from camera RAW file safely (bounded chunk scan)."""
    # 1. Direct PIL open (works for DNG/TIFF RAWs)
    try:
        with Image.open(raw_path) as img:
            img.load()
            return img.copy()
    except Exception:
        pass

    # 2. Bounded binary scan for embedded JPEGs (reads up to 6MB)
    try:
        with open(raw_path, "rb") as f:
            data = f.read(6 * 1024 * 1024)

        pos = 0
        candidates = []
        for _ in range(5):
            start = data.find(b"\xff\xd8\xff", pos)
            if start == -1:
                break

            chunk = data[start:start + 2000000]
            end = chunk.rfind(b"\xff\xd9")
            if end != -1 and end > 500:
                jpeg_bytes = chunk[:end + 2]
                try:
                    with Image.open(io.BytesIO(jpeg_bytes)) as img:
                        img.load()
                        candidates.append((img.width * img.height, img.copy()))
                except Exception:
                    pass
            pos = start + 4

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    except Exception:
        pass
    return None


class HistoryWindow(ctk.CTkToplevel):
    """Sub-window to inspect and manage import history."""

    def __init__(self, parent, history: ImportHistory, on_cleared=None):
        super().__init__(parent)
        self.title("FotoDown - Download-Historie")
        self.geometry("900x540")
        self.history = history
        self.on_cleared = on_cleared

        apply_window_icon(self)
        self.lift()
        self.focus_force()

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1e293b", border_width=1, border_color="#334155")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=14, pady=(14, 10))

        self.lbl_count = ctk.CTkLabel(
            header_frame,
            text="Einträge geladen...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_count.pack(side=tk.LEFT)

        btn_clear = ctk.CTkButton(
            header_frame,
            text="🗑️ Historie leeren",
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._clear_history,
            width=140
        )
        btn_clear.pack(side=tk.RIGHT)

        table_container = ctk.CTkFrame(main_frame, corner_radius=8, fg_color="#0f172a", border_width=1, border_color="#334155")
        table_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Hist.Treeview", font=("Segoe UI", 10), rowheight=32, background="#0f172a", fieldbackground="#0f172a", foreground="#f8fafc", bordercolor="#334155")
        style.configure("Hist.Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#1e293b", foreground="#38bdf8", bordercolor="#334155")

        columns = ("orig_name", "date_taken", "destination", "import_date")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse", style="Hist.Treeview")
        self.tree.heading("orig_name", text="Originaldatei")
        self.tree.heading("date_taken", text="Aufnahmedatum")
        self.tree.heading("destination", text="Gespeichert unter")
        self.tree.heading("import_date", text="Importiert am")

        self.tree.column("orig_name", width=160, anchor=tk.W)
        self.tree.column("date_taken", width=140, anchor=tk.CENTER)
        self.tree.column("destination", width=380, anchor=tk.W)
        self.tree.column("import_date", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=2)

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        records = self.history.get_recent_imports(limit=500)
        total_count = self.history.get_count()
        self.lbl_count.configure(text=f"📋 Gespeicherte Fotos in Historie: {total_count} (zeigt letzte {len(records)})")

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

    COLUMN_TITLES = {
        "select": "Auswahl",
        "status": "Status",
        "type": "Typ",
        "orig_name": "Originaldatei",
        "date_taken": "Aufnahmedatum",
        "camera": "Kamera",
        "target_folder": "Zielordner",
        "target_filename": "Neuer Dateiname",
        "size": "Größe",
    }

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("FotoDown - Foto-Importeur & EXIF-Manager")
        self.root.geometry("1280x920")
        self.root.minsize(1020, 720)

        apply_window_icon(self.root)

        self.config = AppConfig.load()
        self.history = ImportHistory()
        self.engine = ImporterEngine(self.history)

        self.scan_items: List[ScanItem] = []
        self.cancel_event = threading.Event()
        self.drive_list: List[DriveInfo] = []
        self.is_busy = False

        # Collapsible state for sections 1 and 2
        self.is_sec1_open = False
        self.is_sec2_open = False

        # View mode state: "list" or "gallery"
        self.view_mode = "list"

        # Thread-safe Thumbnail Caching Architecture:
        self.thumb_queue = queue.Queue()
        self.thumb_cache: Dict[str, ctk.CTkImage] = {}
        self.gallery_card_labels: Dict[str, ctk.CTkLabel] = {}
        self.placeholders: Dict[str, ctk.CTkImage] = {
            "RAW": create_placeholder_thumb("📸 RAW"),
            "VIDEO": create_placeholder_thumb("📹 VIDEO"),
            "IMG": create_placeholder_thumb("⏳ LADE..."),
        }

        # Background thread tracking
        self.thumb_worker_active = False
        self.total_thumb_count = 0
        self.loaded_thumb_count = 0

        # Sorting state
        self.sort_column: Optional[str] = None
        self.sort_reverse: bool = False

        # Filter state variables
        self.var_filter_status = tk.StringVar(value="Alle Status")
        self.var_filter_type = tk.StringVar(value="Alle Typen")
        self.var_filter_camera = tk.StringVar(value="Alle Kameras")
        self.var_filter_ext = tk.StringVar(value="Alle Endungen")
        self.var_filter_search = tk.StringVar(value="")

        self._build_ui()
        self._refresh_drives()
        self._update_preview()
        self._update_history_status_bar()

    def _build_ui(self):
        main_container = ctk.CTkFrame(self.root, fg_color="#0f172a", corner_radius=0)
        main_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        self._build_header_banner(main_container)
        self._build_source_target_section(main_container)
        self._build_pattern_section(main_container)
        self._build_action_section(main_container)
        self._build_table_section(main_container)
        self._build_status_bar(main_container)

    def _build_header_banner(self, parent: ctk.CTkFrame):
        header = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        header.pack(fill=tk.X, pady=(0, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side=tk.LEFT, padx=14, pady=10)

        # App Icon
        icon_img = load_ctk_image("assets/icon_64.png", size=(42, 42)) or load_ctk_image("assets/icon.png", size=(42, 42))
        if icon_img:
            lbl_icon = ctk.CTkLabel(title_box, image=icon_img, text="")
            lbl_icon.pack(side=tk.LEFT, padx=(0, 12))

        text_box = ctk.CTkFrame(title_box, fg_color="transparent")
        text_box.pack(side=tk.LEFT)

        ctk.CTkLabel(
            text_box,
            text="FotoDown",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor=tk.W)

        ctk.CTkLabel(
            text_box,
            text="Fotos & Videos von SD-Karten automatisch organisieren und umbenennen",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        ).pack(anchor=tk.W)

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side=tk.RIGHT, padx=14, pady=10)

        btn_hist = ctk.CTkButton(
            btn_box,
            text="📋 Import-Historie",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#f8fafc",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._open_history,
            width=140
        )
        btn_hist.pack(side=tk.RIGHT, padx=4)

        btn_save_cfg = ctk.CTkButton(
            btn_box,
            text="💾 Einstellungen merken",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#f8fafc",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._save_config,
            width=160
        )
        btn_save_cfg.pack(side=tk.RIGHT, padx=4)

    def _build_source_target_section(self, parent: ctk.CTkFrame):
        self.grp_sec1 = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        self.grp_sec1.pack(fill=tk.X, pady=(0, 8))

        # Clickable Header Bar for Collapsing / Expanding
        header_f = ctk.CTkFrame(self.grp_sec1, fg_color="transparent", cursor="hand2")
        header_f.pack(fill=tk.X, padx=14, pady=8)

        self.lbl_sec1_title = ctk.CTkLabel(
            header_f,
            text="📂 1. Quelle & Zielordner",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_sec1_title.pack(side=tk.LEFT)

        self.lbl_sec1_summary = ctk.CTkLabel(
            header_f,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#94a3b8"
        )
        self.lbl_sec1_summary.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_sec1_arrow = ctk.CTkLabel(
            header_f,
            text="▶",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_sec1_arrow.pack(side=tk.RIGHT)

        for widget in (header_f, self.lbl_sec1_title, self.lbl_sec1_summary, self.lbl_sec1_arrow):
            widget.bind("<Button-1>", lambda _: self._toggle_section1())

        # Collapsible Content Frame (Collapsed by default)
        self.sec1_content = ctk.CTkFrame(self.grp_sec1, fg_color="transparent")

        # Drive selection row
        row0 = ctk.CTkFrame(self.sec1_content, fg_color="transparent")
        row0.pack(fill=tk.X, pady=(0, 6))

        ctk.CTkLabel(row0, text="Wechseldatenträger / SD:", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)
        self.cbo_drives = ctk.CTkComboBox(row0, state="readonly", fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.cbo_drives.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.cbo_drives.configure(command=self._on_drive_selected)

        btn_refresh_drives = ctk.CTkButton(
            row0,
            text="🔄 Neu suchen",
            width=110,
            fg_color="#334155",
            hover_color="#475569",
            command=self._refresh_drives
        )
        btn_refresh_drives.pack(side=tk.LEFT)

        # Source folder row
        row1 = ctk.CTkFrame(self.sec1_content, fg_color="transparent")
        row1.pack(fill=tk.X, pady=3)

        ctk.CTkLabel(row1, text="Quellordner (Fotos):", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)
        self.var_source = tk.StringVar(value=self.config.source_dir)
        self.ent_source = ctk.CTkEntry(row1, textvariable=self.var_source, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.ent_source.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ctk.CTkButton(row1, text="Ordner wählen...", width=130, fg_color="#334155", hover_color="#475569", command=self._browse_source).pack(side=tk.LEFT)

        # Photo Target folder row
        row2 = ctk.CTkFrame(self.sec1_content, fg_color="transparent")
        row2.pack(fill=tk.X, pady=3)

        ctk.CTkLabel(row2, text="Zielordner Fotos (Basis):", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)
        self.var_target = tk.StringVar(value=self.config.target_dir)
        self.ent_target = ctk.CTkEntry(row2, textvariable=self.var_target, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.ent_target.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ctk.CTkButton(row2, text="Durchsuchen...", width=130, fg_color="#334155", hover_color="#475569", command=self._browse_target).pack(side=tk.LEFT)

        # Video Target folder row
        row3 = ctk.CTkFrame(self.sec1_content, fg_color="transparent")
        row3.pack(fill=tk.X, pady=3)

        self.var_separate_video = tk.BooleanVar(value=self.config.separate_video_dir)
        chk_vid = ctk.CTkSwitch(
            row3,
            text="Eigener Ordner für Videos:",
            variable=self.var_separate_video,
            command=self._on_toggle_video_dir,
            width=180,
            progress_color="#0284c7"
        )
        chk_vid.pack(side=tk.LEFT)

        self.var_video_target = tk.StringVar(value=self.config.video_target_dir)
        self.ent_video_target = ctk.CTkEntry(row3, textvariable=self.var_video_target, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.ent_video_target.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.btn_browse_video = ctk.CTkButton(row3, text="Durchsuchen...", width=130, fg_color="#334155", hover_color="#475569", command=self._browse_video_target)
        self.btn_browse_video.pack(side=tk.LEFT)

    def _toggle_section1(self):
        """Toggles collapse/expand state for Section 1."""
        if self.is_sec1_open:
            self.sec1_content.pack_forget()
            self.lbl_sec1_arrow.configure(text="▶")
            self.lbl_sec1_summary.configure(text="")
            self.is_sec1_open = False
        else:
            self.sec1_content.pack(fill=tk.X, padx=14, pady=(0, 10))
            self.lbl_sec1_arrow.configure(text="▼")
            self.lbl_sec1_summary.configure(text="")
            self.is_sec1_open = False

    def _on_toggle_video_dir(self):
        is_sep = self.var_separate_video.get()
        state = "normal" if is_sep else "disabled"
        self.ent_video_target.configure(state=state)
        self.btn_browse_video.configure(state=state)
        self._update_preview()

    def _build_pattern_section(self, parent: ctk.CTkFrame):
        self.grp_sec2 = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        self.grp_sec2.pack(fill=tk.X, pady=(0, 8))

        # Clickable Header Bar for Collapsing / Expanding
        header_f = ctk.CTkFrame(self.grp_sec2, fg_color="transparent", cursor="hand2")
        header_f.pack(fill=tk.X, padx=14, pady=8)

        self.lbl_sec2_title = ctk.CTkLabel(
            header_f,
            text="⚙️ 2. Umbenennung & Ordnerstruktur",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_sec2_title.pack(side=tk.LEFT)

        self.lbl_sec2_summary = ctk.CTkLabel(
            header_f,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#94a3b8"
        )
        self.lbl_sec2_summary.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_sec2_arrow = ctk.CTkLabel(
            header_f,
            text="▶",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_sec2_arrow.pack(side=tk.RIGHT)

        for widget in (header_f, self.lbl_sec2_title, self.lbl_sec2_summary, self.lbl_sec2_arrow):
            widget.bind("<Button-1>", lambda _: self._toggle_section2())

        # Collapsible Content Frame (Collapsed by default)
        self.sec2_content = ctk.CTkFrame(self.grp_sec2, fg_color="transparent")

        # Folder structure pattern
        f_row = ctk.CTkFrame(self.sec2_content, fg_color="transparent")
        f_row.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_row, text="Ordner-Schema:", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)
        self.var_folder_pattern = tk.StringVar(value=self.config.folder_pattern)
        self.ent_folder = ctk.CTkEntry(f_row, textvariable=self.var_folder_pattern, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.ent_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.var_folder_pattern.trace_add("write", lambda *_: self._update_preview())

        # Folder Quick chips
        chip_f = ctk.CTkFrame(f_row, fg_color="transparent")
        chip_f.pack(side=tk.LEFT)
        for tag in ["{YYYY}", "{YYYY}-{MM}-{DD}", "{MONTH_NAME}", "{camera}", "{type}"]:
            ctk.CTkButton(
                chip_f,
                text=tag,
                width=len(tag) * 9 + 12,
                fg_color="#1e293b",
                hover_color="#334155",
                text_color="#38bdf8",
                border_width=1,
                border_color="#38bdf8",
                corner_radius=6,
                font=ctk.CTkFont(size=11),
                command=lambda t=tag: self._insert_tag(self.ent_folder, t)
            ).pack(side=tk.LEFT, padx=2)

        # File naming pattern
        n_row = ctk.CTkFrame(self.sec2_content, fg_color="transparent")
        n_row.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(n_row, text="Dateiname-Schema:", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)
        self.var_file_pattern = tk.StringVar(value=self.config.file_pattern)
        self.ent_file = ctk.CTkEntry(n_row, textvariable=self.var_file_pattern, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        self.ent_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.var_file_pattern.trace_add("write", lambda *_: self._update_preview())

        # File Quick chips
        chip_n = ctk.CTkFrame(n_row, fg_color="transparent")
        chip_n.pack(side=tk.LEFT)
        for tag in ["{YYYY}-{MM}-{DD}", "{hh}-{mm}-{ss}", "{camera}", "{orig_name}", "{num:04d}"]:
            ctk.CTkButton(
                chip_n,
                text=tag,
                width=len(tag) * 9 + 12,
                fg_color="#1e293b",
                hover_color="#334155",
                text_color="#38bdf8",
                border_width=1,
                border_color="#38bdf8",
                corner_radius=6,
                font=ctk.CTkFont(size=11),
                command=lambda t=tag: self._insert_tag(self.ent_file, t)
            ).pack(side=tk.LEFT, padx=2)

        # RAW & JPG Organization Dropdown
        org_row = ctk.CTkFrame(self.sec2_content, fg_color="transparent")
        org_row.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(org_row, text="RAW- & JPG-Ablage:", width=180, anchor=tk.W, text_color="#f8fafc").pack(side=tk.LEFT)

        current_org_label = self.TYPE_ORG_OPTIONS.get(self.config.type_folder_organization, self.TYPE_ORG_OPTIONS["same"])
        self.var_type_org_display = tk.StringVar(value=current_org_label)
        self.cbo_type_org = ctk.CTkComboBox(
            org_row,
            variable=self.var_type_org_display,
            values=list(self.TYPE_ORG_OPTIONS.values()),
            state="readonly",
            fg_color="#090d16",
            border_color="#334155",
            text_color="#f8fafc",
            command=lambda _: self._update_preview()
        )
        self.cbo_type_org.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        # Live Preview Row
        p_row = ctk.CTkFrame(self.sec2_content, fg_color="transparent")
        p_row.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(p_row, text="Beispiel-Vorschau:", width=180, anchor=tk.NW, text_color="#f8fafc").pack(side=tk.LEFT)

        prev_box = ctk.CTkFrame(p_row, fg_color="transparent")
        prev_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_preview_jpg = ctk.CTkLabel(prev_box, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#4ade80")
        self.lbl_preview_jpg.pack(anchor=tk.W)

        self.lbl_preview_raw = ctk.CTkLabel(prev_box, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#4ade80")
        self.lbl_preview_raw.pack(anchor=tk.W)

        self.lbl_preview_vid = ctk.CTkLabel(prev_box, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#4ade80")
        self.lbl_preview_vid.pack(anchor=tk.W)

        # Options Row with Modern Switches
        opt_row = ctk.CTkFrame(self.sec2_content, fg_color="transparent")
        opt_row.pack(fill=tk.X, pady=(6, 0))

        self.var_only_new = tk.BooleanVar(value=self.config.only_new_files)
        ctk.CTkSwitch(opt_row, text="Nur neue Fotos (bereits importierte überspringen)", variable=self.var_only_new, progress_color="#0284c7").pack(side=tk.LEFT, padx=(0, 20))

        self.var_recursive = tk.BooleanVar(value=self.config.recursive_scan)
        ctk.CTkSwitch(opt_row, text="Unterordner durchsuchen", variable=self.var_recursive, progress_color="#0284c7").pack(side=tk.LEFT, padx=(0, 20))

        self.var_videos = tk.BooleanVar(value=self.config.include_videos)
        ctk.CTkSwitch(opt_row, text="Videos einbeziehen", variable=self.var_videos, progress_color="#0284c7").pack(side=tk.LEFT, padx=(0, 20))

    def _toggle_section2(self):
        """Toggles collapse/expand state for Section 2."""
        if self.is_sec2_open:
            self.sec2_content.pack_forget()
            self.lbl_sec2_arrow.configure(text="▶")
            self.lbl_sec2_summary.configure(text="")
            self.is_sec2_open = False
        else:
            self.sec2_content.pack(fill=tk.X, padx=14, pady=(0, 10))
            self.lbl_sec2_arrow.configure(text="▼")
            self.lbl_sec2_summary.configure(text="")
            self.is_sec2_open = False

    def _build_action_section(self, parent: ctk.CTkFrame):
        act_frame = ctk.CTkFrame(parent, fg_color="transparent")
        act_frame.pack(fill=tk.X, pady=(0, 8))

        self.btn_scan = ctk.CTkButton(
            act_frame,
            text="🔍 1. Karte / Ordner scannen",
            width=220,
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self._start_scan
        )
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_import = ctk.CTkButton(
            act_frame,
            text="⬇️ 2. Fotos herunterladen",
            width=230,
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._start_import
        )
        self.btn_import.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_import.configure(state="disabled")

        self.btn_eject = ctk.CTkButton(
            act_frame,
            text="⏏️ Karte / Ordner aushängen",
            width=220,
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            command=self._eject_source_drive
        )
        self.btn_eject.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            act_frame,
            text="✖ Abbrechen",
            width=120,
            height=36,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._cancel_task
        )
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_cancel.configure(state="disabled")

        # Progress bar
        prog_frame = ctk.CTkFrame(parent, fg_color="transparent")
        prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=10, progress_color="#0284c7", fg_color="#090d16")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(prog_frame, text="Bereit.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8")
        self.lbl_status.pack(side=tk.RIGHT)

    def _build_table_section(self, parent: ctk.CTkFrame):
        table_frame = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # Title & View Mode Switcher Header Row (Row 0)
        sec_header = ctk.CTkFrame(table_frame, fg_color="transparent")
        sec_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 4))

        lbl_sec = ctk.CTkLabel(
            sec_header,
            text="🖼️ 3. Gefundene Fotos & Vorschau",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_sec.pack(side=tk.LEFT)

        # View Mode Segmented Button (Liste vs Galerie)
        self.seg_view = ctk.CTkSegmentedButton(
            sec_header,
            values=["📋 Liste", "🖼️ Galerie"],
            command=self._on_view_mode_changed,
            selected_color="#0284c7",
            selected_hover_color="#0369a1",
            unselected_color="#334155",
            unselected_hover_color="#475569",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.seg_view.set("📋 Liste")
        self.seg_view.pack(side=tk.RIGHT)

        # Top selection bar inside table_frame (Row 1)
        select_bar = ctk.CTkFrame(table_frame, fg_color="transparent")
        select_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))

        ctk.CTkLabel(select_bar, text="Auswahl:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#f8fafc").pack(side=tk.LEFT, padx=(0, 8))

        btn_select_all = ctk.CTkButton(select_bar, text="☑ Alle auswählen", width=140, fg_color="#334155", hover_color="#475569", command=self._select_all_items)
        btn_select_all.pack(side=tk.LEFT, padx=(0, 6))

        btn_deselect_all = ctk.CTkButton(select_bar, text="☐ Alle abwählen", width=140, fg_color="#334155", hover_color="#475569", command=self._deselect_all_items)
        btn_deselect_all.pack(side=tk.LEFT, padx=(0, 6))

        btn_select_new = ctk.CTkButton(select_bar, text="✨ Nur Neue auswählen", width=160, fg_color="#334155", hover_color="#475569", command=self._select_only_new_items)
        btn_select_new.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_selected_summary = ctk.CTkLabel(select_bar, text="", font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"), text_color="#38bdf8")
        self.lbl_selected_summary.pack(side=tk.RIGHT, padx=4)

        # Filter bar inside table_frame (Row 2)
        filter_bar = ctk.CTkFrame(table_frame, fg_color="transparent")
        filter_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))

        ctk.CTkLabel(filter_bar, text="Filter:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#f8fafc").pack(side=tk.LEFT, padx=(0, 8))

        # Status filter
        self.cbo_filter_status = ctk.CTkComboBox(
            filter_bar,
            variable=self.var_filter_status,
            values=["Alle Status", "Nur Neue", "Bereits importiert", "Existiert im Ziel"],
            state="readonly",
            width=150,
            fg_color="#090d16",
            border_color="#334155",
            command=lambda _: self._render_table_items()
        )
        self.cbo_filter_status.pack(side=tk.LEFT, padx=(0, 6))

        # Type filter
        self.cbo_filter_type = ctk.CTkComboBox(
            filter_bar,
            variable=self.var_filter_type,
            values=["Alle Typen", "JPG", "RAW", "VIDEO"],
            state="readonly",
            width=120,
            fg_color="#090d16",
            border_color="#334155",
            command=lambda _: self._render_table_items()
        )
        self.cbo_filter_type.pack(side=tk.LEFT, padx=(0, 6))

        # Camera filter
        self.cbo_filter_camera = ctk.CTkComboBox(
            filter_bar,
            variable=self.var_filter_camera,
            values=["Alle Kameras"],
            state="readonly",
            width=160,
            fg_color="#090d16",
            border_color="#334155",
            command=lambda _: self._render_table_items()
        )
        self.cbo_filter_camera.pack(side=tk.LEFT, padx=(0, 6))

        # Extension filter
        self.cbo_filter_ext = ctk.CTkComboBox(
            filter_bar,
            variable=self.var_filter_ext,
            values=["Alle Endungen"],
            state="readonly",
            width=130,
            fg_color="#090d16",
            border_color="#334155",
            command=lambda _: self._render_table_items()
        )
        self.cbo_filter_ext.pack(side=tk.LEFT, padx=(0, 6))

        # Search term filter
        ctk.CTkLabel(filter_bar, text="🔍 Suche:", text_color="#f8fafc").pack(side=tk.LEFT, padx=(8, 4))
        ent_search = ctk.CTkEntry(filter_bar, textvariable=self.var_filter_search, width=140, fg_color="#090d16", border_color="#334155", text_color="#f8fafc")
        ent_search.pack(side=tk.LEFT, padx=(0, 8))
        self.var_filter_search.trace_add("write", lambda *_: self._render_table_items())

        # Reset button
        btn_reset = ctk.CTkButton(filter_bar, text="🧹 Reset", width=90, fg_color="#334155", hover_color="#475569", command=self._reset_filters)
        btn_reset.pack(side=tk.LEFT)

        # 1) List View Container (TTK Treeview) (Row 3)
        self.table_container = ctk.CTkFrame(table_frame, corner_radius=8, fg_color="#0f172a", border_width=1, border_color="#334155")
        self.table_container.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Main.Treeview",
            font=("Segoe UI", 10),
            rowheight=34,
            background="#0f172a",
            fieldbackground="#0f172a",
            foreground="#f8fafc",
            bordercolor="#334155"
        )
        style.configure(
            "Main.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#1e293b",
            foreground="#38bdf8",
            bordercolor="#334155"
        )
        style.map("Main.Treeview.Heading", background=[("active", "#334155")])
        style.map("Main.Treeview", background=[("selected", "#0369a1")], foreground=[("selected", "#ffffff")])

        columns = tuple(self.COLUMN_TITLES.keys())
        self.tree = ttk.Treeview(self.table_container, columns=columns, show="headings", selectmode="extended", style="Main.Treeview")

        for col_key, title in self.COLUMN_TITLES.items():
            self.tree.heading(col_key, text=title, command=lambda c=col_key: self._sort_table_by_column(c))

        self.tree.column("select", width=65, anchor=tk.CENTER)
        self.tree.column("status", width=130, anchor=tk.CENTER)
        self.tree.column("type", width=90, anchor=tk.W)
        self.tree.column("orig_name", width=140, anchor=tk.W)
        self.tree.column("date_taken", width=150, anchor=tk.CENTER)
        self.tree.column("camera", width=140, anchor=tk.W)
        self.tree.column("target_folder", width=220, anchor=tk.W)
        self.tree.column("target_filename", width=240, anchor=tk.W)
        self.tree.column("size", width=85, anchor=tk.E)

        # Tags for colored rows in Dark Slate Theme
        self.tree.tag_configure("new", background="#064e3b", foreground="#4ade80")
        self.tree.tag_configure("dup", background="#1e293b", foreground="#94a3b8")
        self.tree.tag_configure("exists", background="#451a03", foreground="#fbbf24")
        self.tree.tag_configure("error", background="#4c0519", foreground="#f87171")
        self.tree.tag_configure("unselected", foreground="#64748b")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._on_tree_space)

        scroll_y = ttk.Scrollbar(self.table_container, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(self.table_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y, pady=2)

        # 2) Gallery View Container (CTkScrollableFrame) (Row 3, initially hidden)
        self.gallery_container = ctk.CTkScrollableFrame(table_frame, corner_radius=8, fg_color="#0f172a", border_width=1, border_color="#334155")

        table_frame.grid_rowconfigure(3, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

    def _build_status_bar(self, parent: ctk.CTkFrame):
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(fill=tk.X, pady=(2, 0))

        self.lbl_stats = ctk.CTkLabel(status_frame, text="Keine Dateien gescannt.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#f8fafc")
        self.lbl_stats.pack(side=tk.LEFT)

        self.lbl_hist_count = ctk.CTkLabel(status_frame, text="Historie: 0 Fotos", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#38bdf8")
        self.lbl_hist_count.pack(side=tk.RIGHT)

    def _on_view_mode_changed(self, mode_str: str):
        if "Galerie" in mode_str:
            self.view_mode = "gallery"
            self.table_container.grid_remove()
            self.gallery_container.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 10))
            if self.scan_items and len(self.thumb_cache) < len(self.scan_items):
                self._trigger_async_thumbnails(self.scan_items)
        else:
            self.view_mode = "list"
            self.gallery_container.grid_remove()
            self.table_container.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 10))
        self._render_table_items()

    def _get_filtered_items(self) -> List[ScanItem]:
        status_f = self.var_filter_status.get()
        type_f = self.var_filter_type.get()
        camera_f = self.var_filter_camera.get()
        ext_f = self.var_filter_ext.get()
        search_f = self.var_filter_search.get().strip().lower()

        filtered = []
        for item in self.scan_items:
            if status_f == "Nur Neue" and item.status != "Neu":
                continue
            elif status_f == "Bereits importiert" and item.status != "Bereits importiert":
                continue
            elif status_f == "Existiert im Ziel" and item.status != "Existiert im Ziel":
                continue
            elif status_f == "Fehler" and item.status != "Fehler":
                continue

            if type_f != "Alle Typen" and item.metadata.media_type != type_f:
                continue

            if camera_f != "Alle Kameras":
                cam_name = item.metadata.formatted_camera or "Unbekannt"
                if cam_name != camera_f:
                    continue

            if ext_f != "Alle Endungen":
                if item.source_path.suffix.lower() != ext_f.lower():
                    continue

            if search_f:
                target_name = item.target_path.name.lower()
                source_name = item.source_path.name.lower()
                if search_f not in source_name and search_f not in target_name:
                    continue

            filtered.append(item)

        return filtered

    def _reset_filters(self):
        self.var_filter_status.set("Alle Status")
        self.var_filter_type.set("Alle Typen")
        self.var_filter_camera.set("Alle Kameras")
        self.var_filter_ext.set("Alle Endungen")
        self.var_filter_search.set("")
        self._render_table_items()

    def _update_filter_options(self):
        if not self.scan_items:
            self.cbo_filter_camera.configure(values=["Alle Kameras"])
            self.cbo_filter_ext.configure(values=["Alle Endungen"])
            return

        cameras = sorted(list({item.metadata.formatted_camera or "Unbekannt" for item in self.scan_items}))
        self.cbo_filter_camera.configure(values=["Alle Kameras"] + cameras)
        self.var_filter_camera.set("Alle Kameras")

        exts = sorted(list({item.source_path.suffix.lower() for item in self.scan_items}))
        self.cbo_filter_ext.configure(values=["Alle Endungen"] + exts)
        self.var_filter_ext.set("Alle Endungen")

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        item_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if item_id and column_id == "#1":  # 'select' column
            filtered_items = self._get_filtered_items()
            idx = self.tree.index(item_id)
            if 0 <= idx < len(filtered_items):
                item = filtered_items[idx]
                item.selected = not item.selected
                self._render_table_items()
                return "break"

    def _on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        item_id = self.tree.identify_row(event.y)
        if item_id:
            filtered_items = self._get_filtered_items()
            idx = self.tree.index(item_id)
            if 0 <= idx < len(filtered_items):
                item = filtered_items[idx]
                item.selected = not item.selected
                self._render_table_items()

    def _on_tree_space(self, event):
        selected_ids = self.tree.selection()
        if not selected_ids:
            return
        filtered_items = self._get_filtered_items()
        first_idx = self.tree.index(selected_ids[0])
        if 0 <= first_idx < len(filtered_items):
            target_state = not filtered_items[first_idx].selected
            for item_id in selected_ids:
                idx = self.tree.index(item_id)
                if 0 <= idx < len(filtered_items):
                    filtered_items[idx].selected = target_state
            self._render_table_items()

    def _select_all_items(self):
        for item in self._get_filtered_items():
            item.selected = True
        self._render_table_items()

    def _deselect_all_items(self):
        for item in self._get_filtered_items():
            item.selected = False
        self._render_table_items()

    def _select_only_new_items(self):
        for item in self._get_filtered_items():
            item.selected = (item.status == "Neu")
        self._render_table_items()

    def _sort_table_by_column(self, col: str):
        if not self.scan_items:
            return

        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        def sort_key(item: ScanItem):
            if col == "select":
                return item.selected
            elif col == "status":
                return item.status
            elif col == "type":
                return item.metadata.media_type
            elif col == "orig_name":
                return item.source_path.name.lower()
            elif col == "date_taken":
                return item.metadata.date_taken or datetime.min
            elif col == "camera":
                return (item.metadata.formatted_camera or "").lower()
            elif col == "target_folder":
                return str(item.target_path.parent).lower()
            elif col == "target_filename":
                return item.target_path.name.lower()
            elif col == "size":
                return item.metadata.file_size
            return 0

        self.scan_items.sort(key=sort_key, reverse=self.sort_reverse)

        for c, title in self.COLUMN_TITLES.items():
            if c == self.sort_column:
                arrow = " ▼" if self.sort_reverse else " ▲"
                self.tree.heading(c, text=f"{title}{arrow}")
            else:
                self.tree.heading(c, text=title)

        self._render_table_items()

    def _insert_tag(self, entry: ctk.CTkEntry, tag: str):
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
            self.lbl_preview_jpg.configure(text=f"📷 JPG:  📁 {rel_jpg} / 📄 {name_jpg}")

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
            self.lbl_preview_raw.configure(text=f"📸 RAW:  📁 {rel_raw} / 📄 {name_raw}")

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
            self.lbl_preview_vid.configure(text=f"📹 Video: {vid_target_prefix} 📁 {rel_vid} / 📄 {name_vid}")
        except Exception as e:
            self.lbl_preview_jpg.configure(text=f"[Fehler im Muster: {e}]")
            self.lbl_preview_raw.configure(text="")
            self.lbl_preview_vid.configure(text="")

    def _get_thumbnail_image_fast(self, item: ScanItem) -> ctk.CTkImage:
        """Instant 0ms non-blocking thumbnail lookup."""
        path_str = str(item.source_path)
        if path_str in self.thumb_cache:
            return self.thumb_cache[path_str]

        ext = item.source_path.suffix.lower()
        if item.metadata.is_video:
            return self.placeholders["VIDEO"]
        elif item.metadata.is_raw or ext in [".arw", ".cr2", ".cr3", ".nef", ".orf", ".rw2", ".dng", ".pef", ".raf"]:
            return self.placeholders["RAW"]
        else:
            return self.placeholders["IMG"]

    def _load_single_thumbnail_in_background(self, item: ScanItem) -> Optional[Image.Image]:
        """Loads & processes a thumbnail strictly as a pure PIL Image in background thread (0 Tcl/Tk calls!)."""
        ext = item.source_path.suffix.lower()

        # 1. Standard images (JPG, PNG, WEBP)
        if (not item.metadata.is_video) and ext in [".jpg", ".jpeg", ".png", ".webp"]:
            try:
                with Image.open(item.source_path) as pil_img:
                    pil_img = ImageOps.exif_transpose(pil_img)
                    pil_img.thumbnail((120, 120), Image.Resampling.LANCZOS)

                    canvas = Image.new("RGB", (120, 120), color="#1c222b")
                    offset_x = (120 - pil_img.width) // 2
                    offset_y = (120 - pil_img.height) // 2
                    canvas.paste(pil_img, (offset_x, offset_y))
                    return canvas
            except Exception:
                pass

        # 2. Camera RAW files (ARW, CR2, CR3, NEF, ORF, RW2, DNG, PEF, RAF)
        if item.metadata.is_raw or ext in [".arw", ".cr2", ".cr3", ".nef", ".orf", ".rw2", ".dng", ".pef", ".raf"]:
            try:
                pil_raw = extract_raw_embedded_jpeg(item.source_path)
                if pil_raw:
                    pil_raw = ImageOps.exif_transpose(pil_raw)
                    pil_raw.thumbnail((120, 120), Image.Resampling.LANCZOS)

                    canvas = Image.new("RGB", (120, 120), color="#1c222b")
                    offset_x = (120 - pil_raw.width) // 2
                    offset_y = (120 - pil_raw.height) // 2
                    canvas.paste(pil_raw, (offset_x, offset_y))
                    return canvas
            except Exception:
                pass

        return None

    def _trigger_async_thumbnails(self, items: List[ScanItem]):
        """Asynchronously extracts thumbnails in background thread via thread-safe Queue."""
        if self.thumb_worker_active:
            return

        # Unprocessed items only
        unprocessed = [it for it in items if str(it.source_path) not in self.thumb_cache and not it.metadata.is_video]
        if not unprocessed:
            self.lbl_status.configure(text="Miniaturansichten geladen.")
            return

        self.thumb_worker_active = True
        self.total_thumb_count = len(unprocessed)
        self.loaded_thumb_count = 0

        def worker():
            for item in unprocessed:
                path_str = str(item.source_path)
                try:
                    pil_img = self._load_single_thumbnail_in_background(item)
                    self.thumb_queue.put((path_str, pil_img))
                except Exception:
                    self.thumb_queue.put((path_str, None))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(20, self._poll_thumbnail_queue)

    def _poll_thumbnail_queue(self):
        """Main UI thread consumer loop (batch processes up to 12 items safely per tick)."""
        processed_in_batch = 0
        while processed_in_batch < 12:
            try:
                path_str, pil_img = self.thumb_queue.get_nowait()
                self.loaded_thumb_count += 1

                if pil_img is not None:
                    # Create CTkImage safely strictly on main thread!
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(120, 120))
                    self.thumb_cache[path_str] = ctk_img

                    # Update single card label if visible
                    if path_str in self.gallery_card_labels:
                        try:
                            self.gallery_card_labels[path_str].configure(image=ctk_img)
                        except Exception:
                            pass

                processed_in_batch += 1
            except queue.Empty:
                break

        # Update status feedback
        if self.total_thumb_count > 0:
            if self.loaded_thumb_count < self.total_thumb_count:
                self.lbl_status.configure(text=f"⏳ Lade Miniaturansichten ({self.loaded_thumb_count} / {self.total_thumb_count})...")
                self.root.after(25, self._poll_thumbnail_queue)
            else:
                self.lbl_status.configure(text="Miniaturansichten geladen.")
                self.thumb_worker_active = False

    def _render_table_items(self):
        filtered_items = self._get_filtered_items()

        # Update stats
        new_count = 0
        dup_count = 0
        total_size = 0
        selected_size = 0
        selected_count = 0

        for item in self.scan_items:
            if item.status == "Bereits importiert":
                dup_count += 1
            elif item.status == "Neu":
                new_count += 1

            if item.selected:
                selected_count += 1
                selected_size += item.metadata.file_size

        for item in filtered_items:
            total_size += item.metadata.file_size

        total_mb = total_size / (1024 * 1024)
        total_size_label = f"{total_mb:.1f} MB" if total_mb < 1024 else f"{total_mb / 1024:.2f} GB"

        sel_mb = selected_size / (1024 * 1024)
        sel_size_label = f"{sel_mb:.1f} MB" if sel_mb < 1024 else f"{sel_mb / 1024:.2f} GB"

        filter_info = f" (gefiltert: {len(filtered_items)})" if len(filtered_items) != len(self.scan_items) else ""

        self.lbl_stats.configure(
            text=f"Gesamt: {len(self.scan_items)} Dateien{filter_info}  |  Ausgewählt: {selected_count} ({sel_size_label})  |  Neu: {new_count}  |  Duplikate: {dup_count}"
        )
        self.lbl_selected_summary.configure(
            text=f"{selected_count} von {len(self.scan_items)} Dateien zum Download ausgewählt ({sel_size_label})"
        )

        if self.view_mode == "gallery":
            self._render_gallery_view(filtered_items)
        else:
            self._render_list_view(filtered_items)

    def _render_list_view(self, filtered_items: List[ScanItem]):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for item in filtered_items:
            status_text = item.status
            tag = "new"
            if item.status == "Bereits importiert":
                tag = "dup"
                status_text = "✓ Importiert"
            elif item.status == "Existiert im Ziel":
                tag = "exists"
                status_text = "⚠️ Existiert"
            elif item.status == "Fehler":
                tag = "error"
                status_text = "❌ Fehler"
            elif item.status == "Neu":
                status_text = "✨ Neu"

            m_type = item.metadata.media_type
            type_text = f"📷 {m_type}" if m_type == "JPG" else (f"📸 {m_type}" if m_type == "RAW" else (f"📹 {m_type}" if m_type == "VIDEO" else m_type))

            dt_str = item.metadata.date_taken.strftime("%Y-%m-%d %H:%M:%S") if item.metadata.date_taken else "-"
            size_mb = f"{item.metadata.file_size / (1024 * 1024):.1f} MB"

            base_dir = Path(self.config.video_target_dir) if (item.metadata.is_video and self.config.separate_video_dir) else Path(self.config.target_dir)
            try:
                rel_dest_folder = str(item.target_path.parent.relative_to(base_dir))
                if item.metadata.is_video and self.config.separate_video_dir:
                    rel_dest_folder = f"[Videos] {rel_dest_folder}"
            except Exception:
                rel_dest_folder = str(item.target_path.parent)

            target_name = item.target_path.name
            select_icon = "☑" if item.selected else "☐"
            item_tags = (tag,) if item.selected else (tag, "unselected")

            self.tree.insert(
                "",
                tk.END,
                values=(
                    select_icon,
                    status_text,
                    type_text,
                    item.source_path.name,
                    dt_str,
                    item.metadata.formatted_camera or "-",
                    rel_dest_folder,
                    target_name,
                    size_mb,
                ),
                tags=item_tags,
            )

    def _render_gallery_view(self, filtered_items: List[ScanItem]):
        self.gallery_card_labels.clear()
        for widget in self.gallery_container.winfo_children():
            widget.destroy()

        if not filtered_items:
            ctk.CTkLabel(
                self.gallery_container,
                text="Keine Fotos in der Vorschau vorhanden.",
                font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
                text_color="#94a3b8"
            ).pack(expand=True, pady=40)
            return

        # Dynamic columns calculation based on container width
        container_width = self.gallery_container.winfo_width()
        if container_width < 200:
            container_width = 1180

        card_min_width = 170
        columns_count = max(2, container_width // card_min_width)

        for col_idx in range(columns_count):
            self.gallery_container.grid_columnconfigure(col_idx, weight=1)

        for idx, item in enumerate(filtered_items):
            row = idx // columns_count
            col = idx % columns_count
            path_str = str(item.source_path)

            card_border_color = "#0284c7" if item.selected else "#334155"
            card_border_width = 2 if item.selected else 1

            card = ctk.CTkFrame(
                self.gallery_container,
                corner_radius=10,
                fg_color="#1e293b",
                border_width=card_border_width,
                border_color=card_border_color,
                height=200,
                cursor="hand2"
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            # Header row inside card: Checkbox + Status pill
            card_header = ctk.CTkFrame(card, fg_color="transparent")
            card_header.pack(fill=tk.X, padx=6, pady=(6, 2))

            chk_txt = "☑" if item.selected else "☐"
            chk_color = "#38bdf8" if item.selected else "#64748b"
            lbl_chk = ctk.CTkLabel(card_header, text=chk_txt, font=ctk.CTkFont(size=14, weight="bold"), text_color=chk_color)
            lbl_chk.pack(side=tk.LEFT)

            status_text = item.status
            status_color = "#4ade80"
            if item.status == "Bereits importiert":
                status_text = "✓ Importiert"
                status_color = "#94a3b8"
            elif item.status == "Existiert im Ziel":
                status_text = "⚠️ Existiert"
                status_color = "#fbbf24"
            elif item.status == "Fehler":
                status_text = "❌ Fehler"
                status_color = "#f87171"
            elif item.status == "Neu":
                status_text = "✨ Neu"

            lbl_status = ctk.CTkLabel(card_header, text=status_text, font=ctk.CTkFont(size=10, weight="bold"), text_color=status_color)
            lbl_status.pack(side=tk.RIGHT)

            # Instant non-blocking thumbnail lookup (uses thumb_cache instantly!)
            thumb_img = self._get_thumbnail_image_fast(item)
            lbl_thumb = ctk.CTkLabel(card, image=thumb_img, text="")
            lbl_thumb.pack(padx=6, pady=4)

            # Store reference for instant async image replacement
            self.gallery_card_labels[path_str] = lbl_thumb

            # Filename & Size Footer
            card_footer = ctk.CTkFrame(card, fg_color="transparent")
            card_footer.pack(fill=tk.X, padx=6, pady=(0, 6))

            fname = item.source_path.name
            fname_short = fname if len(fname) <= 16 else fname[:13] + "..."
            size_mb = f"{item.metadata.file_size / (1024 * 1024):.1f} MB"

            lbl_name = ctk.CTkLabel(card_footer, text=fname_short, font=ctk.CTkFont(size=10, weight="bold"), text_color="#f8fafc", anchor=tk.W)
            lbl_name.pack(anchor=tk.W)

            lbl_size = ctk.CTkLabel(card_footer, text=size_mb, font=ctk.CTkFont(size=9), text_color="#94a3b8", anchor=tk.W)
            lbl_size.pack(anchor=tk.W)

            # Bind click to toggle selection
            def make_toggle_handler(target_item=item):
                def handler(event=None):
                    target_item.selected = not target_item.selected
                    self._render_table_items()
                return handler

            toggle_fn = make_toggle_handler(item)
            for w in (card, card_header, lbl_chk, lbl_status, lbl_thumb, card_footer, lbl_name, lbl_size):
                w.bind("<Button-1>", toggle_fn)

    def _refresh_drives(self):
        drives = detect_drives()
        self.drive_list = drives
        display_values = []
        best_idx = 0

        for idx, d in enumerate(drives):
            display_values.append(d.display_name)
            if d.has_dcim:
                best_idx = idx

        self.cbo_drives.configure(values=display_values if display_values else ["Keine Datenträger"])
        if display_values:
            self.cbo_drives.set(display_values[best_idx])
            self._on_drive_selected(display_values[best_idx])
        else:
            self.cbo_drives.set("Keine Wechseldatenträger gefunden")

    def _on_drive_selected(self, choice=None):
        idx = -1
        current_val = choice or self.cbo_drives.get()
        for i, d in enumerate(self.drive_list):
            if d.display_name == current_val:
                idx = i
                break

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
        self.lbl_hist_count.configure(text=f"📋 Historie: {count} Fotos erfasst")

    def _open_history(self):
        HistoryWindow(self.root, self.history, on_cleared=self._on_history_cleared)

    def _on_history_cleared(self):
        self._update_history_status_bar()
        if self.scan_items:
            for item in self.scan_items:
                item.is_duplicate = False
                item.status = "Neu"
                item.selected = True
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
        state = "disabled" if busy else "normal"
        self.btn_scan.configure(state=state)
        self.btn_eject.configure(state=state)
        self.btn_import.configure(state="disabled" if busy or not self.scan_items else "normal")
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        self.ent_source.configure(state=state)
        self.ent_target.configure(state=state)
        if self.var_separate_video.get():
            self.ent_video_target.configure(state=state)

    def _cancel_task(self):
        self.cancel_event.set()
        self.lbl_status.configure(text="Vorgang wird abgebrochen...")

    def _start_scan(self):
        src = self.var_source.get().strip()
        if not src or not Path(src).exists():
            messagebox.showwarning("Fehler", "Bitte wähle einen gültigen Quellordner aus.")
            return

        self._sync_config_from_ui()
        self.cancel_event.clear()
        self._set_ui_busy(True)
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Suche Dateien...")

        def scan_worker():
            try:
                def on_progress(current, total, msg):
                    percent = (current / total) if total > 0 else 0
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
        self.progress_bar.set(percent)
        self.lbl_status.configure(text=msg)

    def _on_scan_finished(self, items: List[ScanItem]):
        self.scan_items = items
        self.thumb_cache.clear()
        self.thumb_worker_active = False
        self._set_ui_busy(False)
        self.btn_import.configure(state="normal" if items else "disabled")
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text="Scan abgeschlossen.")
        self._update_filter_options()
        self._trigger_async_thumbnails(items)
        self._render_table_items()

    def _start_import(self):
        if not self.scan_items:
            messagebox.showinfo("Hinweis", "Keine Dateien zum Importieren vorhanden.")
            return

        to_import = [it for it in self.scan_items if it.selected]
        if not to_import:
            messagebox.showinfo("Hinweis", "Keine Dateien zum Importieren ausgewählt. Bitte mindestens eine Datei auswählen.")
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
        self.progress_bar.set(0)

        def import_worker():
            try:
                def on_progress(current, total, msg):
                    percent = (current / total) if total > 0 else 0
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
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"Import abgeschlossen ({stats.copied_success} kopiert).")
        self._update_history_status_bar()

        for item in self.scan_items:
            if self.history.is_imported(item.source_path, item.file_hash):
                item.is_duplicate = True
                item.status = "Bereits importiert"
                item.selected = False
        self._render_table_items()

        mb_copied = stats.bytes_copied / (1024 * 1024)
        size_str = f"{mb_copied:.1f} MB" if mb_copied < 1024 else f"{mb_copied / 1024:.2f} GB"

        msg = (
            f"Import erfolgreich abgeschlossen!\n\n"
            f"• Neu kopiert: {stats.copied_success} Datei(en) ({size_str})\n"
            f"• Übersprungen (Duplikate/Abgewählt): {stats.duplicates_skipped}\n"
        )
        if stats.failed > 0:
            msg += f"• Fehler: {stats.failed}\n"

        messagebox.showinfo("Import abgeschlossen", msg)



    def _eject_source_drive(self):
        src_path = self.var_source.get().strip()
        if not src_path:
            messagebox.showwarning("Hinweis", "Kein Quellordner ausgewählt.")
            return

        success, msg = eject_drive(src_path)
        if success:
            messagebox.showinfo("Laufwerk ausgehängt", msg)
            self.scan_items = []
            self.thumb_cache.clear()
            self.lbl_status.configure(text="Speicherkarte ausgehängt.")
            self._refresh_drives()
            self._render_table_items()
        else:
            messagebox.showwarning("Aushängen fehlgeschlagen", msg)


def run_gui():
    set_high_dpi()
    root = ctk.CTk()
    app = FotoDownApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
