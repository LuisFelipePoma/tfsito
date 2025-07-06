@echo off
REM Script de despliegue distribuido para Windows
REM deploy_distributed.bat

setlocal EnableDelayedExpansion

REM Configuración
set "PROJECT_NAME=taxi-dispatch"
set "OPENFIRE_HOST=localhost"
set "SSH_USER=%USERNAME%"
set "SSH_PORT=22"
set "SKIP_BUILD=false"
set "DRY_RUN=false"

REM Colores para output (Windows)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "NC=[0m"

REM Función para mostrar uso
:usage
echo Usage: %~n0 [OPTIONS]
echo.
echo Options:
echo   -h, --hosts HOST1,HOST2,HOST3    Comma-separated list of host IPs/names
echo   -a, --agents TOTAL              Total number of agents to deploy
echo   -u, --user USERNAME             SSH username (default: current user)
echo   -p, --port PORT                 SSH port (default: 22)
echo   --openfire-host HOST            Openfire server host (default: localhost)
echo   --dry-run                       Show what would be done without executing
echo   --help                          Show this help message
echo.
echo Examples:
echo   %~n0 -h 192.168.1.10,192.168.1.11 -a 100
echo   %~n0 -h host1,host2,host3 -a 200 -u deploy --openfire-host 192.168.1.5
echo.
goto :eof

REM Función de logging
:log
echo %GREEN%[%date% %time%] %~1%NC%
goto :eof

:warn
echo %YELLOW%[%date% %time%] WARNING: %~1%NC%
goto :eof

:error
echo %RED%[%date% %time%] ERROR: %~1%NC%
goto :eof

REM Parsear argumentos
set "HOSTS="
set "TOTAL_AGENTS="

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="-h" (
    set "HOSTS=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--hosts" (
    set "HOSTS=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="-a" (
    set "TOTAL_AGENTS=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--agents" (
    set "TOTAL_AGENTS=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="-u" (
    set "SSH_USER=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--user" (
    set "SSH_USER=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="-p" (
    set "SSH_PORT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--port" (
    set "SSH_PORT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--openfire-host" (
    set "OPENFIRE_HOST=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--dry-run" (
    set "DRY_RUN=true"
    shift
    goto :parse_args
)
if "%~1"=="--help" (
    call :usage
    exit /b 0
)
call :error "Unknown option: %~1"
call :usage
exit /b 1

:args_done

REM Validar argumentos requeridos
if "%HOSTS%"=="" (
    call :error "Hosts list is required (-h|--hosts)"
    call :usage
    exit /b 1
)

if "%TOTAL_AGENTS%"=="" (
    call :error "Total agents is required (-a|--agents)"
    call :usage
    exit /b 1
)

call :log "Starting distributed deployment"
call :log "Hosts: %HOSTS%"
call :log "Total agents: %TOTAL_AGENTS%"
call :log "SSH User: %SSH_USER%"
call :log "Openfire Host: %OPENFIRE_HOST%"

if "%DRY_RUN%"=="true" (
    call :warn "DRY RUN MODE - No changes will be made"
)

REM Verificar que Python esté instalado
python --version >nul 2>&1
if errorlevel 1 (
    call :error "Python is not installed or not in PATH"
    exit /b 1
)

REM Verificar que los requisitos estén instalados
python -c "import psutil, spade" >nul 2>&1
if errorlevel 1 (
    call :warn "Some Python requirements may be missing. Installing..."
    pip install -r requirements.txt
)

REM Usar Python para el despliegue distribuido (más robusto que batch)
call :log "Using Python distribution manager for deployment..."

if "%DRY_RUN%"=="true" (
    python distribution_manager.py --total-agents %TOTAL_AGENTS% --hosts %HOSTS% --skip-benchmark --monitor-duration 5
) else (
    python distribution_manager.py --total-agents %TOTAL_AGENTS% --hosts %HOSTS% --monitor-duration 15
)

if errorlevel 1 (
    call :error "Deployment failed"
    exit /b 1
) else (
    call :log "Deployment completed successfully"
    call :log "To monitor the deployment, you can run:"
    call :log "python distribution_manager.py --total-agents %TOTAL_AGENTS% --hosts %HOSTS% --monitor-duration 30"
)

endlocal
exit /b 0
