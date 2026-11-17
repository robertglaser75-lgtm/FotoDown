@echo off
setlocal
title Vitrina

cd /d "%~dp0" 2>nul || pushd "%~dp0"

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PY_CMD=py"
        )
    )
)

%PY_CMD% vitrina.py %*

if errorlevel 1 (
    echo.
    echo Es gab ein Problem beim Starten von Vitrina.
    pause
)

popd 2>nul
