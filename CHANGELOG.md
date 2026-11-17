# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.25.0] - 2026-11-17

### Hinzugefügt & Verbessert
- **Massiver Performance- & Darstellungs-Boost bei Vorschauen und Culling:**
  - **7,5-mal schnellere Thumbnail-Konvertierung ([`gui_qt/workers/thumb_worker.py`](gui_qt/workers/thumb_worker.py)):**
    - Ersatz der CPU-intensiven PNG-Zwischencodierung im RAM durch direkte, verlustfreie Speicherübergabe (`QImage(raw_bytes, ...)`).
  - **Vollständig asynchrones Multithreading im Filmstrip ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
    - Filmstrip-Miniaturbilder werden nun parallel über Hintergrund-Threads (`QThreadPool.globalInstance()`) geladen. Der Haupt-GUI-Thread bleibt zu 100 % flüssig und frei von Rucklern.
  - **LRU-Speichercache & Lookahead-Prefetching ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/views/single_view.py`](gui_qt/views/single_view.py)):**
    - Hochauflösende Vorschau-Pixmaps werden im RAM gecacht. Hin- und Herwechseln zwischen Fotos (z. B. zum Schärfevergleich mit `A`/`D`) erfolgt verzögerungsfrei in **0 ms ohne erneuten Festplattenzugriff**.
    - Während ein Foto betrachtet wird, lädt ein Hintergrund-Worker benachbarte Bilder ($N+1$, $N-1$, $N+2$) im Voraus in den Cache, sodass das nächste Bild beim Tastendruck sofort bereitsteht.
  - **Skalierungs-Caching in Galerie-Karten ([`gui_qt/views/delegates.py`](gui_qt/views/delegates.py)):**
    - Vermeidet teure Neuberechnungen von `SmoothTransformation` bei jedem einzelnen Scroll-Frame der Galerie.
  - **High-DPI-Schärfe & 4K-UHD-Vorschauqualität ([`core/thumbnail.py`](core/thumbnail.py), [`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/views/single_view.py`](gui_qt/views/single_view.py)):**
    - Berücksichtigung von `devicePixelRatioF()` verhindert Interpolationsunschärfen auf 4K-, UHD- und 125%/150%-skalierten Bildschirmen.
    - Anhebung der maximalen Vorschaudimension von 2560px auf 3840px (4K) für deutlich höhere Detailtreue. Volle native Auflösung ohne Skalierung bei `max_dim <= 0`.
  - **In-Memory-Beschleunigung beim Ordnerscan ([`gui_qt/models/culling_model.py`](gui_qt/models/culling_model.py)):**
    - Tausende redundante `os.path.exists()`-Netzwerkzugriffe auf NAS- und Dateisysteme werden durch In-Memory-Sets und Monatsordner-Caching ersetzt.

## [0.24.0] - 2026-11-15

### Hinzugefügt & Verbessert
- **Konfigurierbare Abgleich-Methoden im Einstellungsmenü ([`gui_qt/dialogs/settings_dialog.py`](gui_qt/dialogs/settings_dialog.py), [`core/config.py`](core/config.py), [`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py)):**
  - Neue Konfigurationsoption *„Dateiabgleich-Methode (Sichern & Archivieren)“* (`transfer_reconcile_method`) im Einstellungsmenü unter *„🏠 NAS & Archivierung“*:
    - **📁 Namensgleichheit (Dateiname):** Blitzschneller Abgleich über Dateinamen (Groß-/Kleinschreibung tolerant).
    - **📅 EXIF-Aufnahmezeit (`DateTimeOriginal`):** Gleicht Fotos über ihren exakten Metadaten-Aufnahmezeitpunkt ab. Erkennt Fotos auch dann zuverlässig als vorhanden, wenn sie beim Import oder Archivieren umbenannt wurden.
    - **🔒 SHA-256 Prüfsumme:** Bit-genauer Inhaltsabgleich zur 100%igen Duplikatserkennung (optimiert mit Dateigrößen-Vorfilterung zur Minimierung von Netzwerklasten).
  - Anzeige der aktuell aktiven Methode im Ausklappmenü des Abgleich-Buttons inklusive Schnellzugriff auf die Programmeinstellungen.
  - Das Status-Label im Aktionsbereich zeigt nun transparent die verwendete Methode an (z. B. *„✓ 14 fehlende RAWs markiert (EXIF-Zeit)“* oder *„✓ Ziel aktuell (0 fehlen, SHA-256)“*).

## [0.23.0] - 2026-11-13

### Hinzugefügt & Verbessert
- **Dateiabgleich & automatische Markierung fehlender Dateien (JPG, RAW, beide) ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py), [`gui_qt/styles/icons.py`](gui_qt/styles/icons.py)):**
  - Neuer Button *„Abgleich ▾“* im zentralen Aktionsbereich von *3. Sichern & Archivieren*:
    - **Fehlende JPGs markieren:** Ermittelt alle JPG-Dateien, die links vorhanden sind, aber im rechten Zielordner noch fehlen, und markiert sie.
    - **Fehlende RAWs markieren:** Ermittelt alle RAW-Dateien, die links vorhanden sind, aber rechts noch fehlen, und markiert sie.
    - **Beides (RAW & JPG) markieren:** Ermittelt alle fehlenden Bilddateien auf einmal und markiert sie für den Transfer.
  - Die nicht vorhandenen Dateien werden direkt links zur Übertragung ausgewählt, sodass sie mit einem einzigen Klick auf *„Kopieren“* (oder *„Verschieben“*) gesichert werden können.
  - Sofortiges visuelles Feedback über ein Status-Label im Aktionsbereich (z. B. *„✓ 14 fehlende RAWs links markiert“* oder *„✓ Ziel aktuell (0 fehlen)“*).
  - Neues Vektor-Icon `get_search_icon` in `gui_qt/styles/icons.py` für Lupe/Abgleich.
- **Vollständige Pfadanzeige beim Einstiegspunkt der Ordnerauswahl ([`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - Beim Einstiegspunkt im Verzeichnisbaum (sowohl in *2. Sichten & Sortieren* als auch in *3. Sichern & Archivieren*) wird nun der vollständige Pfad angezeigt statt nur der Ordnername.
  - Das Einstiegspunkt-Label neben der Schaltfläche *„Einstiegspunkt...“* zeigt den vollständigen Pfad mit automatischem Zeilenumbruch und Textselektion per Maus an.
  - Der Wurzelknoten des Verzeichnisbaums selbst stellt ebenfalls den vollständigen Pfad dar, während Unterordner weiterhin übersichtlich als relative Ordnernamen dargestellt werden.

## [0.22.0] - 2026-11-10

### Hinzugefügt & Verbessert
- **Spalten-Konfiguration im Verzeichnisbaum (`Bilder`, `RAW`, `JPG`) ([`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py), [`core/config.py`](core/config.py)):**
  - Neues Spalten-Menü (Symbolbutton in der Header-Leiste sowie Rechtsklick auf die Tabellenkopfzeile) zum individuellen Ein- und Ausschalten der Spalten **Bilder**, **RAW** und **JPG**.
  - Die gewählten Spalteneinstellungen (`tree_show_col_bilder`, `tree_show_col_raw`, `tree_show_col_jpg`) werden dauerhaft in der Konfiguration gespeichert.
- **Vektor-Icons statt Emojis & Laptop-optimiertes Kompakt-Layout ([`gui_qt/styles/icons.py`](gui_qt/styles/icons.py), [`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py)):**
  - Einheitliche, gestochen scharfe QPainter-Vektoricons (`get_sort_icon`, `get_columns_icon`, `get_files_icon`, `get_list_icon`, `get_grid_icon`, `get_check_all_icon`, `get_uncheck_all_icon`, `get_invert_icon`, `get_quick_icon`, `get_clear_icon`, `get_arrow_right_icon`, `get_move_icon`, `get_swap_icon`) für alle Buttons.
  - **Anzeigearten über eine einzige Dropdown-Liste (`combo_view_mode`):** Zusammenfassung von *Liste*, *Vorschau: Klein*, *Vorschau: Mittel* und *Vorschau: Groß* in eine kompakte Auswahlbox statt mehrerer separater Buttons.
  - Kompakte Icon-Schaltflächen für Markierung (*Alle*, *Keine*, *Invertieren*) sowie schmalere Aktionsspalte (`156px`) und niedrigere Mindestbreiten (`260px` je Seite) für optimale Bedienbarkeit auch auf kleineren Laptopbildschirmen.

## [0.21.0] - 2026-11-10

### Hinzugefügt
- **Ein-/Ausschaltbare Dateianzeige und flexible Sortierreihenfolge ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py), [`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - **Dateianzeige in den Ordnern ein-/ausschalten (*„📄 Dateien“*):**
    - Sowohl auf der Quell- als auch auf der Zielseite (NAS) lässt sich der Dateibereich in der oberen Ordnerleiste per Klick auf *„📄 Dateien“* ein- oder ausblenden.
    - Beim Ausblenden erweitert sich der Verzeichnisbaum auf die volle Breite der jeweiligen Seite, und unnötiges Scannen großer Ordner (z. B. beim reinen Navigieren durch NAS-Zielordner) wird übersprungen. Beim Wiedereinschalten werden die Dateien sofort geladen; *„Alle kopieren / verschieben“* scannt bei Bedarf automatisch.
  - **Frei wählbare Sortierreihenfolge für Dateien (Listen- & Vorschauansicht):**
    - Auswahlfeld *„Sortierung“*: Sortieren nach **Name**, **Datum (Änderung)**, **Größe**, **Dateityp** oder **Bewertung (★)**.
    - Umschaltbutton **„↑ Auf.“ / „↓ Ab.“** für aufsteigende oder absteigende Reihenfolge – wirkt synchron auf Tabellen- und Kachel-Vorschau.
    - Klicks auf die Spaltenüberschriften in der Listenansicht aktualisieren Sortierkriterium und -richtung direkt mit.
  - **Sortierreihenfolge im Verzeichnisbaum (`CullingDirectoryTreeWidget`):**
    - Neue Schaltfläche **„↑“ / „↓“** im Verzeichnisbaum-Header (sowohl in *2. Sichten & Sortieren* als auch in *3. Sichern & Archivieren*) zum Umschalten der Ordnersortierung zwischen Aufsteigend (A–Z) und Absteigend (Z–A).

## [0.20.3] - 2026-11-10

### Behoben
- **Verzeichnisbaum-Größenänderung und Wiederherstellung im Tab „3. Sichern & Archivieren“ ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py)):**
  - `setChildrenCollapsible(False)` für sowohl den inneren Teiler (`pane_splitter`) als auch den Hauptteiler (`main_splitter`) aktiviert, damit der Verzeichnisbaum beim Ziehen über den Splitter nicht mehr auf `0 px` einklappt.
  - Verbreiterter, gut sichtbarer Splitter-Griff (`6px`) mit Hover-Hervorhebung sowie sinnvolle Mindestbreiten (`140px` für den Verzeichnisbaum, `180px` für die Dateiansicht).
  - Ein-/Ausklappen des Baums (*„📂 Baum“* bzw. Klapp-Symbol) speichert die letzte gültige Breite und stellt diese beim erneuten Öffnen zuverlässig wieder her.

