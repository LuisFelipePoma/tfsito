@echo off
echo ===============================================
echo    SISTEMA DE TAXIS CON MOVIMIENTO CONTINUO
echo ===============================================
echo.
echo Este script ejecuta el sistema de taxis donde:
echo * Los taxis se mueven lentamente y de forma continua
echo * Utilizan patrones de movimiento pseudo-aleatorio
echo * Recogen pasajeros automaticamente
echo * Transportan a destinos especificos
echo * Reanudan movimiento aleatorio despues del viaje
echo.
echo ===============================================
echo Iniciando sistema...
echo ===============================================
echo.

python demo_enhanced_taxi_dispatch.py

echo.
echo ===============================================
echo Sistema finalizado
echo ===============================================
pause
