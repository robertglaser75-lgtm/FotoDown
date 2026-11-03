#!/usr/bin/env bash
# ==============================================================================
# FotoDown - Installationsskript für Linux (optimiert für Arch Linux & Derivate)
# Unterstützt: Arch Linux, Manjaro, EndeavourOS, Garuda, ArcoLinux, CachyOS etc.
# ==============================================================================

set -e

# Farben für Terminalausgabe
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}   FotoDown - Installations-Assistent für Linux      ${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Distribution ermitteln
IS_ARCH=false
if [ -f /etc/arch-release ] || grep -q -i "arch\|manjaro\|endeavouros\|garuda\|arcolinux\|cachyos" /etc/os-release 2>/dev/null; then
    IS_ARCH=true
    echo -e "${GREEN}[Info]${NC} Arch Linux (oder Derivat) erkannt."
fi

# 2. System-Abhängigkeiten auf Arch Linux prüfen / installieren
if [ "$IS_ARCH" = true ] && command -v pacman &>/dev/null; then
    echo -e "${YELLOW}Möchten Sie empfohlene System-Pakete (Python, Qt6, Wayland-Support) via pacman installieren? (j/N)${NC}"
    read -r -p "> " answer
    if [[ "$answer" =~ ^[jJyY]$ ]]; then
        echo -e "${BLUE}[Info]${NC} Installiere System-Pakete..."
        sudo pacman -S --needed --noconfirm python python-pip python-virtualenv qt6-base qt6-wayland
    fi
fi

# 3. Python 3 Verfügbarkeit prüfen
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo -e "${RED}[Fehler]${NC} Python 3 wurde nicht gefunden."
    if [ "$IS_ARCH" = true ]; then
        echo "Bitte installieren Sie Python mit: sudo pacman -S python python-pip"
    else
        echo "Bitte installieren Sie Python 3 über Ihren Paketmanager."
    fi
    exit 1
fi

PY_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PY_CMD="python"
fi

echo -e "${GREEN}[OK]${NC} Python gefunden: $($PY_CMD --version)"

# 4. Virtuelle Umgebung (.venv) anlegen (PEP 668 konform)
echo -e "${BLUE}[1/4]${NC} Richte virtuelle Python-Umgebung (.venv) ein..."
if [ ! -d ".venv" ]; then
    $PY_CMD -m venv .venv
    echo -e "${GREEN}[OK]${NC} Virtuelle Umgebung .venv erfolgreich erstellt."
else
    echo -e "${GREEN}[OK]${NC} Bestehende Umgebung .venv gefunden."
fi

# 5. Abhängigkeiten installieren
echo -e "${BLUE}[2/4]${NC} Installiere Python-Abhängigkeiten in .venv..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
echo -e "${GREEN}[OK]${NC} Alle Abhängigkeiten (Pyside6, Pillow) installiert."

# 6. Starter-Skripte ausführbar machen
echo -e "${BLUE}[3/4]${NC} Setze Ausführungsrechte für Skripte..."
chmod +x fotodown.sh fotodown.py
echo -e "${GREEN}[OK]${NC} Skripte sind ausführbar."

# 7. Desktop-Integration (.desktop Starter erstellen)
echo -e "${BLUE}[4/4]${NC} Erstelle Desktop-Eintrag für Anwendungsmenü..."
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"

ICON_PATH="$SCRIPT_DIR/assets/icon_256.png"
if [ ! -f "$ICON_PATH" ]; then
    ICON_PATH="$SCRIPT_DIR/assets/icon.png"
fi

cat <<EOF > "$APP_DIR/fotodown.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=FotoDown
GenericName=Foto-Importeur & EXIF-Manager
Comment=Automatischer Foto- & Video-Import mit EXIF-Umbenennung und Sicherung
Exec="$SCRIPT_DIR/fotodown.sh"
Icon=$ICON_PATH
Terminal=false
Categories=Graphics;Photography;Utility;
Keywords=Photo;Camera;Import;SD;EXIF;RAW;
StartupNotify=true
EOF

chmod +x "$APP_DIR/fotodown.desktop"

# Desktop-Datenbank aktualisieren, falls vorhanden
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo -e "${GREEN}[OK]${NC} Desktop-Starter erstellt: $APP_DIR/fotodown.desktop"
echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}   Installation erfolgreich abgeschlossen!           ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo ""
echo "FotoDown kann jetzt auf folgende Weisen gestartet werden:"
echo "  1. Über das Anwendungsmenü Ihres Desktops (KDE, GNOME, XFCE etc.)"
echo "  2. Im Terminal über: ./fotodown.sh"
echo ""
echo -e "${YELLOW}Möchten Sie FotoDown jetzt starten? (j/N)${NC}"
read -r -p "> " start_now
if [[ "$start_now" =~ ^[jJyY]$ ]]; then
    ./fotodown.sh &
fi