## [0.20.2] - 2026-11-08

### Verbessert
- **Horizontale Anordnung der Verzeichnisbäume jeweils links neben den Bildern ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py)):**
  - **Quellseite (Laptop / Bearbeiten):** Der Verzeichnisbaum (`CullingDirectoryTreeWidget`) befindet sich nun auf der linken Seite des Quellbereichs; rechts daneben liegt die Bildansicht (Liste/Kacheln mit Filtern und Markierungs-Tools).
  - **Zielseite (NAS / Archiv):** Ebenso befindet sich der Verzeichnisbaum auf der linken Seite des Sicherungsbereichs mit den Zielbildern auf der rechten Seite.
  - **Horizontaler Teiler:** Beide Seiten nutzen einen stufenlos verschiebbaren horizontalen Splitter inklusive Ein-/Ausblend-Möglichkeit (*„📂 Baum“*).

## [0.20.1] - 2026-11-08

### Verbessert
- **Einheitliche Verzeichnisauswahl im Schritt „3. Sichern & Archivieren“ identisch zu „Sichten & Sortieren“ ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py), [`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - **Hierarchischer Verzeichnisbaum (`CullingDirectoryTreeWidget`):** Sowohl auf der Quellseite (Laptop) als auch auf der Zielseite (NAS/Speicher) ist nun exakt derselbe interaktive Verzeichnisbaum wie im Sichten-Tab integriert.
  - **Live-Zähler pro Ordner:** Zeigt auch beim Übertragen für jedes Verzeichnis direkt die getrennten Bildzähler (`Bilder`, `RAW`, `JPG`) an.
  - **Einstellbarer Einstiegspunkt & Navigation:** Freie Wahl des Basisordners via *„Einstiegspunkt...“*, Ausklappen/Einklappen (`+`/`-`), Aktualisieren (`🔄`) und direkte Ordnerauswahl per Mausklick.
  - **Vertikaler Teiler (Splitter):** Flexibles Verschieben des Teilers zwischen Verzeichnisbaum und Bildansicht sowie 1-Klick-Schaltfläche zum Ein-/Ausblenden des Baums (*„📂 Baum“*) für maximale Bildhöhe.

## [0.20.0] - 2026-11-08

### Hinzugefügt
- **Neuer Workflow-Schritt „3. Sichern & Archivieren“ (Tab 3) für NAS- & Speicher-Transfer ([`gui_qt/views/transfer_tab.py`](gui_qt/views/transfer_tab.py), [`gui_qt/workers/transfer_worker.py`](gui_qt/workers/transfer_worker.py)):**
  - **2-geteilte Benutzeroberfläche (Dual-Pane):**
    - **Linke Seite (PC / Laptop / Quelle):** Ordnerauswahl mit Schnellzugriff (letzter Culling-Ordner, Import-Ziel, Windows-Bilder), Dateiliste mit Vorschaubildern, anpassbare Filter (RAW, JPG, RAW+JPG, Videos, Bearbeitet mit XMP) und Textsuchfeld.
    - **Rechte Seite (NAS / Speicher / Archiv / Album):** Zielordnerauswahl mit Schnellzugriff (NAS-Archiv, Familienalbum, Unterordner erstellen), identische Filter- und Darstellungsoptionen.
    - **Mittlere Aktionsspalte:** Schaltflächen mit Richtungspfeilen für *„▶ Kopieren (Auswahl)“*, *„➔ Verschieben (Auswahl)“*, *„▶▶ Alle kopieren“* und *„➔➔ Alle verschieben“*, Button *„⇄ Seiten tauschen“* sowie Fortschrittsanzeige mit Abbrechen-Funktion.
  - **Flexible Anzeige- und Markierungs-Tools:**
    - Umschaltung zwischen detaillierter **Listenansicht** (Tabelle mit Checkbox, Dateiname, Typ, Größe, Änderungsdatum, Status/Rating) und **Vorschau-Kachelansicht** (Grid mit asynchron nachladenden Thumbnails).
    - Einstellbare Vorschaubild-Größen: *Klein (80px)*, *Mittel (140px)*, *Groß (200px)*.
    - Markierungswerkzeuge: *☑ Alle auswählen*, *☐ Keine*, *🔄 Invertieren* sowie interaktive Checkboxen und Standard-Mehrfachauswahl mit Live-Zähler (*„X von Y markiert (Z MB)“*).
  - **Sichere Übertragungs-Engine (`TransferWorker`):**
    - Kopiert oder verschiebt Mediendateien im Hintergrund ohne Einfrieren der Benutzeroberfläche.
    - Vollständige automatische Synchronisation von Begleitdateien (*`.xmp`*-Sidecars für RAW/Darktable).
    - Sicherheitsvalidierung beim Verschieben (Überprüfung der geschriebenen Dateigröße am Ziel vor dem Löschen der Quelldateien).
  - **Integration in Hauptfenster und Kopfleiste ([`gui_qt/widgets/header_banner.py`](gui_qt/widgets/header_banner.py), [`gui_qt/main_window.py`](gui_qt/main_window.py)):**
    - Neuer Reiter *„💾 3. Sichern & Archivieren“* in der Kopfleiste.
    - Nahtlose Verknüpfung im 3-Stufen-Workflow (1. Importieren ➔ 2. Sichten & Sortieren ➔ 3. Sichern & Archivieren).

## [0.19.3] - 2026-11-08

### Verbessert
- **Optimierung der Benutzeroberfläche vor und während des Foto-Ladevorgangs ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/key_navigation.py`](gui_qt/key_navigation.py)):**
  - **Bildarbeitsfläche (Canvas):** Anstelle eines leeren schwarzen Bereichs wird vor und während des Ladevorgangs ein ansprechender, zentrierter Platzhalter mit passendem Status angezeigt (*„Kein Foto ausgewählt“*, *„Fotos werden eingelesen...“* bzw. *„Vorschau wird vorbereitet...“*).
  - **Seitenleiste vor dem Laden bereinigt:**
    - Die Aktions-Schaltflächen (Vorheriges, Nächstes, 100% Zoom, Sterne 1–5, Pick/Reject, Workflow-Status, externe Editoren) sind im Leerzustand sauber deaktiviert.
    - Vorzeitige Anzeige von *„Ansicht: Auto“* ohne geladene Fotos entfernt.
    - Leere Textzeilen unter dem Dateinamen ausgeblendet.
    - Statistikkarte zeigt vor dem Laden *„Kein Ordner geöffnet“* und während des Einlesens präzise den aktuellen Fortschritt anstelle eines statischen *„Scan läuft: 100%“*.
  - **Button-Beschriftung ohne Textüberlauf:**
    - Kompakte, lesbare Navigationsbeschriftungen (*„◀ Zurück [←/A]“*, *„Weiter ▶ [→/D]“*) verhindern unschönes Abschneiden des Weiter-Buttons in der Seitenleiste.
  - **Konsistente Statusmeldungen:** Der Fortschrittsbalken und die Statusmeldungen behalten durchgängig das Schema *„Lese Fotos ein...“* bei.

## [0.19.2] - 2026-11-08

### Verbessert
- **Pulsierender / blinkender Ladebalken während der Bildvorbereitung ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - Nach Abschluss des Verzeichnis-Scans („Lese Fotos ein: 100%“) bleibt der Fortschrittsbalken nun aktiv sichtbar und blinkt/pulsiert sanft (`QPropertyAnimation` auf `QGraphicsOpacityEffect`), während im Hintergrund die Ordnerdaten, Filter, der Filmstreifen initialisiert und das erste Foto gerendert werden.
  - Sobald das erste Foto auf der Arbeitsfläche angezeigt wird, wird das Blinken gestoppt und der Fortschrittsbalken automatisch ausgeblendet.

## [0.19.1] - 2026-11-08

### Verbessert
- **Bereinigung Lade-Rückmeldung beim Foto-Scan ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - Separater Schriftzug *„Lade Fotos...“* auf der Bildfläche und in der Seitenleiste entfernt.
  - Der Fortschrittsbalken mit Statusanzeige *„Lese Fotos ein: X von Y (Z%) • Dateiname“* liefert bereits präzises, kontinuierliches Feedback, sodass keine redundante zusätzliche Ladeanzeige mehr eingeblendet wird.

## [0.19.0] - 2026-11-07

