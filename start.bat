@echo off
REM Script de inicio para TFS ITO en Windows

echo === TFS ITO - Traffic Flow System ===
echo Iniciando sistema de control de trafico aereo...

if "%1"=="start" goto start_full
if "%1"=="env" goto start_env
if "%1"=="towers" goto start_towers
if "%1"=="stop" goto stop_system
if "%1"=="clean" goto clean_system
if "%1"=="logs" goto show_logs
if "%1"=="status" goto show_status
if "%1"=="help" goto show_help
if "%1"=="" goto show_help

:show_help
echo Uso: %0 [OPCION]
echo Opciones:
echo   start       - Iniciar sistema completo
echo   env         - Solo Environment Agent
echo   towers      - Environment + Torres
echo   stop        - Detener sistema
echo   clean       - Limpiar contenedores y volumenes
echo   logs        - Mostrar logs
echo   status      - Mostrar estado de contenedores
echo   help        - Mostrar esta ayuda
goto end

:start_full
echo Iniciando sistema completo...
cd src
docker-compose up --build -d
echo Sistema iniciado. Interfaces disponibles:
echo   - Interfaz web: http://localhost:8080
echo   - Openfire admin: http://localhost:9090 (admin/admin)
echo.
echo Torres activas creando aeronaves dinamicamente:
echo   - TWR_SABE: Aeronaves SABE_XXX
echo   - TWR_SAEZ: Aeronaves SAEZ_XXX
goto end

:start_env
echo Iniciando solo Environment Agent...
cd src
docker-compose up --build env_agent openfire -d
echo Environment Agent iniciado: http://localhost:8080
goto end

:start_towers
echo Iniciando Environment Agent y Torres...
cd src
docker-compose up --build env_agent openfire tower_agent_sabe tower_agent_saez -d
echo Environment y Torres iniciados: http://localhost:8080
goto end

:stop_system
echo Deteniendo sistema...
cd src
docker-compose down
echo Sistema detenido.
goto end

:clean_system
echo Limpiando sistema...
cd src
docker-compose down -v --remove-orphans
docker system prune -f
echo Sistema limpiado.
goto end

:show_logs
echo Mostrando logs del sistema...
cd src
docker-compose logs -f
goto end

:show_status
echo Estado de contenedores:
cd src
docker-compose ps
echo.
echo Uso de recursos:
docker stats --no-stream
goto end

:end
