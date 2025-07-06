@echo off
echo ===============================================
echo    Taxi Dispatch System - Installation
echo ===============================================
echo.

echo [1/5] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [2/5] Testing OR-Tools installation...
python -c "from ortools.sat.python import cp_model; print('OR-Tools: OK')"
if %errorlevel% neq 0 (
    echo WARNING: OR-Tools not working properly
    echo Trying alternative installation...
    pip install --upgrade ortools
)

echo.
echo [3/5] Testing tkinter (built-in GUI)...
python -c "import tkinter; print('Tkinter: OK (built-in)')"

echo.
echo [4/5] Testing SPADE installation...
python -c "import spade; print('SPADE: OK')"
if %errorlevel% neq 0 (
    echo ERROR: SPADE not working properly
    pause
    exit /b 1
)

echo.
echo [5/5] Running quick system test...
python -c "
import sys
sys.path.append('src')
try:
    from agent.libs.taxi_constraints import TaxiDecisionSolver, TaxiState, TaxiConstraints
    print('Constraint system: OK')
except Exception as e:
    print(f'Constraint system: ERROR - {e}')

try:
    from gui.taxi_gui import TaxiDispatchGUI
    print('GUI system: OK')
except Exception as e:
    print(f'GUI system: ERROR - {e}')
"

echo.
echo ===============================================
echo    Installation completed!
echo ===============================================
echo.
echo You can now run the demos:
echo   1. Basic demo: python demo_taxi_dispatch.py
echo   2. Visual demo: Choose option 1 in the demo
echo   3. Full system: Setup Openfire first, then choose option 3
echo.
echo For Openfire setup:
echo   cd src
echo   docker-compose up -d
echo.
pause