### Hinzugefügt
- **Konfigurierbare Tastenbelegung für Bildwechsel / Weiterschalten ([`gui_qt/key_navigation.py`](gui_qt/key_navigation.py), [`core/config.py`](core/config.py)):**
  - Neues modulares Navigationssystem mit frei wählbaren Tasten-Schemata für das Weiterschalten zwischen Fotos in der Einzelansicht und beim Sichten:
    - **Nur Pfeiltasten (← Links / → Rechts):** Reine Pfeiltastennavigation, verhindert versehentliches Schalten über A/D.
    - **Pfeiltasten & A / D (Kombiniert - Standard):** Parallele Unterstützung von Pfeiltasten und Tastaturkürzeln `A` (Vorheriges) und `D` (Nächstes).
    - **Pfeiltasten alle Richtungen (← / → & ↑ / ↓):** Weiterschalten über Links/Rechts oder Oben/Unten.
    - **Nur A / D Tasten (A = Zurück, D = Vor):** Kompakte Einhand-Tastaturnavigation.
    - **Bild auf / Bild ab (Page Up / Page Down):** Schnelles Blättern über die Standard-Dokumentnavigationstasten.
    - **Alle gängigen Navigationstasten:** Unterstützung sämtlicher Navigationsvarianten.
- **Mausrad-Weiterschalten ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/views/single_view.py`](gui_qt/views/single_view.py)):**
  - Optionale Einstellung `navigation_enable_mouse_wheel`: Erlaubt das komfortable Durchblättern von Fotos mit dem Mausrad (solange nicht vergrößert / 100% Zoom aktiv ist).
- **Zahnrad-Menü Direktumschaltung ([`gui_qt/widgets/header_banner.py`](gui_qt/widgets/header_banner.py)):**
  - Schnelle 1-Klick-Auswahl des gewünschten Navigationsschemas direkt im Dropdown-Menü des oberen Einstellungs-Zahnrads über exklusive Radio-Aktionen.
- **Einstellungsdialog Integration ([`gui_qt/dialogs/settings_dialog.py`](gui_qt/dialogs/settings_dialog.py)):**
  - Gruppe *„Tastatur & Bild-Navigation (Weiterschalten)“* im Tab *„👁️ Einzelansicht“* mit Auswahlliste, dynamischem Hinweistext und Mausrad-Option.
- **Dynamische Button-Beschriftungen & Tooltips:**
  - Die Navigations-Buttons (`btn_prev` und `btn_next`) in Tab 1 und Tab 2 aktualisieren ihre Beschriftung (`◀ Vorheriges [←]`, `Nächstes ▶ [→]`) sowie Tooltips automatisch anhand des gewählten Schemas.
  - Das Viewport-Widget leitet Tastaturereignisse zuverlässig an die übergeordnete Ansicht weiter, auch wenn die Bildfläche Fokus besitzt.

## [0.18.2] - 2026-11-07

### Verbessert
- **Bereinigung redundanter Hinweis-Symbole ([`gui_qt/widgets/header_banner.py`](gui_qt/widgets/header_banner.py), [`gui_qt/views/single_view.py`](gui_qt/views/single_view.py), [`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - **Zahnrad-Button rechts oben:** Doppeltes Zahnradsymbol entfernt; die Schaltfläche zeigt nun ausschließlich das saubere Vektor-Zahnradicon ohne redundanten Text `"⚙️"`.
  - **Bewertungsanzeige:** Überflüssiges Präfix-Symbol `⭐` vor den eigentlichen Sternen entfernt. Bewertungen werden direkt als Sterne (`★★★`, `0★` bzw. mit Pick/Reject/Workflow-Status) dargestellt.
  - **Belichtungsanzeige:** Unnötiges `⚙️`-Symbol vor den Belichtungswerten (Blende, Verschlusszeit, ISO) entfernt.

## [0.18.1] - 2026-11-07

### Verbessert
- **Pulsierende Lade-Animation bei „Lade Fotos...“ ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - Sanftes, langsames Blinken/Atmen (`QPropertyAnimation` mit `InOutSine`-Kurve, 1400ms Zyklus) des Schriftzugs *„Lade Fotos...“* in der Seitenleiste sowie mittig auf der Bildarbeitsfläche während des Ordnereinlesens.
  - Verhindert den Eindruck eines hängenden Programms bei großen Verzeichnissen mit hunderten RAW- und Bilddateien.
  - Sauberes Beenden der Animation und Wiederherstellung voller Deckkraft, sobald der Scan abgeschlossen oder abgebrochen wird.

## [0.18.0] - 2026-11-06

### Hinzugefügt
- **Zentrales Konfigurationsmenü & Zahnrad-Symbol ([`gui_qt/widgets/header_banner.py`](gui_qt/widgets/header_banner.py), [`gui_qt/dialogs/settings_dialog.py`](gui_qt/dialogs/settings_dialog.py)):**
  - **Zahnrad-Button rechts oben:** Neuer Button `[ ⚙️ ]` in der oberen Kopfzeile mit Vektor-Zahnrad-Icon ([`gui_qt/styles/icons.py`](gui_qt/styles/icons.py)) und Dropdown-Konfigurationsmenü.
  - **Schnellzugriffs-Menü:** Direktes Umschalten sichtbarer Einzelansicht-Optionen per 1-Klick-Checkboxen im Menü sowie Direktsprünge zu Einstellungsbereichen.
  - **Umfassender Einstellungsdialog (`SettingsDialog`):** Strukturierte Konfiguration in 5 übersichtlichen Tabs:
    - 👁️ **Einzelansicht:** Konfiguration aller sichtbaren Datei- und Metadaten-Felder mit interaktivem Live-Vorschaubereich.
    - 📥 **Import & Organisation:** RAW/JPG-Kopplung, Sidecars, Duplikatsprüfung, Prüfsummen.
    - 🏠 **NAS & Familienalbum:** Zielpfade und Struktur mit Ordnerauswahl.
    - 🎨 **Externe Editoren:** Darktable & Topaz Pfade, Aussortieren-Aktion.
    - ✍️ **IPTC & Copyright:** Urheberrecht-Einbettung beim Import.
