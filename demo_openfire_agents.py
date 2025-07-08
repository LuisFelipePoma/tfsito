#!/usr/bin/env python3
"""
🚕 DEMO SIMPLE CON AGENTES OPENFIRE
===================================

Demo simplificado que crea agentes reales en OpenFire usando la API REST.
Ejecuta el sistema de taxis y muestra los agentes creados en el servidor.

Uso: python demo_openfire_agents.py
"""

import sys
import os
import time
import requests
import json
from typing import Dict, List

# Configuración OpenFire
OPENFIRE_CONFIG = {
    "host": "localhost",
    "port": 9090,
    "admin_user": "admin", 
    "admin_password": "123",
    "secret_key": "jNw5zFIsgCfnk75M",
    "domain": "localhost"
}

class OpenFireAgentManager:
    """Gestiona agentes en OpenFire usando API REST"""
    
    def __init__(self):
        self.base_url = f"http://{OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}/plugins/restapi/v1"
        self.headers = {
            "Authorization": f"Bearer {OPENFIRE_CONFIG['secret_key']}",
            "Content-Type": "application/json"
        }
        self.created_agents = []
    
    def test_connection(self):
        """Prueba la conexión con OpenFire"""
        try:
            response = requests.get(f"{self.base_url}/system/properties", headers=self.headers, timeout=5)
            if response.status_code == 200:
                print("✅ Conexión con OpenFire exitosa")
                return True
            else:
                print(f"❌ Error de conexión: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ No se puede conectar con OpenFire: {e}")
            return False
    
    def create_agent(self, agent_id: str, agent_type: str, host_id: str = "local"):
        """Crea un agente en OpenFire"""
        try:
            # Datos del usuario/agente
            user_data = {
                "username": agent_id,
                "password": f"{agent_id}123",
                "name": f"{agent_type.title()} {agent_id}",
                "email": f"{agent_id}@{OPENFIRE_CONFIG['domain']}",
                "properties": {
                    "agent_type": agent_type,
                    "host_id": host_id,
                    "created_by": "taxi_system",
                    "creation_time": str(int(time.time()))
                }
            }
            
            # Crear usuario en OpenFire
            response = requests.post(
                f"{self.base_url}/users",
                headers=self.headers,
                json=user_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.created_agents.append({
                    "id": agent_id,
                    "type": agent_type, 
                    "host": host_id,
                    "jid": f"{agent_id}@{OPENFIRE_CONFIG['domain']}",
                    "password": f"{agent_id}123"
                })
                print(f"✅ Agente {agent_type} '{agent_id}' creado en OpenFire")
                return True
            else:
                # Si ya existe, no es error
                if response.status_code == 409:
                    print(f"ℹ️ Agente '{agent_id}' ya existe en OpenFire")
                    return True
                else:
                    print(f"❌ Error creando agente '{agent_id}': {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error creando agente '{agent_id}': {e}")
            return False
    
    def list_agents(self):
        """Lista todos los agentes creados"""
        try:
            response = requests.get(f"{self.base_url}/users", headers=self.headers, timeout=10)
            if response.status_code == 200:
                users = response.json()
                taxi_agents = []
                
                # Filtrar agentes del sistema de taxis
                for user in users.get("users", []):
                    username = user.get("username", "")
                    if username.startswith(("taxi_", "passenger_", "coordinator")):
                        taxi_agents.append(user)
                
                return taxi_agents
            else:
                print(f"❌ Error listando usuarios: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error listando agentes: {e}")
            return []
    
    def delete_all_taxi_agents(self):
        """Elimina todos los agentes del sistema de taxis"""
        agents = self.list_agents()
        deleted = 0
        
        for agent in agents:
            username = agent.get("username", "")
            try:
                response = requests.delete(
                    f"{self.base_url}/users/{username}",
                    headers=self.headers,
                    timeout=10
                )
                if response.status_code in [200, 204]:
                    print(f"🗑️ Agente '{username}' eliminado")
                    deleted += 1
            except Exception as e:
                print(f"❌ Error eliminando '{username}': {e}")
        
        print(f"✅ {deleted} agentes eliminados del sistema")
        return deleted

def create_distributed_taxi_system():
    """Crea el sistema distribuido completo de agentes"""
    
    print("🚕" * 30)
    print("   CREANDO SISTEMA DISTRIBUIDO DE TAXIS")
    print("   Agentes reales en OpenFire")
    print("🚕" * 30)
    print()
    
    manager = OpenFireAgentManager()
    
    # Probar conexión
    print("🔧 Probando conexión con OpenFire...")
    if not manager.test_connection():
        print("❌ No se puede conectar con OpenFire. Verifique:")
        print("   - OpenFire está ejecutándose")
        print("   - Puerto 9090 está abierto")
        print("   - Usuario admin/123 configurado")
        print(f"   - Secret key: {OPENFIRE_CONFIG['secret_key']}")
        return
    
    print()
    
    # Limpiar agentes previos
    print("🧹 Limpiando agentes previos...")
    manager.delete_all_taxi_agents()
    print()
    
    # Crear coordinador
    print("🎯 Creando agente coordinador...")
    manager.create_agent("coordinator", "coordinator", "coordinator_host")
    print()
    
    # Crear agentes taxi distribuidos
    print("🚖 Creando agentes taxi...")
    taxi_hosts = ["taxi_host_1", "taxi_host_2"]
    
    for i in range(4):  # 4 taxis
        taxi_id = f"taxi_{i+1}"
        host_id = taxi_hosts[i % len(taxi_hosts)]  # Alternar entre hosts
        manager.create_agent(taxi_id, "taxi", host_id)
    
    print()
    
    # Crear agentes pasajero
    print("👥 Creando agentes pasajero...")
    for i in range(5):  # 5 pasajeros iniciales
        passenger_id = f"passenger_{i+1}"
        manager.create_agent(passenger_id, "passenger", "passenger_host")
    
    print()
    
    # Mostrar resumen
    print("📊 RESUMEN DEL SISTEMA DISTRIBUIDO")
    print("=" * 50)
    
    agents = manager.list_agents()
    if agents:
        # Agrupar por tipo
        coordinators = [a for a in agents if a["username"] == "coordinator"]
        taxis = [a for a in agents if a["username"].startswith("taxi_")]
        passengers = [a for a in agents if a["username"].startswith("passenger_")]
        
        print(f"🎯 Coordinadores: {len(coordinators)}")
        for coord in coordinators:
            print(f"   • {coord['username']}@{OPENFIRE_CONFIG['domain']}")
        
        print(f"\n🚖 Taxis: {len(taxis)}")
        for taxi in taxis:
            print(f"   • {taxi['username']}@{OPENFIRE_CONFIG['domain']}")
        
        print(f"\n👥 Pasajeros: {len(passengers)}")
        for passenger in passengers:
            print(f"   • {passenger['username']}@{OPENFIRE_CONFIG['domain']}")
        
        print(f"\n✅ TOTAL: {len(agents)} agentes creados en OpenFire")
        print(f"🌐 Dominio: {OPENFIRE_CONFIG['domain']}")
        print(f"🔧 Host OpenFire: {OPENFIRE_CONFIG['host']}:{OPENFIRE_CONFIG['port']}")
        
    else:
        print("❌ No se pudieron crear agentes")
    
    print()
    print("🎮 PRÓXIMOS PASOS:")
    print("   1. Los agentes están creados en OpenFire")
    print("   2. Ejecutar: python demo_spade_gui_local.py")
    print("   3. O usar cualquier cliente XMPP para ver los agentes")
    print("   4. Verificar en admin OpenFire: http://localhost:9090")
    
    return len(agents) if agents else 0

def show_current_agents():
    """Muestra los agentes actuales en OpenFire"""
    print("📋 AGENTES ACTUALES EN OPENFIRE")
    print("=" * 40)
    
    manager = OpenFireAgentManager()
    
    if not manager.test_connection():
        print("❌ No se puede conectar con OpenFire")
        return
    
    agents = manager.list_agents()
    if agents:
        print(f"📊 Total: {len(agents)} agentes del sistema de taxis")
        print()
        
        for agent in agents:
            username = agent.get("username", "")
            name = agent.get("name", "")
            email = agent.get("email", "")
            
            # Determinar tipo
            if username == "coordinator":
                type_emoji = "🎯"
                type_name = "Coordinador"
            elif username.startswith("taxi_"):
                type_emoji = "🚖"
                type_name = "Taxi"
            elif username.startswith("passenger_"):
                type_emoji = "👤"
                type_name = "Pasajero"
            else:
                type_emoji = "❓"
                type_name = "Desconocido"
            
            print(f"{type_emoji} {type_name}: {username}")
            print(f"   JID: {username}@{OPENFIRE_CONFIG['domain']}")
            print(f"   Nombre: {name}")
            print()
    else:
        print("ℹ️ No hay agentes del sistema de taxis en OpenFire")

def cleanup_agents():
    """Limpia todos los agentes del sistema"""
    print("🧹 LIMPIANDO AGENTES DEL SISTEMA")
    print("=" * 40)
    
    manager = OpenFireAgentManager()
    
    if not manager.test_connection():
        print("❌ No se puede conectar con OpenFire")
        return
    
    deleted = manager.delete_all_taxi_agents()
    if deleted > 0:
        print(f"✅ {deleted} agentes eliminados exitosamente")
    else:
        print("ℹ️ No había agentes para eliminar")

def main():
    """Función principal con menú"""
    while True:
        print("\n🚕 GESTIÓN DE AGENTES OPENFIRE")
        print("=" * 40)
        print("1. 🏗️  Crear sistema distribuido completo")
        print("2. 📋 Ver agentes actuales")
        print("3. 🧹 Limpiar todos los agentes")
        print("4. 🔧 Probar conexión OpenFire") 
        print("5. ❌ Salir")
        print()
        
        choice = input("Selecciona una opción (1-5): ").strip()
        
        if choice == "1":
            create_distributed_taxi_system()
        elif choice == "2":
            show_current_agents()
        elif choice == "3":
            cleanup_agents()
        elif choice == "4":
            manager = OpenFireAgentManager()
            manager.test_connection()
        elif choice == "5":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida")
        
        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    main()
