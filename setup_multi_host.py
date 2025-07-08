#!/usr/bin/env python3
"""
Configurador Automático para Despliegue Multi-Host
=================================================

Este script configura automáticamente el sistema para despliegue distribuido
usando tu configuración específica de OpenFire.
"""

import os
import json
import subprocess
import requests
import time
from pathlib import Path

# Tu configuración específica de OpenFire
OPENFIRE_CONFIG = {
    "host": "localhost",  # Cambiar por IP real del servidor OpenFire
    "domain": "localhost",  # Cambiar por dominio real
    "port": 9090,
    "xmpp_port": 5222,
    "admin_user": "admin",
    "admin_password": "123",
    "secret_key": "jNw5zFIsgCfnk75M"
}

# Configuración de hosts remotos (MODIFICAR SEGÚN TUS HOSTS REALES)
REMOTE_HOSTS = {
    "coordinator": {
        "ip": "192.168.1.100",  # IP del host coordinador
        "type": "coordinator",
        "max_agents": 50
    },
    "taxi_host_1": {
        "ip": "192.168.1.101",  # IP del primer host de taxis
        "type": "taxi_host",
        "max_agents": 100
    },
    "passenger_host_1": {
        "ip": "192.168.1.102",  # IP del primer host de pasajeros
        "type": "passenger_host",
        "max_agents": 150
    },
    "taxi_host_2": {
        "ip": "192.168.1.103",  # IP del segundo host de taxis
        "type": "taxi_host",
        "max_agents": 100
    }
}

def create_host_config(host_id, host_config):
    """Crea archivo de configuración para un host específico"""
    config_content = f"""# ===================================================================
# CONFIGURACIÓN PARA HOST: {host_id.upper()}
# ===================================================================

# OpenFire Configuration (apunta al servidor central)
OPENFIRE_HOST={OPENFIRE_CONFIG['host']}
OPENFIRE_DOMAIN={OPENFIRE_CONFIG['domain']}
OPENFIRE_PORT={OPENFIRE_CONFIG['port']}
OPENFIRE_XMPP_PORT={OPENFIRE_CONFIG['xmpp_port']}
OPENFIRE_ADMIN_USER={OPENFIRE_CONFIG['admin_user']}
OPENFIRE_ADMIN_PASSWORD={OPENFIRE_CONFIG['admin_password']}
OPENFIRE_SECRET_KEY={OPENFIRE_CONFIG['secret_key']}

# Host Configuration
HOST_ID={host_id}
HOST_TYPE={host_config['type']}
HOST_IP={host_config['ip']}

# System Configuration
MAX_AGENTS_PER_HOST={host_config['max_agents']}
HEARTBEAT_INTERVAL=5.0
MESSAGE_TIMEOUT=15.0

# Performance Tuning
TAXI_GRID_WIDTH=50
TAXI_GRID_HEIGHT=50
ASSIGNMENT_INTERVAL=1.0

# Coordinator Reference
COORDINATOR_HOST={REMOTE_HOSTS['coordinator']['ip']}
"""
    
    # Configuración específica por tipo de host
    if host_config['type'] == 'taxi_host':
        config_content += f"""
# Taxi Host Specific
MAX_TAXIS_PER_HOST={host_config['max_agents']}
TAXI_CREATION_RATE=0.1
"""
    elif host_config['type'] == 'passenger_host':
        config_content += f"""
# Passenger Host Specific
MAX_PASSENGERS_PER_HOST={host_config['max_agents']}
PASSENGER_SPAWN_RATE=0.3
PASSENGER_CREATION_INTERVAL=5.0
"""
    
    # Crear directorio config si no existe
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Escribir archivo de configuración
    config_file = config_dir / f"{host_id}.env"
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"✅ Configuración creada: {config_file}")
    return config_file

