@echo off
title FotoDown
chcp 65001 > nul

:: pushd unterstützt im Gegensatz zu 'cd' auch UNC-Netzwerkpfade (z.B. \\192.168.x.x\...)
:: indem es temporär automatisch einen Laufwerksbuchstaben zuweist.
pushd "%~dp0"

python fotodown.py

if errorlevel 1 (
    echo.
    echo Es gab ein Problem beim Starten von FotoDown.
    pause
)

popd
