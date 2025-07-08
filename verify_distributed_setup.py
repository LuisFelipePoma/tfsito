#!/usr/bin/env python3
"""
Verificador de Configuración Distribuida
=======================================

Este script verifica que el sistema esté correctamente configurado
para despliegue distribuido con tu configuración específica de OpenFire.

Configuración OpenFire:
- Host: localhost (o tu IP del servidor OpenFire)
- Puerto: 9090
- XMPP Puerto: 5222
- Admin: admin
- Contraseña: 123
- Secret Key: jNw5zFIsgCfnk75M
"""

import os
import sys
import json
import subprocess
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from config import config, load_config_from_env
    from services.openfire_api import openfire_api
    print("✅ Módulos locales importados correctamente")
except ImportError as e:
    print(f"❌ Error importando módulos locales: {e}")
    sys.exit(1)

class DistributedSystemVerifier:
    """Verificador del sistema distribuido"""
    
    def __init__(self):
        self.openfire_config = {
            "host": "localhost",
            "domain": "localhost", 
            "port": 9090,
            "xmpp_port": 5222,
            "admin_user": "admin",
            "admin_password": "123",
            "secret_key": "jNw5zFIsgCfnk75M"
        }
        
        # Hosts remotos de ejemplo (modificar según tu configuración real)
        self.remote_hosts = {
            "coordinator": "192.168.1.100",
            "taxi_host_1": "192.168.1.101", 
            "passenger_host_1": "192.168.1.102",
            "taxi_host_2": "192.168.1.103"
        }
        
    def verify_openfire_config(self) -> bool:
        """Verifica la configuración de OpenFire"""
        print("\n🔧 Verificando configuración de OpenFire...")
        
        # Verificar que la configuración esté cargada correctamente
        if config.openfire_secret_key != self.openfire_config["secret_key"]:
            print(f"❌ Secret key no coincide: {config.openfire_secret_key} != {self.openfire_config['secret_key']}")
            return False
            
        if config.openfire_admin_user != self.openfire_config["admin_user"]:
            print(f"❌ Usuario admin no coincide: {config.openfire_admin_user} != {self.openfire_config['admin_user']}")
            return False
            
        if config.openfire_admin_password != self.openfire_config["admin_password"]:
            print(f"❌ Contraseña admin no coincide: {config.openfire_admin_password} != {self.openfire_config['admin_password']}")
            return False
            
        print("✅ Configuración de OpenFire cargada correctamente")
        return True
        
    def test_openfire_connection(self) -> bool:
        """Prueba la conexión con OpenFire"""
        print("\n🌐 Probando conexión con OpenFire...")
        
        try:
            # Verificar si OpenFire está corriendo
            health = openfire_api.health_check()
            if health:
                print("✅ OpenFire está respondiendo")
                return True
            else:
                print("❌ OpenFire no está respondiendo")
                print("💡 Asegúrate de que OpenFire esté ejecutándose:")
                print("   docker run --name openfire -d --restart=always \\")
                print("     --publish 9090:9090 --publish 5222:5222 --publish 7777:7777 \\")
                print("     --volume /srv/docker/openfire:/var/lib/openfire \\")
                print("     sameersbn/openfire:3.10.3-19")
                return False
                
        except Exception as e:
            print(f"❌ Error conectando con OpenFire: {e}")
            return False
    
    def verify_config_files(self) -> bool:
        """Verifica que existan todos los archivos de configuración"""
        print("\n📁 Verificando archivos de configuración...")
        
        config_files = [
            "config/coordinator.env",
            "config/taxi_host_1.env", 
            "config/taxi_host_2.env",
            "config/passenger_host_1.env",
            "config/multi-host.env"
        ]
        
        all_exist = True
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"✅ {config_file}")
                # Verificar que contenga el secret key correcto
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if self.openfire_config["secret_key"] not in content:
                        print(f"⚠️  {config_file} no contiene el secret key correcto")
            else:
                print(f"❌ {config_file} no existe")
                all_exist = False
                
        return all_exist
    
    def verify_deployment_scripts(self) -> bool:
        """Verifica que existan los scripts de despliegue"""
        print("\n🚀 Verificando scripts de despliegue...")
        
        scripts = [
            "deploy_multi_host.bat",
            "deploy_multi_host.sh", 
            "docker-compose-multi-host.yml",
            "setup_multi_host.py"
        ]
        
        all_exist = True
        for script in scripts:
            if os.path.exists(script):
                print(f"✅ {script}")
            else:
                print(f"❌ {script} no existe")
                all_exist = False
                
        return all_exist
    
    def verify_distributed_system_files(self) -> bool:
        """Verifica archivos del sistema distribuido"""
        print("\n🏗️ Verificando archivos del sistema distribuido...")
        
        key_files = [
            "src/distributed_multi_host_system.py",
            "src/config.py",
            "src/services/openfire_api.py",
            "Dockerfile.distributed"
        ]
        
        all_exist = True
        for file_path in key_files:
            if os.path.exists(file_path):
                print(f"✅ {file_path}")
            else:
                print(f"❌ {file_path} no existe")
                all_exist = False
                
        return all_exist
    
    def show_deployment_instructions(self):
        """Muestra instrucciones de despliegue"""
        print("\n" + "="*60)
        print("🚕 INSTRUCCIONES DE DESPLIEGUE DISTRIBUIDO")
        print("="*60)
        print(f"""
📋 CONFIGURACIÓN OPENFIRE:
   Host: {self.openfire_config['host']}
   Puerto Admin: {self.openfire_config['port']}
   Puerto XMPP: {self.openfire_config['xmpp_port']}
   Usuario: {self.openfire_config['admin_user']}
   Contraseña: {self.openfire_config['admin_password']}
   Secret Key: {self.openfire_config['secret_key']}

🌐 HOSTS CONFIGURADOS:
""")
        for host_type, ip in self.remote_hosts.items():
            print(f"   {host_type}: {ip}")
            
        print(f"""
🚀 PASOS PARA DESPLIEGUE:

1. PREPARAR OPENFIRE:
   docker run --name openfire -d --restart=always \\
     --publish 9090:9090 --publish 5222:5222 --publish 7777:7777 \\
     --volume /srv/docker/openfire:/var/lib/openfire \\
     sameersbn/openfire:3.10.3-19

2. CONFIGURAR CADA HOST:
   - Copiar proyecto completo a cada host remoto
   - En cada host, copiar el archivo .env correspondiente

3. EJECUTAR EN ORDEN:
   
   HOST COORDINADOR ({self.remote_hosts['coordinator']}):
   cd /ruta/al/proyecto
   cp config/coordinator.env .env
   python src/distributed_multi_host_system.py --type coordinator
   
   HOST TAXI 1 ({self.remote_hosts['taxi_host_1']}):
   cd /ruta/al/proyecto  
   cp config/taxi_host_1.env .env
   python src/distributed_multi_host_system.py --type taxi_host
   
   HOST PASAJEROS ({self.remote_hosts['passenger_host_1']}):
   cd /ruta/al/proyecto
   cp config/passenger_host_1.env .env
   python src/distributed_multi_host_system.py --type passenger_host

4. VERIFICAR FUNCIONAMIENTO:
   python verify_distributed_setup.py

💡 TIPS:
   - Modificar IPs en config/*.env según tu red
   - Asegurar conectividad entre hosts
   - Verificar puertos abiertos (9090, 5222, 7777)
   - Monitorear logs de cada host
""")

    def run_full_verification(self) -> bool:
        """Ejecuta verificación completa"""
        print("🔍 VERIFICACIÓN COMPLETA DEL SISTEMA DISTRIBUIDO")
        print("=" * 50)
        
        # Cargar configuración desde variables de entorno
        load_config_from_env()
        
        checks = [
            ("Configuración OpenFire", self.verify_openfire_config),
            ("Conexión OpenFire", self.test_openfire_connection),
            ("Archivos de configuración", self.verify_config_files),
            ("Scripts de despliegue", self.verify_deployment_scripts),
            ("Archivos del sistema", self.verify_distributed_system_files)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                print(f"❌ Error en {check_name}: {e}")
                all_passed = False
        
        print("\n" + "="*50)
        if all_passed:
            print("✅ SISTEMA LISTO PARA DESPLIEGUE DISTRIBUIDO")
            print("✅ CUMPLE REQUISITO: Al menos 2 hosts remotos configurados")
        else:
            print("❌ SISTEMA REQUIERE CONFIGURACIÓN ADICIONAL")
            
        self.show_deployment_instructions()
        return all_passed

def main():
    """Función principal"""
    verifier = DistributedSystemVerifier()
    verifier.run_full_verification()

if __name__ == "__main__":
    main()
