# 📦 Installationsanleitung für FotoDown

Diese Anleitung führt Sie Schritt für Schritt durch die Installation von **FotoDown** unter **Windows** sowie unter **Linux** (mit speziellem Fokus auf **alle Arch Linux Varianten**).

---

## Inhaltsverzeichnis

1. [Systemanforderungen](#-systemanforderungen)
2. [Installationsanleitung für Windows](#-windows-10--11)
   - [Methode 1: 1-Klick-Installation (Empfohlen)](#methode-1-1-klick-installation-empfohlen)
   - [Methode 2: Manuelle Installation](#methode-2-manuelle-installation)
3. [Installationsanleitung für Linux & Arch Linux](#-linux--arch-linux-varianten)
   - [Unterstützte Arch-Distributionen](#unterstützte-arch-distributionen)
   - [Methode 1: Automatischer Schnell-Installer (`install_linux.sh`)](#methode-1-automatischer-schnell-installer)
   - [Methode 2: Native Installation via `pacman` (Arch-Standard)](#methode-2-native-installation-via-pacman-arch-standard)
   - [Methode 3: Isolierte Virtual-Environment (`.venv`, PEP 668)](#methode-3-isolierte-virtual-environment-venv)
   - [Desktop-Integration & Anwendungsmenü](#desktop-integration--anwendungsmenü)
   - [Grafikserver: Wayland vs. X11](#grafikserver-wayland-vs-x11)
   - [Speicherkarten-Zugriffsrechte (udisks2)](#speicherkarten-zugriffsrechte-udisks2)
4. [Andere Linux-Distributionen (Debian, Ubuntu, Fedora)](#-andere-linux-distributionen)
5. [Häufige Fragen & Fehlerbehebung (Troubleshooting)](#-häufige-fragen--fehlerbehebung)

---

## 💻 Systemanforderungen

- **Betriebssystem:**
  - Windows 10 (64-Bit) oder Windows 11
  - Linux (beliebige moderne Distribution, z. B. Arch Linux, Manjaro, EndeavourOS, Ubuntu, Fedora)
- **Python:** Version 3.10 oder neuer
- **Grafikoberfläche:** Beliebiger Desktop (KDE Plasma, GNOME, XFCE, Cinnamon, Sway, Hyprland etc.)
- **Freier Speicherplatz:** ca. 150 MB für Abhängigkeiten

---

## 🪟 Windows (10 / 11)

### Methode 1: 1-Klick-Installation (Empfohlen)

1. Stellen Sie sicher, dass **Python** auf Ihrem System installiert ist:
   - Download: [python.org/downloads](https://www.python.org/downloads/)
   - > [!IMPORTANT]
     > Achten Sie bei der Python-Installation unbedingt darauf, das Häkchen bei **„Add python.exe to PATH“** zu setzen!
2. Laden Sie FotoDown herunter oder entpacken Sie das ZIP-Archiv in ein Verzeichnis Ihrer Wahl.
3. Führen Sie im FotoDown-Ordner die Datei **`install_windows.bat`** per Doppelklick aus.
4. Das Skript erledigt alles automatisch:
   - Richtet eine isolierte virtuelle Umgebung (`.venv`) ein
   - Installiert alle Abhängigkeiten (`PySide6`, `Pillow`)
   - Erstellt eine **Desktop-Verknüpfung** mit individuellem FotoDown-Kamera-Icon
5. Sie können FotoDown nun direkt vom Desktop oder über **`FotoDown.bat`** starten.

---

### Methode 2: Manuelle Installation

Falls Sie die Schritte manuell in der Eingabeaufforderung (CMD) oder PowerShell ausführen möchten:

```cmd
:: 1. In das Verzeichnis von FotoDown wechseln
cd C:\Pfad\zu\FotoDown

:: 2. Virtuelle Python-Umgebung erstellen
python -m venv .venv

:: 3. Virtuelle Umgebung aktivieren
call .venv\Scripts\activate

:: 4. Paketmanager aktualisieren und Bibliotheken installieren
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 5. FotoDown starten
python fotodown.py
```

---

## 🐧 Linux & Arch Linux Varianten

### Unterstützte Arch-Distributionen

Diese Anleitung gilt für **alle** auf Arch Linux basierenden Betriebssysteme:
- **Arch Linux** (Standard)
- **Manjaro Linux**
- **EndeavourOS**
- **Garuda Linux**
- **ArcoLinux**
- **CachyOS**
- **Artix Linux**
- Sowie alle weiteren Derivate mit `pacman`-Paketverwaltung.

---

### Methode 1: Automatischer Schnell-Installer

Der einfachste und schnellste Weg unter Arch Linux und allen Derivaten:

1. Öffnen Sie ein Terminal im FotoDown-Ordner.
2. Führen Sie das mitgelieferte Installationsskript aus:
   ```bash
   chmod +x install_linux.sh
   ./install_linux.sh
   ```
3. Das Skript:
   - Erkennt Ihre Arch-Distribution automatisch.
   - Bietet die Installation empfohlener Systembibliotheken an (`qt6-base`, `qt6-wayland`).
   - Erstellt eine saubere, PEP-668-konforme virtuelle Umgebung (`.venv`).
   - Installiert alle Abhängigkeiten.
   - Setzt Ausführungsrechte für alle Starter.
   - Bindet **FotoDown automatisch in Ihr Anwendungsmenü** (KDE, GNOME, Rofi etc.) mit vollem Icon-Support ein.

---

### Methode 2: Native Installation via `pacman` (Arch-Standard)

Arch Linux bietet den Vorteil, dass alle benötigten Bibliotheken direkt als offizielle, performante Systempakete im Repository vorliegen. Dadurch ist kein separates `pip`-Virtualenv zwingend erforderlich:

```bash
# 1. Systempakete via Pacman installieren
sudo pacman -S --needed python python-pyside6 python-pillow qt6-base qt6-wayland

# 2. In das FotoDown-Verzeichnis wechseln
cd /pfad/zu/FotoDown

# 3. Starter ausführbar machen
chmod +x fotodown.sh fotodown.py

# 4. FotoDown starten
./fotodown.sh
```

---

### Methode 3: Isolierte Virtual-Environment (`.venv`)

Auf Arch Linux ist systemweites `pip install` zum Schutz der Systemstabilität standardmäßig gesperrt (PEP 668). Eine virtuelle Umgebung ist der standardisierte Python-Weg:

```bash
# 1. Basispakete sicherstellen
sudo pacman -S --needed python python-pip python-virtualenv qt6-base qt6-wayland

# 2. Virtuelle Umgebung anlegen
python -m venv .venv

# 3. Umgebung aktivieren und Pakete installieren
source .venv/bin/activate
pip install -r requirements.txt

# 4. FotoDown starten
./fotodown.sh
```

> [!TIP]
> Das Startskript `fotodown.sh` erkennt automatisch, ob eine `.venv` vorhanden ist, und verwendet diese bevorzugt. Sie müssen die Umgebung vor dem Start nicht jedes Mal manuell aktivieren!

---

### Desktop-Integration & Anwendungsmenü

Damit FotoDown im Startmenü Ihres Desktops (KDE Kickoff, GNOME Aktivitäten, XFCE, Rofi, dmenu etc.) erscheint:

```bash
# Verzeichnis für Desktop-Einträge sicherstellen
mkdir -p ~/.local/share/applications

# Starter erzeugen (ersetzen Sie /pfad/zu/FotoDown mit Ihrem echten Pfad)
cat <<EOF > ~/.local/share/applications/fotodown.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=FotoDown
GenericName=Foto-Importeur & EXIF-Manager
Comment=Automatischer Foto- & Video-Import mit EXIF-Umbenennung und Sicherung
Exec=/pfad/zu/FotoDown/fotodown.sh
Icon=/pfad/zu/FotoDown/assets/icon_256.png
Terminal=false
Categories=Graphics;Photography;Utility;
Keywords=Photo;Camera;Import;SD;EXIF;RAW;
StartupNotify=true
EOF

# Ausführungsrecht vergeben und Menü-Cache aktualisieren
chmod +x ~/.local/share/applications/fotodown.desktop
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

---

### Grafikserver: Wayland vs. X11

FotoDown nutzt Qt 6 (PySide6) und läuft nativ unter **Wayland** sowie unter **X11 / Xorg**.

- **Unter Wayland (KDE Wayland, GNOME Wayland, Hyprland, Sway):**
  Stellen Sie sicher, dass das Paket `qt6-wayland` installiert ist:
  ```bash
  sudo pacman -S --needed qt6-wayland
  ```
- **Erzwingen von Wayland:**
  ```bash
  QT_QPA_PLATFORM=wayland ./fotodown.sh
  ```
- **Erzwingen von X11 (Fallback via XWayland):**
  Falls unter Wayland Darstellungsprobleme auftreten:
  ```bash
  QT_QPA_PLATFORM=xcb ./fotodown.sh
  ```

---

### Speicherkarten-Zugriffsrechte (udisks2)

Unter Arch Linux werden Speicherkarten und USB-Laufwerke typischerweise über `udisks2` automatisch unter `/run/media/$USER/<Label>` eingehängt.

- Stellen Sie sicher, dass Ihr Benutzer in der Gruppe `storage` ist (falls erforderlich):
  ```bash
  sudo usermod -aG storage $USER
  ```
- FotoDown erkennt eingehängte Karten in `/run/media/$USER/` und `/media/` automatisch beim Einstecken.

---

## 🐧 Andere Linux-Distributionen

### Debian / Ubuntu / Linux Mint

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv libxcb-cursor0 qt6-base-dev
./install_linux.sh
```

### Fedora / RHEL

```bash
sudo dnf install python3 python3-pip qt6-qtbase-gui qt6-qtwayland
./install_linux.sh
```

---

## ❓ Häufige Fragen & Fehlerbehebung

### Windows: „Der Befehl 'python' ist entweder falsch geschrieben...“
- **Ursache:** Python wurde ohne PATH-Variable installiert.
- **Lösung:** Python-Installer erneut starten, auf *„Modify“* klicken und den Haken bei *„Add Python to environment variables“* setzen.

### Linux/Arch: „error: externally-managed-environment“
- **Ursache:** Arch Linux blockiert systemweite `pip`-Installationen (PEP 668).
- **Lösung:** Nutzen Sie `./install_linux.sh` oder installieren Sie die nativen Pakete mit `sudo pacman -S python-pyside6 python-pillow`.

### Linux: „qt.qpa.plugin: Could not load the Qt platform plugin 'xcb'“
- **Ursache:** Es fehlen X11-Bibliotheken (z. B. `libxcb-cursor`).
- **Lösung auf Arch:**
  ```bash
  sudo pacman -S --needed libxcb xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms
  ```

---

## 🚀 Deinstallation

Da FotoDown keine Dateien im System verstreut, ist die Deinstallation denkbar einfach:

- **Windows:** Löschen Sie den FotoDown-Projektordner und die Desktop-Verknüpfung `FotoDown.lnk`.
- **Linux:**
  ```bash
  rm ~/.local/share/applications/fotodown.desktop
  rm -rf /pfad/zu/FotoDown
  ```
- **Benutzerkonfigurationen entfernen (optional):**
  - Windows: `%LOCALAPPDATA%\FotoDown`
  - Linux: `~/.config/FotoDown` oder `~/.fotodown`
