"""Keyboard navigation definitions and helpers for image switching in Vitrina."""

from typing import Dict, Set, Tuple
from PySide6.QtCore import Qt


NAVIGATION_SCHEMES: Dict[str, dict] = {
    "arrows": {
        "id": "arrows",
        "name": "Nur Pfeiltasten (← Links / → Rechts)",
        "short_name": "Pfeiltasten (← / →)",
        "prev_label": "◀ Zurück [←]",
        "next_label": "Weiter ▶ [→]",
        "hint": "Vorheriges: Pfeil-Links [←] | Nächstes: Pfeil-Rechts [→]",
        "prev_keys": {Qt.Key.Key_Left},
        "next_keys": {Qt.Key.Key_Right},
    },
    "arrows_ad": {
        "id": "arrows_ad",
        "name": "Pfeiltasten & A / D (Kombiniert - Standard)",
        "short_name": "Pfeiltasten & A / D",
        "prev_label": "◀ Zurück [← / A]",
        "next_label": "Weiter ▶ [→ / D]",
        "hint": "Vorheriges: Pfeil-Links [←] oder [A] | Nächstes: Pfeil-Rechts [→] oder [D]",
        "prev_keys": {Qt.Key.Key_Left, Qt.Key.Key_A},
        "next_keys": {Qt.Key.Key_Right, Qt.Key.Key_D},
    },
    "arrows_all": {
        "id": "arrows_all",
        "name": "Pfeiltasten alle Richtungen (← / → & ↑ / ↓)",
        "short_name": "Pfeiltasten (←/→ & ↑/↓)",
        "prev_label": "◀ Zurück [← / ↑]",
        "next_label": "Weiter ▶ [→ / ↓]",
        "hint": "Vorheriges: Pfeil-Links [←] oder Pfeil-Oben [↑] | Nächstes: Pfeil-Rechts [→] oder Pfeil-Unten [↓]",
        "prev_keys": {Qt.Key.Key_Left, Qt.Key.Key_Up},
        "next_keys": {Qt.Key.Key_Right, Qt.Key.Key_Down},
    },
    "ad_only": {
        "id": "ad_only",
        "name": "Nur A / D Tasten (A = Zurück, D = Vor)",
        "short_name": "Nur A / D Tasten",
        "prev_label": "◀ Zurück [A]",
        "next_label": "Weiter ▶ [D]",
        "hint": "Vorheriges: Taste [A] | Nächstes: Taste [D]",
        "prev_keys": {Qt.Key.Key_A},
        "next_keys": {Qt.Key.Key_D},
    },
    "page_keys": {
        "id": "page_keys",
        "name": "Bild auf / Bild ab (Page Up / Page Down)",
        "short_name": "Bild auf / Bild ab",
        "prev_label": "◀ Zurück [PgUp]",
        "next_label": "Weiter ▶ [PgDn]",
        "hint": "Vorheriges: Bild-Auf [PgUp] oder [←] | Nächstes: Bild-Ab [PgDn] oder [→]",
        "prev_keys": {Qt.Key.Key_PageUp, Qt.Key.Key_Left},
        "next_keys": {Qt.Key.Key_PageDown, Qt.Key.Key_Right},
    },
    "all": {
        "id": "all",
        "name": "Alle Tasten (Pfeile, A/D, Bild auf/ab)",
        "short_name": "Alle Navigationstasten",
        "prev_label": "◀ Zurück [← / A]",
        "next_label": "Weiter ▶ [→ / D]",
        "hint": "Vorheriges: [←], [A] oder [PgUp] | Nächstes: [→], [D] oder [PgDn]",
        "prev_keys": {Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_A, Qt.Key.Key_PageUp},
        "next_keys": {Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_D, Qt.Key.Key_PageDown},
    },
}

DEFAULT_NAVIGATION_SCHEME = "arrows_ad"


def is_nav_prev(key: int, scheme: str = DEFAULT_NAVIGATION_SCHEME) -> bool:
    """Returns True if the given Qt key triggers navigating to the previous photo."""
    info = NAVIGATION_SCHEMES.get(scheme, NAVIGATION_SCHEMES[DEFAULT_NAVIGATION_SCHEME])
    return key in info["prev_keys"]


def is_nav_next(key: int, scheme: str = DEFAULT_NAVIGATION_SCHEME) -> bool:
    """Returns True if the given Qt key triggers navigating to the next photo."""
    info = NAVIGATION_SCHEMES.get(scheme, NAVIGATION_SCHEMES[DEFAULT_NAVIGATION_SCHEME])
    return key in info["next_keys"]


def get_nav_labels(scheme: str = DEFAULT_NAVIGATION_SCHEME) -> Tuple[str, str]:
    """Returns (prev_button_label, next_button_label) for the given scheme."""
    info = NAVIGATION_SCHEMES.get(scheme, NAVIGATION_SCHEMES[DEFAULT_NAVIGATION_SCHEME])
    return info["prev_label"], info["next_label"]


def get_nav_hint(scheme: str = DEFAULT_NAVIGATION_SCHEME) -> str:
    """Returns user-facing shortcut hint string for status/tooltips."""
    info = NAVIGATION_SCHEMES.get(scheme, NAVIGATION_SCHEMES[DEFAULT_NAVIGATION_SCHEME])
    return info["hint"]
