@echo off
echo ========================================
echo 🚕 SISTEMA DE TAXIS INTELIGENTE MEJORADO
echo ========================================
echo.
echo Elige una opción:
echo.
echo 1. Test del sistema (recomendado primero)
echo 2. Demo avanzado con todas las mejoras
echo 3. Demo original (con mejoras integradas)
echo 4. Salir
echo.
set /p choice="Ingresa tu opción (1-4): "

if "%choice%"=="1" goto test
if "%choice%"=="2" goto demo_enhanced
if "%choice%"=="3" goto demo_original
if "%choice%"=="4" goto exit

:test
echo.
echo 🧪 Ejecutando tests del sistema...
echo ====================================
python test_enhanced_system.py
pause
goto menu

:demo_enhanced
echo.
echo 🚀 Iniciando demo avanzado...
echo =============================
echo Características:
echo - Movimiento pseudo-aleatorio continuo
echo - Optimización global con CP-SAT
echo - 7 taxis con distribución inteligente
echo - Generación automática de clientes
echo - Métricas en tiempo real
echo.
python demo_enhanced_taxi_dispatch.py
pause
goto menu

:demo_original
echo.
echo 🔄 Iniciando demo original mejorado...
echo ====================================
python demo_taxi_dispatch.py
pause
goto menu

:exit
echo.
echo 👋 ¡Gracias por usar el sistema de taxis inteligente!
echo.
exit

:menu
cls
goto start

:start
goto begin

:begin
