@echo off
title Taxi Dispatch System - Quick Start

echo.
echo  🚕 TAXI DISPATCH SYSTEM 🚕
echo ============================
echo.
echo Select demo to run:
echo.
echo [1] Visual Demo (Recommended)
echo     - Interactive GUI with tkinter
echo     - Watch taxis move and pick up passengers
echo     - Automatic client generation
echo.
echo [2] Constraint Logic Demo
echo     - Test OR-Tools decision making
echo     - No GUI required
echo     - Shows constraint evaluation
echo.
echo [3] Full SPADE System Demo
echo     - Complete multi-agent system
echo     - Requires Openfire server
echo     - Real distributed communication
echo.
echo [4] Install/Update Dependencies
echo.
echo [0] Exit
echo.

set /p choice="Enter your choice (0-4): "

if "%choice%"=="1" goto visual_demo
if "%choice%"=="2" goto constraint_demo
if "%choice%"=="3" goto full_demo
if "%choice%"=="4" goto install
if "%choice%"=="0" goto exit
goto invalid_choice

:visual_demo
echo.
echo Starting Visual Demo...
echo (Using tkinter GUI from standard library)
echo.
python demo_taxi_dispatch.py
echo 1 | python demo_taxi_dispatch.py
goto end

:constraint_demo
echo.
echo Starting Constraint Logic Demo...
echo.
echo 2 | python demo_taxi_dispatch.py
goto end

:full_demo
echo.
echo Starting Full SPADE System Demo...
echo (Make sure Openfire is running: cd src && docker-compose up -d)
echo.
echo 3 | python demo_taxi_dispatch.py
goto end

:install
echo.
echo Installing/Updating dependencies...
echo.
call install.bat
goto end

:invalid_choice
echo.
echo Invalid choice. Please select 0-4.
echo.
pause
goto start

:end
echo.
echo Demo finished. Press any key to return to menu...
pause > nul
cls
goto start

:exit
echo.
echo Goodbye!
echo.
pause
exit
