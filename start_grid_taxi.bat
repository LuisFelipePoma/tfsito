@echo off
echo ========================================
echo    Grid Taxi Constraint Programming
echo ========================================
echo.
echo Iniciando sistema de taxis con:
echo - 3 taxis en movimiento continuo
echo - 4 pasajeros iniciales
echo - Constraint programming con OR-Tools
echo - Movimiento solo en grillas (no diagonal)
echo.
cd /d "d:\OneDrive - Universidad Peruana de Ciencias\Documents\Carrera\2025-1\Tópicos\tfsito"
python src\gui\taxi_grid_constraint_system.py
echo.
echo Sistema finalizado.
pause
