@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title FotoDown - Windows Installation

echo =====================================================
echo    FotoDown - Installations-Assistent für Windows
echo =====================================================
echo.

cd /d "%~dp0" 2>nul || pushd "%~dp0"

:: 1. Python prüfen
set "PY_CMD="
where python >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo [FEHLER] Python wurde auf Ihrem System nicht gefunden!
    echo.
    echo Bitte laden Sie Python herunter und installieren Sie es:
    echo https://www.python.org/downloads/
    echo.
    echo WICHTIG: Setzen Sie bei der Installation unbedingt den Haken bei:
    echo "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python gefunden:
%PY_CMD% --version
echo.

:: 2. Virtuelle Umgebung erstellen
echo [1/3] Richte isolierte Python-Umgebung (.venv) ein...
if not exist ".venv" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] Die virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo [OK] Virtuelle Umgebung .venv erstellt.
) else (
    echo [OK] Bestehende Umgebung .venv gefunden.
)
echo.

:: 3. Abhängigkeiten installieren
echo [2/3] Installiere benötigte Pakete (PySide6, Pillow)...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [FEHLER] Fehler bei der Installation der Abhängigkeiten.
    pause
    exit /b 1
)
echo [OK] Alle Abhängigkeiten erfolgreich installiert.
echo.

:: 4. Desktop-Verknüpfung erstellen
echo [3/3] Erstelle Desktop-Verknüpfung...
set "BAT_PATH=%~dp0FotoDown.bat"
set "ICON_PATH=%~dp0assets\fotodown.ico"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\FotoDown.lnk'); $s.TargetPath = '%BAT_PATH%'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%ICON_PATH%,0'; $s.Description = 'FotoDown - Foto-Importeur & EXIF-Manager'; $s.Save()"

if exist "%DESKTOP_DIR%\FotoDown.lnk" (
    echo [OK] Desktop-Verknüpfung 'FotoDown' wurde erfolgreich erstellt.
) else (
    echo [Hinweis] Verknüpfung konnte nicht automatisch auf dem Desktop angelegt werden.
)
echo.

echo =====================================================
echo    Installation erfolgreich abgeschlossen!
echo =====================================================
echo.
echo Sie können FotoDown jetzt starten:
echo  - Per Doppelklick auf die Verknüpfung 'FotoDown' auf Ihrem Desktop
echo  - Oder direkt über 'FotoDown.bat' in diesem Ordner
echo.
set /p "START_NOW=Möchten Sie FotoDown jetzt starten? (J/N): "
if /i "%START_NOW%"=="J" (
    start "" "%~dp0FotoDown.bat"
)

popd 2>nul
