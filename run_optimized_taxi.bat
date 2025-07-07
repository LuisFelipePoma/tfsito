@echo off
echo ========================================
echo  SISTEMA DE DESPACHO DE TAXIS OPTIMIZADO
echo ========================================
echo.
echo Iniciando el sistema optimizado...
echo.

cd /d "%~dp0"
python src\gui\taxi_tkinter_gui.py

echo.
echo Sistema cerrado.
pause
