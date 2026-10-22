@echo off
setlocal
title FotoDown

cd /d "%~dp0" 2>nul || pushd "%~dp0"

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py"
    )
)

%PY_CMD% fotodown.py %*

if errorlevel 1 (
    echo.
    echo Es gab ein Problem beim Starten von FotoDown.
    pause
)

popd 2>nul