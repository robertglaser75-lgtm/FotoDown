@echo off
setlocal
title Vitrina (FotoDown)

cd /d "%~dp0" 2>nul || pushd "%~dp0"
call "%~dp0Vitrina.bat" %*
popd 2>nul