- **Konfigurierbare Einzelansicht ([`gui_qt/views/single_view.py`](gui_qt/views/single_view.py), [`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`core/config.py`](core/config.py)):**
  - Granulare Anzeige-Optionen für die Großbildanzeige in Tab 1 und Tab 2:
    - **Name des Bildes:** Dateiname ein- oder ausblenden.
    - **Dateiendung:** Format (.JPG, .ORF, .CR3...) anzeigen oder ausblenden.
    - **Sterne und sonstige Bewertungen:** Sterne (1–5★), Behalten [P], Abgelehnt [X] und Workflow-Status (SOOC, Zu bearbeiten, Bearbeitet).
    - **Speicherort:** Ordnerpfad auf der Festplatte / SD-Karte / NAS.
    - **Kamera & Objektiv:** Kameramodell und verwendetes Objektiv.
    - **Belichtungsdaten:** Blende, Verschlusszeit, ISO, Brennweite.
    - **Aufnahmedatum & Uhrzeit.**
    - **Dateigröße & Dimensionen (Megapixel).**
  - Echtzeit-Aktualisierung: Änderungen im Menü oder Dialog werden sofort ohne Neustart auf das aktuell angezeigte Foto angewendet.

## [0.17.0] - 2026-11-06

### Hinzugefügt
- **Foto-Workflow & Bearbeitungsstatus in Tab 2 („Sichten & Sortieren“):**
  - **Neue Workflow-Steuerungskarte in der linken Seitenleiste ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
    - Direkte Klassifizierung des Bearbeitungsstandes für jedes Foto bzw. RAW+JPG-Paar:
      - 📸 **SOOC ok [Q]:** Qualität passt direkt aus der Kamera (keine RAW-Entwicklung nötig).
      - 🎨 **Zu bearbeiten [B]:** Zur RAW-/KI-Nachbearbeitung in Darktable oder Topaz vorgemerkt.
      - ✔ **Bearbeitung fertig [E]:** Bild wurde bereits entwickelt, optimiert und exportiert.
    - Schnelle Einhandbedienung über Tastaturkürzel <kbd>Q</kbd>, <kbd>B</kbd>, <kbd>E</kbd> mit optischer Hervorhebung der aktiven Schaltflächen.
    - Farblich kodierte Status-Badges im aktiven Bildheader und im Filmstreifen.
  - **Automatische Darktable-Bearbeitungserkennung ([`core/xmp_sync.py`](core/xmp_sync.py)):**
    - Auswertung von `darktable:history_end` in `.xmp`-Sidecars: Fotos mit bestehender Bearbeitungshistorie werden automatisch als *„In Bearbeitung (Darktable)“* erkannt.
  - **Automatische Erkennung von Familienalbum-Exporten ([`gui_qt/models/culling_model.py`](gui_qt/models/culling_model.py)):**
    - Prüft automatisch, ob für ein Bild bereits ein entwickelter Export im NAS-Familienalbum (`0001_Unsere_Fotos/{YYYY}/{MM}/`) oder als lokale Exportdatei (`_edit.jpg`, `_dt.jpg`, `darktable_exported/`) vorliegt.
    - Automatisches Setzen des Status auf *„✔ Album-Export“* mit Tooltip zum genauen NAS-Dateipfad.
  - **XMP-Metadaten-Synchronisierung ([`core/xmp_sync.py`](core/xmp_sync.py)):**
    - Speichert den Workflow-Status standardkonform im Tag `fotodown:WorkflowStatus` im XMP-Sidecar, sodass der Bearbeitungsstand systemunabhängig und dateibasiert erhalten bleibt.
  - **Workflow-Filter im Filter-Tab ([`gui_qt/views/culling_filter.py`](gui_qt/views/culling_filter.py)):**
    - Neuer Filterbereich *„📋 Workflow-Stand“*: Ermöglicht das sofortige Herausfiltern nach *Alle*, *⚪ Ungeprüft*, *📸 Qualität passt (SOOC)*, *🎨 Zu bearbeiten*, *⚙️ In Bearbeitung* oder *✔ Bearbeitet*.
  - **Konfiguration für NAS & Familienalbum ([`core/config.py`](core/config.py), [`gui_qt/widgets/general_settings.py`](gui_qt/widgets/general_settings.py)):**
    - Einstellungen für `family_album_dir` und `nas_archive_dir` inklusive Ordner-Durchsuchen-Dialogen in den allgemeinen Einstellungen.

## [0.16.0] - 2026-11-06

### Hinzugefügt
- **Neuer Tab „Filter“ im linken Navigations-Dock ([`gui_qt/views/culling_filter.py`](gui_qt/views/culling_filter.py), [`gui_qt/views/culling_left_dock.py`](gui_qt/views/culling_left_dock.py)):**
  - **Umschaltbare Tabs im linken Dock:** Das linke Dock vereint nun *„Verzeichnisse“* (Ordnerbaum) und den neuen *„Filter“*-Tab als saubere Reiter, die gemeinsam nach links in die 36px-Leiste eingeklappt werden können.
  - **Schnellzugriff in der 36px-Dockleiste:** Direktes Ausklappen und Aktivieren des Filters per `[ 🔍 ]` oder des Baums per `[ 📁 ]`.
  - **Filterung nach Dateityp (RAW / JPEG):** Einschränkung auf *Alle Formate*, *Nur RAW (inkl. RAW+JPG)*, *Nur JPEG*, *Nur RAW+JPEG Paare*, *Reine RAWs* oder *Reine JPEGs*.
  - **Filterung nach Bewertung & Status (Tags):**
    - Sterne: *Mindestens 1 bis 5 Sterne* oder *Ohne Bewertung (0★)*.
    - Status: *Nur Behalten [P]*, *Nur Abgelehnt [X]* oder *Nicht abgelehnt*.
    - Farblabels: *Rot, Gelb, Grün, Blau, Lila* oder *Ohne Farblabel*.
  - **Filterung nach Kamera (Camera):** Dynamisches Dropdown, das automatisch mit allen im aktuellen Ordner erkannten Kamera-Modellen und deren Bildanzahl gefüllt wird.
  - **Erweiterte EXIF-Filter & Volltextsuche (vorbereitet & aktiv):**
    - Textsuche nach Dateinamen, Kamera- oder Objektiv-Bezeichnung.
    - Dropdown für erkannte Objektive (Lenses).
    - ISO-Bereichsfilter (Niedrig ≤400, Mittel 400-1600, Hoch 1600-6400, Sehr hoch >6400).
  - **Echtzeit-Synchronisierung ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
    - Filmstreifen, Canvas-Bildanzeige und Vor/Zurück-Blättern passen sich sofort an die gefilterte Auswahl an.
    - Statusanzeige zeigt gefilterte Treffer: z. B. *„Filter: 42 von 120 Fotos (78 ausgeblendet)“*.
    - Schaltfläche *„✕ Zurücksetzen“* stellt jederzeit alle Bilder wieder her.

## [0.15.4] - 2026-11-06

### Behoben
- **Volle Unterstützung für Olympus / OM System ORI-Dateien ([`core/thumbnail.py`](core/thumbnail.py), [`gui_qt/models/culling_model.py`](gui_qt/models/culling_model.py), [`core/config.py`](core/config.py)):**
  - **Erkennung im Ordner-Scan & Culling-Modell:** `.ori`-Dateien (die hochauflösenden Einzelaufnahmen aus Olympus High-Res-Shot-Serien) werden nun verlässlich erkannt und als vollwertige RAW-Bilder in die Bildauswahl aufgenommen.
  - **Olympus TIFF-Container Header-Unterstützung:** Der native TIFF-Parser in `core/thumbnail.py` erkennt nun zusätzlich zu den Standard-TIFF-Signaturen auch Olympus-eigene Signaturen (`IIRO`, `IIRS`, `MMOR`).
  - **Embedded-Preview-Extraktion:** Eingebettete Vollauflösungs- und Vorschau-JPEGs werden aus `.ori`-Dateien blitzschnell direkt aus dem Container bzw. per LibRaw-Stream extrahiert.
  - **Parallele Erhaltung bei High-Res-Serien:** Bei Vorhandensein von zusammengesetzten High-Res-RAWs (`.ORF`) und Einzelframe-RAWs (`.ORI`) mit identischem Basisnamen (z. B. `P1010001.ORF` und `P1010001.ORI`) werden beide Dateien sauber nebeneinander als eigenständige Culling-Objekte dargestellt und können individuell bewertet, angezeigt und an Darktable übergeben werden.
  - **Metadaten & RAW-Klassifizierung ([`core/exif_reader.py`](core/exif_reader.py)):** `.ori`-Dateien werden korrekt als `RAW` eingestuft.
  - **Hilfe & Dokumentation ([`gui_qt/dialogs/help_dialog.py`](gui_qt/dialogs/help_dialog.py)):** `.ori` als unterstütztes Olympus-Kamera-RAW-Format gelistet.

### Behoben
- **Kein unbenutzbarer Leerraum beim Einklappen ([`gui_qt/views/culling_left_dock.py`](gui_qt/views/culling_left_dock.py)):**
  - Beim Einklappen des linken Docks auf 36px wird der gesamte gewonnene Platz direkt und millimetergenau an den Bildbetrachter (`Canvas`) übergeben.
  - Die mittlere Seitenleiste behält exakt ihre optimale Breite, wodurch kein toter/grauer Zwischenraum mehr entsteht und der Splitter nicht mehr manuell nachgezogen werden muss.

### Verbessert
- **Fokussierter Workflow & Bereinigung ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/views/culling_left_dock.py`](gui_qt/views/culling_left_dock.py)):**
  - **Quellordner-Auswahl entfernt:** Die redundante Quellordner-Auswahl wurde entfernt; die Ordnerauswahl erfolgt nun zentral und einheitlich über den Verzeichnisbaum.
  - **Aufgeräumte Bild-Kopfzeile:** Die Schaltfläche zum Ein-/Ausklappen in der Bildansicht wurde entfernt, um dem Foto maximale Höhe und Ruhe einzuräumen. Das Einklappen erfolgt direkt am Verzeichnisbaum (`[ ◀ ]`), an der 36px-Dockleiste (`[ ▶ ]` / `[ 📁 ]`) oder per Shortcut <kbd>V</kbd>.

## [0.15.2] - 2026-11-06