def create_deployment_scripts():
    """Crea scripts de despliegue específicos para tu configuración"""
    
    # Script para Windows
    windows_script = f"""@echo off
REM ===================================================================
REM SCRIPT DE DESPLIEGUE ESPECÍFICO PARA TU CONFIGURACIÓN
REM ===================================================================

echo 🚕 Sistema de Taxis Distribuido - Configuración Personalizada
echo ===============================================================
echo.
echo Configuración OpenFire:
echo - Host: {OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}
echo - Domain: {OPENFIRE_CONFIG['domain']}
echo - Secret Key: {OPENFIRE_CONFIG['secret_key']}
echo.

if "%1"=="test-local" goto :test_local
if "%1"=="create-configs" goto :create_configs
if "%1"=="start-coordinator" goto :start_coordinator
if "%1"=="start-taxi-host" goto :start_taxi_host
if "%1"=="start-passenger-host" goto :start_passenger_host
goto :show_help

:test_local
echo 🧪 Iniciando prueba local multi-host...
echo.

echo [1/4] Iniciando coordinador...
start "Coordinador" cmd /k "set HOST_TYPE=coordinator && set HOST_ID=coordinator_test && set OPENFIRE_HOST={OPENFIRE_CONFIG['host']} && set OPENFIRE_DOMAIN={OPENFIRE_CONFIG['domain']} && cd src && python distributed_multi_host_system.py --type coordinator --host-id coordinator_test"

timeout /t 8 /nobreak > nul

echo [2/4] Iniciando host de taxis 1...
start "Taxi Host 1" cmd /k "set HOST_TYPE=taxi_host && set HOST_ID=taxi_host_1 && set OPENFIRE_HOST={OPENFIRE_CONFIG['host']} && set OPENFIRE_DOMAIN={OPENFIRE_CONFIG['domain']} && cd src && python distributed_multi_host_system.py --type taxi_host --host-id taxi_host_1"

timeout /t 5 /nobreak > nul

echo [3/4] Iniciando host de pasajeros 1...
start "Passenger Host 1" cmd /k "set HOST_TYPE=passenger_host && set HOST_ID=passenger_host_1 && set OPENFIRE_HOST={OPENFIRE_CONFIG['host']} && set OPENFIRE_DOMAIN={OPENFIRE_CONFIG['domain']} && cd src && python distributed_multi_host_system.py --type passenger_host --host-id passenger_host_1"

timeout /t 5 /nobreak > nul

echo [4/4] Iniciando host de taxis 2...
start "Taxi Host 2" cmd /k "set HOST_TYPE=taxi_host && set HOST_ID=taxi_host_2 && set OPENFIRE_HOST={OPENFIRE_CONFIG['host']} && set OPENFIRE_DOMAIN={OPENFIRE_CONFIG['domain']} && cd src && python distributed_multi_host_system.py --type taxi_host --host-id taxi_host_2"

echo.
echo ✅ Sistema distribuido multi-host iniciado en 4 ventanas separadas
echo 📊 Total de hosts: 4 (1 coordinador + 2 taxi + 1 pasajero)
echo 🚗 Capacidad estimada: 350+ agentes distribuidos
echo.
echo Para detener: cerrar las ventanas o usar Ctrl+C en cada una
goto :end

:create_configs
echo 📝 Creando archivos de configuración para hosts remotos...
python setup_multi_host.py
echo ✅ Configuraciones creadas en la carpeta config/
goto :end

:start_coordinator
echo 🎯 Iniciando COORDINADOR en este host...
cd src
python distributed_multi_host_system.py --type coordinator --host-id coordinator_main --openfire-host {OPENFIRE_CONFIG['host']} --openfire-domain {OPENFIRE_CONFIG['domain']}
goto :end

:start_taxi_host
echo 🚗 Iniciando HOST DE TAXIS en este host...
cd src
python distributed_multi_host_system.py --type taxi_host --host-id taxi_host_%COMPUTERNAME% --openfire-host {OPENFIRE_CONFIG['host']} --openfire-domain {OPENFIRE_CONFIG['domain']}
goto :end

:start_passenger_host
echo 👥 Iniciando HOST DE PASAJEROS en este host...
cd src
python distributed_multi_host_system.py --type passenger_host --host-id passenger_host_%COMPUTERNAME% --openfire-host {OPENFIRE_CONFIG['host']} --openfire-domain {OPENFIRE_CONFIG['domain']}
goto :end

:show_help
echo Uso: %0 [comando]
echo.
echo Comandos disponibles:
echo   test-local         - Prueba local simulando 4 hosts
echo   create-configs     - Crea archivos de configuración
echo   start-coordinator  - Inicia coordinador en este host
echo   start-taxi-host    - Inicia host de taxis en este host
echo   start-passenger-host - Inicia host de pasajeros en este host
echo.
echo CONFIGURACIÓN ACTUAL:
echo   OpenFire: {OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}
echo   Domain: {OPENFIRE_CONFIG['domain']}
echo   Secret Key: {OPENFIRE_CONFIG['secret_key']}
echo.
echo HOSTS CONFIGURADOS:"""

    for host_id, host_config in REMOTE_HOSTS.items():
        windows_script += f"""
echo   {host_id}: {host_config['ip']} ({host_config['type']}) - {host_config['max_agents']} agentes"""

    windows_script += """

:end
pause
"""
    
    # Escribir script de Windows
    with open("deploy_custom.bat", 'w') as f:
        f.write(windows_script)
    
    print("✅ Script de despliegue creado: deploy_custom.bat")

