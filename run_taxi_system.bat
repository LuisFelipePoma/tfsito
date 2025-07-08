@echo off
echo ========================================
echo  Sistema de Despacho de Taxis Distribuido
echo ========================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instale Python 3.7+ desde https://python.org
    pause
    exit /b 1
)

echo Python encontrado, iniciando sistema...
echo.

:: Change to src directory
cd /d "%~dp0src"

:: Install required packages (optional dependencies)
echo Verificando dependencias opcionales...
pip install ortools --quiet 2>nul || echo OR-Tools no disponible, usando algoritmo greedy
pip install spade --quiet 2>nul || echo SPADE no disponible, ejecutando en modo local

echo.
echo Iniciando sistema de taxis...
echo Presione Ctrl+C para detener
echo.

:: Run the taxi system
python distributed_taxi_system.py

echo.
echo Sistema terminado.
pause
