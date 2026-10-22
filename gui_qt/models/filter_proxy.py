"""Filter proxy model to filter scan items by status, type, and search keyword."""

from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, Qt
from core.importer import ScanItem


class ScanFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._status_filter = "all"  # "all", "new_only", "duplicates_only"
        self._type_filter = "all"    # "all", "Fotos", "RAW", "Videos"
        self._search_term = ""

    def set_status_filter(self, status: str):
        self._status_filter = status
        self.invalidate()

    def set_type_filter(self, type_str: str):
        self._type_filter = type_str
        self.invalidate()

    def set_search_term(self, term: str):
        self._search_term = term.strip().lower()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        idx = model.index(source_row, 0, source_parent)
        item: ScanItem = model.data(idx, Qt.ItemDataRole.UserRole)
        if not item:
            return True

        # Status Filter
        if self._status_filter == "new_only" and item.status != "Neu":
            return False
        elif self._status_filter == "duplicates_only" and not item.is_duplicate:
            return False

        # Media Type Filter
        if self._type_filter != "all":
            if self._type_filter == "Fotos" and item.metadata.media_type not in ("JPG", "PNG", "HEIC", "TIFF", "IMAGE"):
                return False
            elif self._type_filter == "RAW" and not item.metadata.is_raw:
                return False
            elif self._type_filter == "Videos" and not item.metadata.is_video:
                return False

        # Search Query
        if self._search_term:
            query = self._search_term
            matches = (
                query in item.source_path.name.lower() or
                query in item.target_path.name.lower() or
                query in (item.metadata.formatted_camera or "").lower()
            )
            if not matches:
                return False

        return True
