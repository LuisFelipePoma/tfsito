import asyncio
import json
import websockets
import time
import os
import random
import math
import requests
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message


class TowerAgent(Agent):
    def __init__(self, jid, password, tower_id="TWR001", airport="SABE", *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.aircraft_buffer = {}  # {aircraft_id: {position, altitude}}
        self.tower_id = tower_id
        self.airport = airport
        self.environment_jid = None
        self.environment_info = {}
        self.managed_aircraft = {}  # {aircraft_id: aircraft_data}
        self.openfire_api_url = None
        self.openfire_auth = None

    class SetupOpenFireAPI(OneShotBehaviour):
        """Configura la conexión con la API REST de OpenFire"""
        async def run(self):
            xmpp_server = os.getenv("XMPP_SERVER", "localhost")
            self.agent.openfire_api_url = f"http://{xmpp_server}:9090/plugins/restapi/v1"
            self.agent.openfire_auth = ("admin", "admin")
            print(f"[TWR] API OpenFire configurada: {self.agent.openfire_api_url}")

    class RegisterWithEnvironment(OneShotBehaviour):
        """Registra la torre con el Environment Agent"""
        async def run(self):
            xmpp_server = os.getenv("XMPP_SERVER", "localhost")
            env_jid = f"environment@{xmpp_server}"
            
            registration_msg = Message(to=env_jid)
            registration_msg.body = json.dumps({
                "type": "tower_registration",
                "tower_id": self.agent.tower_id,
                "airport": self.agent.airport
            })
            
            await self.send(registration_msg)
            self.agent.environment_jid = env_jid
            print(f"[TWR] Registro enviado al Environment Agent: {env_jid}")

    class AircraftCreationBehaviour(CyclicBehaviour):
        """Crea aeronaves automáticamente"""
        async def run(self):
            await asyncio.sleep(30)  # Crear aeronave cada 30 segundos
            
            # Límite de aeronaves por torre
            max_aircraft = 5
            if len(self.agent.managed_aircraft) < max_aircraft:
                await self.create_aircraft()

        async def create_aircraft(self):
            """Crea una nueva aeronave"""
            aircraft_id = f"{self.agent.airport}_{random.randint(100, 999)}"
            aircraft_jid = f"{aircraft_id.lower()}@{os.getenv('XMPP_SERVER', 'localhost')}"
            
            # Crear usuario en OpenFire via API REST
            success = await self.register_aircraft_in_openfire(aircraft_id, aircraft_jid)
            
            if success:
                # Crear datos de la aeronave
                aircraft_data = {
                    "aircraft_id": aircraft_id,
                    "jid": aircraft_jid,
                    "position": {
                        "lat": -34.6037 + random.uniform(-0.5, 0.5),
                        "lon": -58.3816 + random.uniform(-0.5, 0.5)
                    },
                    "altitude": random.randint(1000, 35000),
                    "heading": random.randint(0, 360),
                    "speed": random.randint(200, 500),
                    "target": {
                        "lat": -34.6037 + random.uniform(-1.0, 1.0),
                        "lon": -58.3816 + random.uniform(-1.0, 1.0)
                    },
                    "status": "active",
                    "created_at": time.time(),
                    "last_update": time.time()
                }
                
                self.agent.managed_aircraft[aircraft_id] = aircraft_data
                print(f"[TWR] Aeronave creada: {aircraft_id} - {aircraft_jid}")
                
                # Notificar al Environment Agent
                await self.notify_environment_new_aircraft(aircraft_data)

        async def register_aircraft_in_openfire(self, aircraft_id, aircraft_jid):
            """Registra la aeronave en OpenFire via API REST"""
            try:
                url = f"{self.agent.openfire_api_url}/users"
                data = {
                    "username": aircraft_id.lower(),
                    "password": "aircraft123",
                    "name": f"Aircraft {aircraft_id}",
                    "email": f"{aircraft_id.lower()}@aircraft.local"
                }
                
                response = requests.post(url, json=data, auth=self.agent.openfire_auth, timeout=10)
                
                if response.status_code == 201:
                    print(f"[TWR] Usuario {aircraft_id} registrado en OpenFire")
                    return True
                elif response.status_code == 409:
                    print(f"[TWR] Usuario {aircraft_id} ya existe en OpenFire")
                    return True
                else:
                    print(f"[TWR] Error al registrar {aircraft_id}: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"[TWR] Error al conectar con OpenFire API: {e}")
                return False

        async def notify_environment_new_aircraft(self, aircraft_data):
            """Notifica al Environment Agent sobre nueva aeronave"""
            if self.agent.environment_jid:
                env_msg = Message(to=self.agent.environment_jid)
                env_msg.body = json.dumps({
                    "type": "aircraft_created",
                    "aircraft_id": aircraft_data["aircraft_id"],
                    "position": aircraft_data["position"],
                    "altitude": aircraft_data["altitude"],
                    "tower": self.agent.tower_id,
                    "jid": aircraft_data["jid"]
                })
                await self.send(env_msg)

    class AircraftSimulationBehaviour(CyclicBehaviour):
        """Simula el comportamiento de las aeronaves gestionadas"""
        async def run(self):
            await asyncio.sleep(2)  # Actualizar cada 2 segundos
            
            for aircraft_id, aircraft_data in self.agent.managed_aircraft.items():
                await self.simulate_aircraft_movement(aircraft_id, aircraft_data)
                await self.report_aircraft_position(aircraft_id, aircraft_data)

        async def simulate_aircraft_movement(self, aircraft_id, aircraft_data):
            """Simula el movimiento de una aeronave"""
            # Calcular movimiento hacia el objetivo
            lat_diff = aircraft_data["target"]["lat"] - aircraft_data["position"]["lat"]
            lon_diff = aircraft_data["target"]["lon"] - aircraft_data["position"]["lon"]
            distance = math.sqrt(lat_diff**2 + lon_diff**2)
            
            if distance > 0.001:  # Si no hemos llegado
                # Mover hacia el objetivo
                speed_factor = 0.001
                aircraft_data["position"]["lat"] += lat_diff * speed_factor
                aircraft_data["position"]["lon"] += lon_diff * speed_factor
                
                # Pequeña variación aleatoria para simular turbulencia
                aircraft_data["position"]["lat"] += random.uniform(-0.0001, 0.0001)
                aircraft_data["position"]["lon"] += random.uniform(-0.0001, 0.0001)
                
                # Pequeña variación en altitud
                alt_change = random.randint(-100, 100)
                aircraft_data["altitude"] = max(1000, min(40000, aircraft_data["altitude"] + alt_change))
                
            else:
                # Generar nuevo objetivo
                aircraft_data["target"] = {
                    "lat": -34.6037 + random.uniform(-1.0, 1.0),
                    "lon": -58.3816 + random.uniform(-1.0, 1.0)
                }
                print(f"[TWR] {aircraft_id} - Nuevo objetivo: {aircraft_data['target']}")
            
            aircraft_data["last_update"] = time.time()

        async def report_aircraft_position(self, aircraft_id, aircraft_data):
            """Reporta la posición de la aeronave al Environment Agent"""
            if self.agent.environment_jid:
                env_msg = Message(to=self.agent.environment_jid)
                env_msg.body = json.dumps({
                    "type": "aircraft_position",
                    "aircraft_id": aircraft_id,
                    "position": aircraft_data["position"],
                    "altitude": aircraft_data["altitude"],
                    "tower": self.agent.tower_id,
                    "heading": aircraft_data["heading"],
                    "speed": aircraft_data["speed"]
                })
                await self.send(env_msg)

    class AircraftCleanupBehaviour(CyclicBehaviour):
        """Limpia aeronaves inactivas"""
        async def run(self):
            await asyncio.sleep(60)  # Revisar cada minuto
            
            current_time = time.time()
            to_remove = []
            
            for aircraft_id, aircraft_data in self.agent.managed_aircraft.items():
                # Remover aeronaves que no se han actualizado en 5 minutos
                if current_time - aircraft_data["last_update"] > 300:
                    to_remove.append(aircraft_id)
            
            for aircraft_id in to_remove:
                del self.agent.managed_aircraft[aircraft_id]
                print(f"[TWR] Aeronave removida por inactividad: {aircraft_id}")
                
                # Notificar al Environment Agent
                if self.agent.environment_jid:
                    env_msg = Message(to=self.agent.environment_jid)
                    env_msg.body = json.dumps({
                        "type": "aircraft_removed",
                        "aircraft_id": aircraft_id,
                        "tower": self.agent.tower_id
                    })
    class ReceiveFromEnvironment(CyclicBehaviour):
        """Recibe información del Environment Agent"""
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg and self.agent.environment_jid and str(msg.sender) == self.agent.environment_jid:
                try:
                    data = json.loads(msg.body)
                    msg_type = data.get("type")
                    
                    if msg_type == "environment_info":
                        self.agent.environment_info = data
                        print(f"[TWR] Información del entorno recibida: {len(data.get('airports', {}))} aeropuertos")
                        
                except json.JSONDecodeError:
                    print(f"[TWR] Error al decodificar mensaje del entorno: {msg.body}")

    class MonitoringBehaviour(CyclicBehaviour):
        """Monitorea el estado de la torre"""
        async def run(self):
            await asyncio.sleep(15)  # Cada 15 segundos
            active_aircraft = len(self.agent.managed_aircraft)
            print(f"[TWR] Torre {self.agent.tower_id} - Aeronaves gestionadas: {active_aircraft}")
            
            # Mostrar detalles de aeronaves
            for aircraft_id, data in self.agent.managed_aircraft.items():
                print(f"  {aircraft_id}: Lat: {data['position']['lat']:.4f}, "
                      f"Lon: {data['position']['lon']:.4f}, Alt: {data['altitude']} ft")

    async def setup(self):
        print(f"[TWR] Torre {self.tower_id} iniciada como {str(self.jid)} - Aeropuerto: {self.airport}")
        
        # Añadir comportamientos
        self.add_behaviour(self.SetupOpenFireAPI())
        self.add_behaviour(self.RegisterWithEnvironment())
        self.add_behaviour(self.ReceiveFromEnvironment())
        self.add_behaviour(self.AircraftCreationBehaviour())
        self.add_behaviour(self.AircraftSimulationBehaviour())
        self.add_behaviour(self.AircraftCleanupBehaviour())
        self.add_behaviour(self.MonitoringBehaviour())

async def main():
    import sys
    
    # Parámetros de línea de comandos
    tower_id = sys.argv[1] if len(sys.argv) > 1 else "TWR001"
    airport = sys.argv[2] if len(sys.argv) > 2 else "SABE"
    
    xmpp_server = os.getenv("XMPP_SERVER", "localhost")
    
    agent = TowerAgent(f"{tower_id.lower()}@{xmpp_server}", "tower123", 
                      tower_id=tower_id, airport=airport)
    await agent.start()
    
    print(f"[TWR] Torre {tower_id} corriendo...")
    try:
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print(f"[TWR] Deteniendo torre {tower_id}...")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