def test_openfire_connection():
    """Prueba la conexión con OpenFire"""
    print("🔍 Probando conexión con OpenFire...")
    
    try:
        url = f"http://{OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ OpenFire accesible en {url}")
            return True
        else:
            print(f"⚠️  OpenFire responde con código {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Error conectando a OpenFire: {e}")
        return False

def calculate_system_capacity():
    """Calcula la capacidad total del sistema"""
    total_agents = sum(host['max_agents'] for host in REMOTE_HOSTS.values())
    taxi_hosts = [h for h in REMOTE_HOSTS.values() if h['type'] == 'taxi_host']
    passenger_hosts = [h for h in REMOTE_HOSTS.values() if h['type'] == 'passenger_host']
    
    print("📊 CAPACIDAD DEL SISTEMA DISTRIBUIDO")
    print("=" * 50)
    print(f"Total de hosts: {len(REMOTE_HOSTS)}")
    print(f"Hosts de taxis: {len(taxi_hosts)}")
    print(f"Hosts de pasajeros: {len(passenger_hosts)}")
    print(f"Capacidad total de agentes: {total_agents}")
    print()
    
    for host_id, host_config in REMOTE_HOSTS.items():
        print(f"  {host_id}: {host_config['ip']} ({host_config['type']}) - {host_config['max_agents']} agentes")

def main():
    """Función principal"""
    print("🚕 CONFIGURADOR MULTI-HOST PARA SISTEMA DE TAXIS")
    print("=" * 60)
    print()
    
    # Mostrar configuración actual
    print("📋 CONFIGURACIÓN ACTUAL:")
    print(f"  OpenFire: {OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}")
    print(f"  Domain: {OPENFIRE_CONFIG['domain']}")
    print(f"  Admin: {OPENFIRE_CONFIG['admin_user']}")
    print(f"  Secret Key: {OPENFIRE_CONFIG['secret_key']}")
    print()
    
    # Calcular capacidad del sistema
    calculate_system_capacity()
    print()
    
    # Probar conexión OpenFire
    openfire_ok = test_openfire_connection()
    print()
    
    # Crear configuraciones para cada host
    print("📝 Creando configuraciones para hosts...")
    for host_id, host_config in REMOTE_HOSTS.items():
        create_host_config(host_id, host_config)
    print()
    
    # Crear scripts de despliegue
    print("🛠️  Creando scripts de despliegue...")
    create_deployment_scripts()
    print()
    
    # Resumen final
    print("✅ CONFIGURACIÓN COMPLETADA")
    print("=" * 30)
    print()
    print("Pasos siguientes:")
    print("1. Revisar y ajustar las IPs en REMOTE_HOSTS si es necesario")
    print("2. Ejecutar: deploy_custom.bat test-local (para prueba local)")
    print("3. Para despliegue real, copiar el proyecto a cada host remoto")
    print("4. En cada host, usar el archivo .env correspondiente")
    print()
    print("Archivos creados:")
    print("  - deploy_custom.bat (script de despliegue)")
    for host_id in REMOTE_HOSTS.keys():
        print(f"  - config/{host_id}.env (configuración)")

if __name__ == "__main__":
    main()
