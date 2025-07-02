import asyncio
import json
import time
import random
import math
import os
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

class AircraftAgent(Agent):
    def __init__(self, jid, password, aircraft_id="AC001", tower_jid=None, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.aircraft_id = aircraft_id
        self.tower_jid = tower_jid
        
        # Posición inicial aleatoria en el área de Buenos Aires
        self.position = {
            "lat": -34.6037 + random.uniform(-0.5, 0.5),
            "lon": -58.3816 + random.uniform(-0.5, 0.5)
        }
        self.altitude = random.randint(1000, 35000)
        self.heading = random.randint(0, 360)  # Rumbo en grados
        self.speed = random.randint(200, 500)  # Velocidad en nudos
        
        # Destino objetivo (para simulación de movimiento)
        self.target = {
            "lat": -34.6037 + random.uniform(-1.0, 1.0),
            "lon": -58.3816 + random.uniform(-1.0, 1.0)
        }

    class FlightSimulation(CyclicBehaviour):
        """Simula el vuelo de la aeronave"""
        async def run(self):
            await asyncio.sleep(2)  # Actualizar cada 2 segundos
            
            # Calcular movimiento hacia el objetivo
            lat_diff = self.agent.target["lat"] - self.agent.position["lat"]
            lon_diff = self.agent.target["lon"] - self.agent.position["lon"]
            distance = math.sqrt(lat_diff**2 + lon_diff**2)
            
            if distance > 0.001:  # Si no hemos llegado
                # Mover hacia el objetivo
                speed_factor = 0.001  # Factor de velocidad
                self.agent.position["lat"] += lat_diff * speed_factor
                self.agent.position["lon"] += lon_diff * speed_factor
                
                # Pequeña variación aleatoria para simular turbulencia
                self.agent.position["lat"] += random.uniform(-0.0001, 0.0001)
                self.agent.position["lon"] += random.uniform(-0.0001, 0.0001)
                
                # Pequeña variación en altitud
                alt_change = random.randint(-100, 100)
                self.agent.altitude = max(1000, min(40000, self.agent.altitude + alt_change))
                
            else:
                # Generar nuevo objetivo
                self.agent.target = {
                    "lat": -34.6037 + random.uniform(-1.0, 1.0),
                    "lon": -58.3816 + random.uniform(-1.0, 1.0)
                }
                print(f"[AC] {self.agent.aircraft_id} - Nuevo objetivo: {self.agent.target}")

    class ReportPosition(CyclicBehaviour):
        """Reporta posición a la torre de control"""
        async def run(self):
            await asyncio.sleep(3)  # Reportar cada 3 segundos
            
            if self.agent.tower_jid:
                position_msg = Message(to=self.agent.tower_jid)
                position_msg.body = json.dumps({
                    "aircraft_id": self.agent.aircraft_id,
                    "position": self.agent.position,
                    "altitude": self.agent.altitude,
                    "heading": self.agent.heading,
                    "speed": self.agent.speed,
                    "timestamp": time.time()
                })
                
                await self.send(position_msg)
                print(f"[AC] {self.agent.aircraft_id} - Posición reportada: "
                      f"Lat: {self.agent.position['lat']:.4f}, "
                      f"Lon: {self.agent.position['lon']:.4f}, "
                      f"Alt: {self.agent.altitude} ft")

    class ReceiveInstructions(CyclicBehaviour):
        """Recibe instrucciones de la torre de control"""
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                try:
                    data = json.loads(msg.body)
                    instruction_type = data.get("type")
                    
                    if instruction_type == "altitude_change":
                        new_altitude = data.get("altitude")
                        print(f"[AC] {self.agent.aircraft_id} - Instrucción: cambiar altitud a {new_altitude} ft")
                        self.agent.altitude = new_altitude
                        
                    elif instruction_type == "heading_change":
                        new_heading = data.get("heading")
                        print(f"[AC] {self.agent.aircraft_id} - Instrucción: cambiar rumbo a {new_heading}°")
                        self.agent.heading = new_heading
                        
                    elif instruction_type == "speed_change":
                        new_speed = data.get("speed")
                        print(f"[AC] {self.agent.aircraft_id} - Instrucción: cambiar velocidad a {new_speed} nudos")
                        self.agent.speed = new_speed
                        
                except json.JSONDecodeError:
                    print(f"[AC] {self.agent.aircraft_id} - Error al decodificar instrucción: {msg.body}")

    async def setup(self):
        print(f"[AC] Aeronave {self.aircraft_id} iniciada como {str(self.jid)}")
        print(f"[AC] Posición inicial: Lat: {self.position['lat']:.4f}, "
              f"Lon: {self.position['lon']:.4f}, Alt: {self.altitude} ft")
        
        if self.tower_jid:
            print(f"[AC] Comunicándose con torre: {self.tower_jid}")
        
        # Añadir comportamientos
        self.add_behaviour(self.FlightSimulation())
        self.add_behaviour(self.ReportPosition())
        self.add_behaviour(self.ReceiveInstructions())

async def main():
    import sys
    
    # Parámetros de línea de comandos
    aircraft_id = sys.argv[1] if len(sys.argv) > 1 else f"AC{random.randint(100, 999)}"
    tower_id = sys.argv[2] if len(sys.argv) > 2 else "twr001"
    
    xmpp_server = os.getenv("XMPP_SERVER", "localhost")
    tower_jid = f"{tower_id}@{xmpp_server}"
    
    agent = AircraftAgent(f"{aircraft_id.lower()}@{xmpp_server}", "aircraft123", 
                         aircraft_id=aircraft_id, tower_jid=tower_jid)
    await agent.start()
    
    print(f"[AC] Aeronave {aircraft_id} volando...")
    try:
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print(f"[AC] Aterrizando aeronave {aircraft_id}...")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