### Verbessert
- **Linkes Navigations-Dock mit Tabs & Einklappen nach Links ([`gui_qt/views/culling_left_dock.py`](gui_qt/views/culling_left_dock.py), [`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - **Zusammenklappen nach Links:** Der Verzeichnisbaum wird nicht mehr komplett ausgeblendet, sondern faltet sich nach links zu einer schmalen 36px-Dockleiste zusammen.
  - **Schnellzugriff in der eingeklappten Leiste:** Die 36px-Leiste bietet direkte Schaltflächen zum Ausklappen (`▶`), für den Verzeichnisbaum (`📁`) und das Quellverzeichnis (`📂`).
  - **Gemeinsame linke Ordner-Navigation:** Sowohl *„Verzeichnisse“* (Baumstruktur mit Zählern) als auch *„Quellordner“* (Direktwahl mit Scan-Fortschritt) sind als Umschalt-Tabs im linken Dock vereint und klappen gemeinsam nach links zusammen.
  - **Aufgeräumte Bewertungs-Seitenleiste:** Die mittlere Seitenleiste bleibt exklusiv auf den Culling- und Bewertungs-Workflow (Foto-Details, Bewertung, Darktable/Topaz, Statistik, Shortcuts) fokussiert.

## [0.15.1] - 2026-11-06

### Behoben
- **Plattformunabhängige Vektor-Icons für Verzeichnisbaum- und Aktions-Buttons ([`gui_qt/styles/icons.py`](gui_qt/styles/icons.py), [`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - Ersetzung nativer Unicode-Emojis durch saubere, hochauflösende Vektor-Icons (`QPainter`):
    - *Aktualisieren*: Runder Reload-Pfeil (`⟳`)
    - *Unterordner ausklappen*: Crisp Plus (`+`)
    - *Alle Ordner einklappen*: Crisp Minus (`−`)
    - *Verzeichnisbaum-Leiste einklappen*: Einklapp-Pfeil (`◀`)
    - *Ordner in der Baumansicht*: Fluent-Folder-Icons für alle Zeilen und Ordnerwahl-Buttons
  - Beseitigt fehlende Glyphen, gelbe Rechtecke und Emoji-Fallback-Artefakte auf Windows und Linux vollständig.

### Verbessert
- **Einklappbare Bereiche für Verzeichnisse und Quellordner ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py), [`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - **Einklappbares Quellverzeichnis:** Die Sektion *„Ordner & Quellverzeichnis“* in der Seitenleiste wurde in eine interaktive `CollapsibleBox` umgewandelt und kann per Klick auf den Header oder `[ Einklappen ▲ ]` / `[ Ausklappen ▼ ]` platzsparend zusammengefaltet werden.
  - **Verzeichnisbaum einklappen:** Der gesamte Verzeichnisbaum kann nun direkt über den Header-Button `[ ◀ ]` im Verzeichnisbaum selbst oder über die obere Symbolleiste bzw. Shortcut <kbd>V</kbd> vollständig ein- und ausgeklappt werden.

## [0.15.0] - 2026-11-06

### Hinzugefügt
- **Interaktiver Verzeichnisbaum mit Bild-, RAW- und JPEG-Zählern ([`gui_qt/views/culling_tree.py`](gui_qt/views/culling_tree.py)):**
  - **Hierarchischer Verzeichnisbaum:** Ermöglicht die flexible Navigation durch Ordner und Unterverzeichnisse direkt im Tab *„Sichten & Sortieren“*.
  - **Präzise Bildzählung je Ordner:** Zeigt für jedes Verzeichnis übersichtlich getrennte Spalten für:
    - `Bilder`: Gesamtzahl aller erkannten Bilddateien
    - `RAW`: Anzahl der RAW-Sensordaten (z. B. CR2/CR3, NEF, ARW, DNG, RAF, RW2 etc.) in auffälligem Magenta/Pink
    - `JPEG`: Anzahl der JPEG-Dateien in Sky-Blue
  - **Frei wählbarer Einstiegspunkt (Root-Verzeichnis):**
    - Der Einstiegspunkt kann über die Schaltfläche *„Einstiegspunkt...“* oder das Kontextmenü jederzeit beliebig gewechselt werden (z. B. spezifische Jahres- oder Projektordner).
    - Die Auswahl bleibt sitzungsübergreifend in der Konfiguration (`culling_root_folder`) gespeichert.
  - **High-Performance Lazy Loading:** Unterordner werden bedarfsgerecht und ohne Ladezeiten expandiert – selbst bei riesigen Archiven oder Netzlaufwerken bleibt FotoDown sofort reaktionsfähig.
  - **Kontextmenü & Schnellzugriff:**
    - Per Rechtsklick: Ordner als neuen Einstiegspunkt setzen, im System-Dateimanager öffnen oder Zähler aktualisieren.
    - Schaltflächen zum Aktualisieren (`🔄`) sowie Ein- und Ausklappen (`➕` / `➖`).
  - **Nahtlose 3-Spalten-Workstation für Ultrawide-Monitore:**
    - Pane 1: Verzeichnisbaum (Breite anpassbar, ein-/ausblendbar mit <kbd>V</kbd>)
    - Pane 2: Steuerung, Bewertungen, Darktable/Topaz Export und Statistiken
    - Pane 3: Bildbetrachter mit maximaler vertikaler Monitorhöhe und einklappbarem Filmstreifen (<kbd>T</kbd>)

## [0.14.2] - 2026-11-05

### Verbessert
- **Ultrawide-optimiertes Layout für maximale Bildhöhe im Sichten-Tab ([`gui_qt/views/culling_tab.py`](gui_qt/views/culling_tab.py)):**
  - **Neues 2-Spalten-Layout mit horizontalem Splitter:**
    - Alle Bedienelemente (Ordnerwahl, Fortschrittsbalken, Navigation, Sternebewertung, Behalten/Ablehnen, externe Editoren Darktable & Topaz Photo sowie Statistiken) wurden in eine übersichtliche, vertikale linke Seitenleiste verlegt.
  - **Maximale Bildhöhe für das Hauptfoto:**
    - Über und unter dem Bild befinden sich keine sperrigen horizontalen Leisten mehr, sodass die volle Bildschirmhöhe auf 21:9 / 32:9 Monitoren dem Foto zur Verfügung steht.
  - **Einklappbarer Filmstreifen:**
    - Der untere Filmstreifen kann per Knopfdruck oder Shortcut <kbd>T</kbd> vollständig ein- und ausgeblendet werden, um dem angezeigten Foto 100% der vertikalen Monitorhöhe einzuräumen.
  - **Tastatur-Schnellzugriff:** Integrierte Übersicht der Shortcuts direkt in der linken Seitenleiste.

## [0.14.1] - 2026-11-05

### Behoben
- **Asynchroner Ladefortschritt beim Öffnen von Ordnern im Sichten-Tab (`gui_qt/views/culling_tab.py`, `gui_qt/workers/culling_worker.py`, `gui_qt/models/culling_model.py`):**
  - **Kein Einfrieren der Benutzeroberfläche:** Das Einlesen von Bilddateien, EXIF-Metadaten und XMP-Sidecars erfolgt nun in einem dedizierten Hintergrund-Thread (`CullingScanWorker`).
  - **Live-Fortschrittsbalken:** Während des Einlesens wird ein Fortschrittsbalken mit Prozentangabe, aktuellem Dateinamen und Zähler (`Lese Fotos ein: X von Y (Z%)...`) angezeigt.
  - **Abbruchmöglichkeit:** Über die Schaltfläche *„✕ Abbrechen“* kann das Einlesen sehr großer Ordner jederzeit ohne UI-Hänger gestoppt werden.
  - Schaltflächen für Ordnerauswahl und Neuladen werden während des Scan-Vorgangs geschützt deaktiviert.

## [0.14.0] - 2026-11-05

### Hinzugefügt
- **2. Hauptfunktion: Tab „Sichten & Sortieren“ (Culling, Bewertung & Editor-Export):**
  - **Zwei-Phasen-Workflow:** Hauptumschaltung im Header zwischen *„📥 1. Importieren“* und *„👁️ 2. Sichten & Sortieren“*.
  - **Direkter Absprung nach Import:** Nach erfolgreichem Kopiervorgang bietet FotoDown die Schaltfläche *„👁️ Jetzt sichten & bewerten ➔“*, die den Zielordner direkt im 2. Tab öffnet.
  - **High-Performance Culling-Workspace ([`CullingTabView`](gui_qt/views/culling_tab.py)):**
    - Schneller Bildbetrachter mit stufenloser Anpassung und 100%-Schärfelupe (<kbd>F</kbd> / Doppelklick).
    - Horizontaler Filmstreifen mit synchronisierter Kartenvorschau, Bewertungssternen und Statusanzeige.
    - Schnelle Tastaturnavigation (<kbd>◀</kbd> / <kbd>▶</kbd>, <kbd>A</kbd> / <kbd>D</kbd>).
  - **Logische RAW + JPEG Koppelung:**
    - RAW und JPEG werden als eine konsolidierte Einheit geführt.
    - Mit Taste <kbd>J</kbd> / <kbd>R</kbd> kann unterbrechungsfrei zwischen der Kamera-JPEG-Farbwiedergabe und der RAW-Sensor-Vorschau umgeschaltet werden.
  - **Standard-XMP-Synchronisation ([`core/xmp_sync.py`](core/xmp_sync.py)):**
    - Bewertungen (1–5 Sterne mit Tasten <kbd>1</kbd>–<kbd>5</kbd>, <kbd>0</kbd> zum Zurücksetzen) sowie Pick (<kbd>P</kbd>) und Reject (<kbd>X</kbd>) werden sofort und synchron in standardkonforme `.xmp`-Sidecar-Dateien geschrieben.
    - Voll kompatibel mit Darktable, Lightroom und DigiKam.
  - **Direkte Übergabe an externe Programme ([`core/external_tools.py`](core/external_tools.py)):**
    - 🎨 **Darktable-Übergabe (<kbd>Strg+D</kbd>):** Übergibt selektierte oder 3★+ bewertete **ausschließlich als RAW-Dateien** an Darktable.
    - ✨ **Topaz Photo Übergabe (<kbd>Strg+T</kbd>):** Übergibt selektierte oder 3★+ bewertete **ausschließlich als JPEG-Dateien** an Topaz Photo zur KI-Optimierung.
    - Automatische Programmerkennung unter Windows (`C:\Program Files\...`) und Linux.
  - **Konfigurierbares Reject-Handling:**
    - In den Einstellungen wählbar: *In Unterordner verschieben (`_Abgelehnt/`)*, *In den Papierkorb / Löschen* oder *Nur in Metadaten als abgelehnt markieren*.
    - Button *„🗑️ Aussortierte verarbeiten“* mit Sicherheitsabfrage.

## [0.13.0] - 2026-11-03

### Hinzugefügt
- **Umfassende Vorschau- und Thumbnail-Unterstützung für RAW-Formate (`core/thumbnail.py`, `requirements.txt`):**
  - **Unterstützung aller gängigen Kamera-RAW-Formate:** Canon (`.cr2`, `.cr3`, `.crw`), Nikon (`.nef`, `.nrw`), Sony (`.arw`, `.srf`, `.sr2`), Fujifilm (`.raf`), Olympus/OM System (`.orf`, `.ori`), Panasonic/Lumix (`.rw2`, `.raw`), Pentax (`.pef`), Adobe DNG (`.dng`), Samsung (`.srw`), Hasselblad (`.3fr`, `.fff`), Phase One (`.iiq`), Kodak (`.kdc`, `.dcr`), Minolta (`.mrw`), Epson (`.erf`) und Sigma (`.x3f`).
  - **Multi-Level Extraktions-Pipeline:**
    1. **Begleit-JPEG-Priorität:** Automatische Verwendung vorhandener RAW+JPG Begleitdateien für sofortige Latenzfreiheit.
    2. **Direkte Container-Parser:** Blitzschnelle Extraktion eingebetteter JPEG-Vorschauen aus Fujifilm RAF-Headern, Canon CR3 (ISOBMFF `PRVW`/`thmb` Boxen) sowie TIFF-basierten Formaten (CR2, NEF, ARW, DNG, ORF, PEF) über SubIFD-, ExifIFD- und StripOffsets-Tags.
    3. **LibRaw / rawpy Integration:** Volle Unterstützung von `rawpy` zur direkten Extraktion von embedded Previews oder schnellem Sensor-Demosaicing (`half_size`), falls kein JPEG eingebettet ist.
    4. **Robuster Pure-Python-Stream-Scan:** Fehlertoleranter SOI-Marker-Scan (`\xff\xd8\xff`) mit dynamischer Pillow-Auflösungsanalyse als Ausfallsicherung.
  - **Durchgängige Anzeige im gesamten Programm:**
    - Miniatur-Kacheln in der Galerieansicht ([`MediaGalleryView`](file:///192.168.1.20/Daten\Developement\FotoDown\gui_qt\views\gallery_view.py)).
    - Hochauflösende Einzelbild-Betrachtung ([`MediaSingleView`](file:///192.168.1.20/Daten\Developement\FotoDown\gui_qt\views\single_view.py)).
    - Vollbild-Vorschau ([`QuickPreviewDialog`](file:///192.168.1.20/Daten\Developement\FotoDown\gui_qt\dialogs\quick_preview_dialog.py)).
    - EXIF-Inspektor-Vorschau und Histogramm-Berechnung ([`ExifInspectorWidget`](file:///192.168.1.20/Daten\Developement\FotoDown\gui_qt\widgets\exif_inspector.py)).
  - **Abhängigkeiten aktualisiert:** `rawpy>=0.20.0` und `numpy>=1.26.0` in `requirements.txt` ergänzt.

## [0.12.2] - 2026-11-03

### Behoben
- **Vorschau beim Auswerfen leeren (`gui_qt/widgets/header_banner.py`, `gui_qt/main_window.py`):**
  - Beim Klick auf „⏏ Auswerfen“ oder beim automatischen Entfernen eines Laufwerks werden alle geladenen Bilder und Vorschaudaten vollständig aus dem Arbeitsbereich entfernt:
    - Tabellenmodell, Galerieansicht und Einzelbildansicht werden geleert.
    - Die Zielordner-Vorschau (Ziel-Baum) wird zurückgesetzt.
    - Miniaturbild-Cache wird bereinigt und freigegeben.
    - EXIF-Inspektor wird geschlossen/zurückgesetzt.
    - Status- und Statistikleiste sowie Quellpfad werden auf den Ausgangszustand („Bereit“) zurückgesetzt.
    - Der Arbeitsbereich wechselt zurück auf die Willkommens- und Leeransicht („Noch keine Fotos eingelesen“).

## [0.12.1] - 2026-11-03

### Hinzugefügt
- **Umfassende Installationsanleitung & 1-Klick-Installer (`INSTALL.md`, `install_windows.bat`, `install_linux.sh`):**
  - **Detaillierte Installationsanleitung ([`INSTALL.md`](INSTALL.md)):** Strukturierte Anleitungen für Windows 10/11 und alle Linux-Systeme.
  - **Spezifischer Support für alle Arch Linux Varianten:** Arch Linux, Manjaro, EndeavourOS, Garuda Linux, ArcoLinux, CachyOS etc. inklusive Pacman-Direktinstallation (`python-pyside6`, `python-pillow`), PEP-668-konformer venv-Einrichtung, Wayland/X11-Support (`qt6-wayland`) und Speicherkarten-Berechtigungen (`udisks2`).
  - **1-Klick-Assistent für Linux (`install_linux.sh`):** Automatische Erkennung der Distribution, Einrichtung von `.venv`, Installation der Abhängigkeiten und Erstellung eines `.desktop`-Starters mit Icon für das Anwendungsmenü (KDE Plasma, GNOME, etc.).
  - **1-Klick-Assistent für Windows (`install_windows.bat`):** Automatische `.venv`-Erstellung, Paketinstallation und Anlegen einer Desktop-Verknüpfung mit Kamera-Icon.
  - **Starter-Optimierung (`FotoDown.bat`, `fotodown.sh`):** Erkennt und verwendet automatisch `.venv`, sofern vorhanden.

## [0.12.0] - 2026-11-03

### Hinzugefügt
- **Bereichsauswahl mit STRG / Shift (`gui_qt/views/gallery_view.py`, `gui_qt/views/table_view.py`, `gui_qt/main_window.py`):**
  - **Bereichsauswahl (Range Selection) in Galerie- und Tabellenansicht:** Durch Klicken auf ein erstes Bild und anschließendes Klicken auf ein zweites Bild bei gedrückter <kbd>STRG</kbd>- (oder <kbd>Umschalt</kbd>-)Taste werden automatisch alle dazwischen liegenden Fotos für den Import ausgewählt (`selected = True`).
  - Visuelle Aktualisierung aller Kärtchen (Checkboxen & Umrandung) und synchrone Neuberechnung der Statistik-Leiste (Anzahl und Gesamtgröße).
  - Synchronisation mit Qts `QItemSelectionModel`, sodass auch die Fokus- und Tastaturmarkierung für den gesamten Bereich gesetzt wird.
  - Shortcut <kbd>S</kbd> in der Tabellenansicht zum Umschalten aller markierten Zeilen ergänzt.

## [0.11.1] - 2026-11-03

### Behoben
- **Absturz beim Umschalten auf die Galerie-Ansicht behoben (`gui_qt/workers/thumb_worker.py`, `gui_qt/main_window.py`, `gui_qt/views/delegates.py`):**
  - **Thread-sichere Signal-Architektur:** Beseitigung eines kritischen Race-Conditions-/Dangling-Pointer-Absturzes in Qt/PySide6. Bisher wurde in `ThumbnailTask` (einem `QRunnable` mit `autoDelete=True`) ein ephemeres `ThumbnailSignals`-Objekt ohne festen Qt-Parent erstellt, das nach Beendigung des Worker-Threads in C++ zerstört wurde, während die Signal-Events noch in der Qt-Ereignisschleife des Hauptthreads verarbeitet wurden.
  - `MainWindow` verwaltet nun eine langlebige, threadsichere Instanz `thumb_signals`, die direkt und ohne fehleranfällige Lambda-Closures mit dem Galerie-Delegate kommuniziert.
  - **Sichere QImage-Konvertierung:** Thumbnails werden nun über einen In-Memory-PNG-Bytestrom via `QImage.loadFromData()` instanziiert, wodurch Puffer-Lebenszeitprobleme und Zugriffsverletzungen (Access Violation) bei asynchronen Threadpool-Ladevorgängen vollständig ausgeschlossen werden.
  - **Robuste Delegaten-Absicherung:** `GalleryDelegate.paint()` validiert `index.isValid()` und stellt sicher, dass nur skalierte Pixmaps mit positiven Dimensionen gezeichnet werden.

## [0.11.0] - 2026-11-03

### Hinzugefügt
- **Integrierte Einzelansicht (`gui_qt/views/single_view.py`, `gui_qt/widgets/filter_bar.py`, `gui_qt/main_window.py`):**
  - Neuer Ansichtsmodus *„🔍 Einzelansicht“* im Hauptarbeitsbereich.
  - Ermöglicht das Betrachten von Fotos in voller Pracht direkt im Hauptfenster mit bequemer Tastaturnavigation (`◀` / `▶` bzw. `A` / `D`), Bildzähler und Titelleiste.
  - Umschaltung per Klick oder Tastenkombination (`F` / Doppelklick) zwischen *„Einpassen“* (skaliert an Anzeigefläche) und *„100% Originalgröße“* (1:1 Pixeldarstellung mit Scrollbereich zur Schärfe- und Fokusbeurteilung).
  - Direkte Auswahl-Checkbox (`Für Import ausgewählt [S]`) sowie Schnell-Absprung in den Vollbild-Vorschaudialog (`Leertaste`).
  - Detaillierte Metadaten-Leiste am unteren Rand (Kameramodell, Objektiv, Belichtungswerte, Megapixel, Dateigröße, Datum).

### Behoben
- **Kristallklare Bilddarstellung & Schärfe-Optimierung (`core/thumbnail.py`, `gui_qt/workers/thumb_worker.py`, `gui_qt/views/delegates.py`, `gui_qt/dialogs/quick_preview_dialog.py`):**
  - **Erhöhte Thumbnail-Auflösung:** Vorschaubilder in der Galerie werden nun nativ in 480x480 Pixeln mit `Image.Resampling.LANCZOS` generiert (zuvor 160x160), wodurch Fotos auch bei hoher Zoomstufe und auf Windows-HiDPI-Displays gestochen scharf dargestellt werden.
  - **Glattes Rendering aktiviert:** `QPainter.RenderHint.SmoothPixmapTransform` in `GalleryDelegate` hinzugefügt, um Unschärfen und Moiré-Artefakte beim Zeichnen von Miniaturbildern zu verhindern.
  - **Verbesserte RAW-Vorschauextraktion:**
    - Behebung eines Problems, bei dem für RAW-Dateien fälschlicherweise das winzige 160x120-IFD0-Thumbnail verwendet wurde.
    - `extract_raw_embedded_jpeg` prüft nun vorrangig vorhandene Begleit-JPGs und durchsucht den RAW-Datenstrom (bis 24 MB) nach den hochauflösenden eingebetteten JPEG-Vorschaubildern der Kamera.
    - Sortierung aller gefundenen Bildkandidaten nach maximaler Auflösung (`width * height`), sodass stets die schärfste Vorschau gewählt wird.
  - **Zentrale Vorschau-Ladefunktion (`load_preview_image`):** Lädt Vorschauen für Einzelansicht und Quick Look in bis zu 2560px Auflösung mit automatischer EXIF-Ausrichtung.

## [0.10.5] - 2026-11-03

### Behoben
- **Profil-Persistenz & Muster-Synchronisation (`core/config.py`, `gui_qt/main_window.py`, `gui_qt/widgets/pattern_editor.py`, `gui_qt/widgets/path_selector.py`, `gui_qt/widgets/general_settings.py`):**
  - **Namens- und Ordnerstruktur-Muster werden zuverlässig im Profil gespeichert:**
    - Beim Wechseln oder Speichern von Profilen wurden zuvor Signale während des Ladens (`load_config`) ausgelöst, die noch unvollständige Formulareingaben zurück in die Konfiguration spiegelten und Muster mit leeren Strings überschreiben konnten.
    - `load_config` blockiert nun in allen Einstellungs-Widgets (`PatternEditorWidget`, `PathSelectorWidget`, `GeneralSettingsWidget`) vorübergehend die Signale, und `MainWindow` verhindert mit einem Lade-Guard (`_is_loading_config`) vorzeitiges oder zirkuläres Zurückschreiben in die Konfiguration während Profilwechseln.
    - Muster-Felder fallen bei leeren Eingaben automatisch auf gültige Standardmuster zurück (`{YYYY}/{YYYY}-{MM}-{DD}` bzw. `{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}`), sodass niemals ungültige oder leere Muster in Profilen gespeichert werden.
    - **Automatische Profil-Migration:** Bestehende Konfigurationen aus älteren Versionen werden beim Laden automatisch mit allen Profil-Schlüsseln (inklusive IPTC, Dual-Backup und Muster) abgeglichen und nachgepflegt.
    - Änderungen an Mustern oder allgemeinen Einstellungen im UI werden sofort im aktuell aktiven Profil hinterlegt und gesichert.

## [0.10.4] - 2026-11-03

### Behoben
- **Sidebar-Layout & Proportionen (`gui_qt/main_window.py`, `gui_qt/widgets/path_selector.py`, `gui_qt/widgets/pattern_editor.py`, `gui_qt/widgets/collapsible_box.py`):**
  - **Architektur der Seitenleiste optimiert:** Aufteilung in einen feststehenden Kopfbereich (Profil-Auswahl), einen flexiblen scrollbaren Mittelteil für die einklappbaren Konfigurationsblöcke (`QScrollArea` mit vertikalem Scrollbalken bei Bedarf) und eine fest am unteren Rand verankerte Aktionsleiste (`[Scannen]`, `[Importieren]`, Speicherwarnungen und Fortschrittsbalken). Dadurch sind die Hauptaktionen stets direkt erreichbar und werden nie verdeckt oder nach unten weggescrollt.
  - **Größen- und Abschneideprobleme behoben:**
    - `PatternEditorWidget`: Platzhalter-Chips wurden von einer 10-Elemente-Horizontalzeile (die über 640px Mindestbreite erzwang) in ein kompaktes 2-Zeilen-Raster (2x5) umorganisiert.
    - `PathSelectorWidget`: Text der 2. Backup-Checkbox gekürzt auf `🛡️ Gleichzeitig 2. Backup erstellen (NAS/Festplatte)` mit erklärendem Tooltip.
    - `CollapsibleBox`: Feste Layout-Größenbeschränkung (`SetMinimumSize`) verhindert, dass eingeklappte oder ausgeklappte Boxen auf wenige Pixel zusammengestaucht werden.
  - Die Mindestbreite und Initialaufteilung des Hauptsplitters (`420px / 860px`) sorgt dafür, dass alle Schaltflächen (`Durchsuchen`, `Einklappen`, `Ausklappen`, Profil-Buttons) und Labels vollständig ohne Abschneiden lesbar sind.

## [0.10.3] - 2026-11-03

### Behoben
- **Galerie-Ansicht Rendering (`gui_qt/views/delegates.py`):**
  - Behebung eines `AttributeError` in `GalleryDelegate.paint()`, bei dem `option.State_MouseOver` fälschlicherweise auf `QStyleOptionViewItem` statt auf `QStyle.StateFlag.State_MouseOver` referenziert wurde.
  - Dieser Laufzeitfehler führte dazu, dass Qt den Zeichenvorgang für jedes Galeriekärtchen abbrach und die Galerieansicht beim Umschalten vollständig leer blieb.
  - Unit-Test zur Absicherung des Rendering-Vorgangs der `MediaGalleryView` hinzugefügt.

## [0.10.2] - 2026-11-03

### Behoben
- **Layout-Aufteilung im rechten Arbeitsbereich (`gui_qt/main_window.py`, `gui_qt/widgets/filter_bar.py`):**
  - Korrektur der vertikalen Größenverteilung im Medien-Arbeitsbereich: Die Filterleiste war unbeabsichtigt vertikal auf ~380px expandiert und hatte den gesamten Ansichtsbereich mit Tabelle/Galerie/Baum bzw. den Leeren Zustand nach unten gedrückt.
  - `FilterBarWidget` erhält jetzt eine feste vertikale Größenpolitik (`QSizePolicy.Fixed`), und `workspace_splitter` erhält den vollen vertikalen Dehnungsfaktor (`stretch=1`).
  - Die Filterleiste sitzt nun wieder schlank und bündig oben (Höhe ~36px), während die Inhaltsansichten den gesamten verbleibenden vertikalen Raum einnehmen.

## [0.10.1] - 2026-11-03

### Behoben
- **Profil-Aktionsbuttons in der Profilleiste (`gui_qt/widgets/profile_bar.py`, `gui_qt/styles/dark_fluent.qss`):**
  - Behebung eines Darstellungsfehlers, durch den das Standard-Button-Padding (`padding: 6px 14px`) den Inhalt von kompakten 28x28-Buttons komplett abgeschnitten hatte und alle drei Buttons als leere graue Quadrate erschienen.
  - Spezifische Objekt-IDs (`profileBtnSave`, `profileBtnNew`, `profileBtnDelete`) mit `padding: 0px` und zentrierter Glyph-Darstellung (`Segoe UI Emoji` / `Segoe UI Symbol`).
  - Semantische Farbkodierung zur klaren visuellen Unterscheidung:
    - *Speichern* (`💾`): Blauer Akzentrahmen (`#0369a1`) und Icon-Farbe (`#38bdf8`) mit blauem Hover-Effekt.
    - *Neu anlegen* (`➕`): Grüner Akzentrahmen (`#047857`) und Icon-Farbe (`#34d399`) mit smaragdgrünem Hover-Effekt.
    - *Löschen* (`🗑️`): Roter Akzentrahmen (`#991b1b`) und Icon-Farbe (`#f87171`) mit rotem Danger-Hover-Effekt.
  - Eindeutige, informative Tooltips für jede Aktion.

## [0.10.0] - 2026-11-03

### Hinzugefügt
- **Interaktive Zielstruktur-Baumvorschau (`gui_qt/views/tree_view.py`):**
  - Neuer Ansichtsmodus *„📁 Ordnerstruktur“* in der Ansichts-Umschaltung der Filterleiste.
  - Hierarchische Baumdarstellung (`QTreeView`) aller geplanten Zielverzeichnisse und Dateien vor dem Kopiervorgang.
  - Zeigt exakte Ordnerhierarchien, Dateigrößen-Badges, RAW+JPG-Paar-Zuordnung und Status pro Datei an.
  - Doppelklick öffnet direkt die Großbild-Vorschau; Auswahl synchronisiert mit dem EXIF-Inspektor.
  - Komfort-Schaltflächen für *„➕ Alle ausklappen“* und *„➖ Alle einklappen“*.
- **IPTC- & Copyright-Metadaten-Injektion beim Import (`core/metadata_writer.py`, `core/config.py`, `core/importer.py`):**
  - Automatische Injektion von Urheberdaten (Fotografenname, Copyright-Hinweis mit `{year}` / `{creator}` Platzhaltern und Schlagwörtern / Keywords) während des Kopiervorgangs.
  - Erstellung und Anreicherung von Adobe-kompatiblen standardisierten XMP/Dublin-Core-Sidecars (`.xmp`) für Bilder und RAW-Dateien.
  - Konfigurierbar in den Allgemeinen Einstellungen sowie in Import-Profilen sicherbar.
- **Integrierter EXIF-Detail-Inspector als ausklappbares Seiten-Panel (`gui_qt/widgets/exif_inspector.py`):**
  - Schnelles Ein- und Ausblenden über die Filterleiste (`ℹ️ EXIF`).
  - Umfassende Anzeige aller technischen Aufnahmedaten (Kamera, Objektiv, Belichtungs-Chip `ƒ/2.8 | 1/500s | ISO 200 | 50mm`, Auflösung in Megapixeln, Dateigröße).
  - Integriertes, antialiastes RGB- und Luminanz-Histogramm (`HistogramWidget`).
  - GPS-Koordinaten-Anzeige mit Direkt-Button *„In OpenStreetMap öffnen ↗“*.
- **Automatische Foto-Rotation nach EXIF-Orientierung:**
  - Konsequente Anwendung von `ImageOps.exif_transpose` in allen Vorschaukomponenten (Gallery, Quick Preview, EXIF Inspector), sodass Hochformat- und gedrehte Fotos stets aufrecht dargestellt werden.
- **Vorbereitung für v1.0.0:**
  - Alle Kernfunktionen vollständig implementiert und mit 44 Unit-Tests abgesichert.

## [0.9.0] - 2026-11-03

### Hinzugefügt
- **Import-Profile & Voreinstellungen (Presets) (`core/config.py`, `gui_qt/widgets/profile_bar.py`):**
  - Schnelles Umschalten zwischen vorkonfigurierten Profilen: *„Standard“*, *„Urlaub & Reise“*, *„Studio & Shooting“* und *„Drohne & Actioncam“*.
  - Jedes Profil sichert Zielordner, Video-Ablage, 2. Backup, Dateinamen-Muster, Ordnerstruktur, RAW+JPG-Organisation und Sicherheitsoptionen.
  - Profile können direkt über die Profil-Leiste gespeichert (`💾`), neu angelegt (`➕`) oder gelöscht (`🗑️`) werden.
- **Eigene einklappbare Sektion für Allgemeine Einstellungen (`gui_qt/widgets/general_settings.py`):**
  - Trennung der Konfiguration in logische Blöcke:
    - *1. Quell- und Zielordner* (Pfade & Speicherplatzbalken)
    - *2. Namens- und Ordnerstruktur-Muster* (Dateinamen, Ordner und Tags)
    - *3. Allgemeine Einstellungen & Optionen* (JPG/RAW-Organisation, RAW+JPG Kopplung, XMP-Sidecars, Hotplug-Erkennung, Duplikatsprüfung, Bit-Integritätsprüfung).
- **Interaktive, intuitive Ein-/Ausklapp-Balken (`gui_qt/widgets/collapsible_box.py`):**
  - Der gesamte Header-Balken ist jetzt klickbar und signalisiert die Interaktivität mit Hand-Cursor (`PointingHandCursor`) und deutlicher Hover-Hervorhebung.
  - Rechter Hand zeigt ein deutlicher Aktions-Button (`[ Einklappen ▲ ]` bzw. `[ Ausklappen ▼ ]`) unmissverständlich an, wo geklickt werden kann.
  - Visuelle Chevron-Icons (`▼` / `▶`) auf der linken Seite.

## [0.8.0] - 2026-11-03

### Hinzugefügt
- **Automatische Speicherkartenerkennung bei Einstecken (Hotplug / Auto-Detect):**
  - **Hintergrund-Laufwerksüberwachung (`DriveMonitor` & `DriveWatcherThread`):** Asynchrone Erkennung neu verbundener oder entfernter Wechsellaufwerke und SD-Karten in Echtzeit.
  - **Hotplug-Benachrichtigungsbanner (`CardNotificationBanner`):** Sobald eine SD-Karte (insb. mit `DCIM`-Kamera-Ordner) eingesteckt wird, erscheint am oberen Bildschirmrand ein dezentes, elegantes Banner mit Laufwerksbuchstaben, Label, freiem Speicherplatz und einem **„🔍 Jetzt Fotos scannen“**-Button.
  - **1-Klick-Scan:** Ein Klick auf das Banner übernimmt direkt den DCIM-Quellpfad und startet den Scanvorgang sofort.
  - **Automatisches Aushängen / Entfernen:** Beim Abziehen der Karte wird das Banner automatisch geschlossen und die Laufwerksauswahl aktualisiert.
  - **Konfigurierbar:** Option in den Einstellungen (`auto_detect_drives`) zum Aktivieren/Deaktivieren der automatischen Erkennung.

## [0.7.0] - 2026-11-03

### Hinzugefügt
- **RAW + JPG Kopplung als logische Einheit (`core/importer.py`, `core/config.py`):**
  - Beim Scannen werden RAW- und JPG-Dateien desselben Motivs (gleicher Stammname im selben Quellordner) automatisch zu einem einzelnen Eintrag (`is_pair=True`) gekoppelt.
  - Einheitliche Umbenennung: Beide Dateien erhalten exakt denselben neuen Namen und dieselbe fortlaufende Nummer.
  - Selektiert der Benutzer das Foto, werden stets RAW und JPG gemeinsam ausgewählt und importiert.
  - Vollständige Unterstützung für getrennte Unter- oder Hauptordner (`.../RAW` und `.../JPG`) bei simultaner Kopplung.
  - Beide Dateien werden in der Historie-Datenbank mit ihren SHA-256 Hashes erfasst, damit künftige Scans Duplikate lückenlos erkennen.
- **XMP-Sidecar-Synchronisation (`.xmp`):**
  - Vorhandene `.xmp`-Metadatendateien (z.B. von Lightroom, Capture One oder Kamera-Bewertungen) werden automatisch erkannt und mitkopiert.
  - Die `.xmp`-Dateien werden exakt synchron zum neuen Zieldateinamen umbenannt.
  - Beim optionalen Löschen von der Quelle nach erfolgreichem Import werden Sidecars erst dann gelöscht, wenn alle Kopiervorgänge und Prüfsummenvalidierungen erfolgreich waren.
- **UI-Integration für RAW+JPG & XMP:**
  - Neue Konfigurations-Checkboxen in der Seitenleiste: *„RAW & JPG als logische Einheit koppeln“* und *„XMP-Sidecars (.xmp) synchron mitführen“*.
  - Galerieansicht zeigt einen visuellen Badge (`RAW+JPG`, `RAW+JPG+XMP`, `+XMP`) auf den Fotokarten.
  - Tabellenansicht zeigt im Typfeld `RAW+JPG` sowie die kombinierte Gesamtdateigröße.
  - Schnellvorschau (`QuickPreviewDialog`) nutzt bei RAW+JPG-Paaren automatisch das Begleit-JPG für sofortigen, gestochen scharfen Bildaufbau.
  - Speicherkapazitätsprüfung berechnet das Gesamtdatenvolumen inklusive Begleitdateien und Sidecars.

## [0.6.0] - 2026-11-03

### Hinzugefügt
- **Duales Backup / 2. Sicherungsziel (`core/importer.py`, `gui_qt/widgets/path_selector.py`):**
  - Option zum automatischen simultanen Kopieren auf ein zweites Ziel (z.B. NAS oder externe Backup-Festplatte) direkt während des Imports.
  - Eigener Füllstandsbalken mit Speicherplatzprüfung für das 2. Backup-Ziel.
  - Quelllöschung (sofern aktiviert) erfolgt erst nach erfolgreichem Schreiben und Verifizieren *beider* Ziele.
- **Bit-genaue Integritätsprüfung (SHA-256 Checksum Verification):**
  - Automatischer Vergleich der SHA-256 Prüfsummen nach dem Schreibvorgang zwischen Quell- und Zieldatei (sowie Backup-Datei).
  - Erkennt Übertragungsfehler oder Dateibeschädigungen sofort und schützt vor Datenverlust.

## [0.5.1] - 2026-11-03

### Behoben & Verbessert
- **Sidebar-Layout (Vertikales Form-Design):**
  - Umstellung der Quell- und Zielpfade auf ein vertikales Layout (Label oben, breites Eingabefeld mit Durchsuchen-Button darunter).
  - Beseitigung aller horizontalen Stauchungen und Textüberhänge.
  - JPG/RAW-Organisation als kompaktes, vollwertiges Dropdown-Menü (`QComboBox`) umgesetzt.
- **Speicherplatzbalken (`StorageBarWidget`):**
  - Entzerren von Titel und Speicherdetails (Prozentanzeige rechts oben, Füllstandsbalken und vollständige GB-Details vollflächig darunter).
- **Responsive Filterleiste (`FilterBarWidget`):**
  - Mindestbreite für das Suchfeld garantiert; kein Zusammenschrumpfen mehr auf `...`.
  - Kompakte Beschriftungen und Schaltflächen.
- **Empty-State-Platzhalter (`EmptyStateWidget`):**
  - Anstelle eines leeren schwarzen Tabellenfeldes wird vor dem ersten Scan ein elegantes Platzhalter-Widget mit Hilfetext und Direkt-Scan-Button angezeigt.

## [0.5.0] - 2026-11-03

### Hinzugefügt
- **Quick-Look / Vollbild-Schnellvorschau (`gui_qt/dialogs/quick_preview_dialog.py`):**
  - Schnelle Tastatur- und Mausvorschau für Fotos und RAWs per **Leertaste (Space)** oder **Doppelklick**.
  - Flüssiges Blättern mit den Pfeiltasten (Links/Rechts) und Schließen per Leertaste oder Escape.
  - Direkte Auswahl/Abwahl für den Import über die Taste `S` oder Checkbox direkt im Vorschaufenster.
  - Integrierter EXIF-Inspektor mit Kamera-Name, Aufnahmedatum, Dateigröße und Status.
  - Extrem schnelles Rendern von RAW-Dateien über eingebettete JPEG-Previews.
- **Echtzeit-Durchsatz (MB/s) & verbleibende Restzeit (ETA) beim Import:**
  - Während des Importvorgangs wird kontinuierlich die Übertragungsgeschwindigkeit und die verbleibende Restzeit berechnet und im Statusbalken visualisiert.

### Behoben
- **Kompakte Kopfzeile & Versionsanzeige:**
  - Vertikaler Platzbedarf der Titelleiste (`HeaderBanner`) und des Versionsabzeichens (`#versionBadge`) drastisch reduziert (von ~65px auf schlanke 42px).
  - Saubere vertikale Zentrierung von Logo, App-Titel, Versions-Badge und Aktions-Buttons.

## [0.4.0] - 2026-11-03

### Hinzugefügt
- **Modernisierter Fluent Dark Splashscreen (`gui_qt/widgets/splash_screen.py`):**
  - Eleganter Startbildschirm beim App-Start mit Logo, Versionsanzeige und Ladefortschritt (`QSplashScreen`).
  - Asynchrone Statusanzeige während der Initialisierung von Ressourcen, Hardware-Erkennung und Datenmodellen.
- **Speicherplatz-Visualisierung (`gui_qt/widgets/storage_bar.py`):**
  - Dynamische Anzeige des belegten und freien Speichers für Quelllaufwerke (SD-Karten/Ordner) und Ziellaufwerke (Festplatten/Netzwerkfreigaben).
  - Farbcodierte Füllstandsbalken (Normal, Warnung bei >85%, Kritisch bei >95%).
  - **Pre-Flight-Speicherkapazitätsprüfung:** Automatische Vorab-Prüfung, ob auf der Zielfestplatte genügend freier Speicher für die ausgewählten Fotos vorhanden ist, mit visueller Warnung und Sperre bei Speicherengpässen.
- **Stufenloser Zoom-Slider für die Fotogalerie:**
  - Schieberegler in der Filterleiste zum Skalieren der Galerie-Vorschaubilder zwischen 110px und 320px.
  - Dynamische Anpassung des `GalleryDelegate`-Rasters und flüssiges Reflow.
- **Neues 2-Spalten-Layout (Sidebar links, Medienbereich rechts):**
  - Vertikaler Splitter durch horizontalen Splitter ersetzt: Einstellungen, Laufwerksauswahl und Aktionen befinden sich in einer scrollbaren Sidebar links, wodurch der Foto- und Tabellenbereich die maximale Fensterhöhe erhält.
- **Erweiterte Speicherplatz-Erkennung (`core/drive_detector.py`):**
  - Neues Datenmodell `DiskSpaceInfo` und Hilfsfunktionen `get_disk_space()` und `format_size()`.
  - Unterstützung für lokale Festplatten, Wechsellaufwerke und UNC-Netzwerkpfade.

## [0.3.2] - 2026-10-22
