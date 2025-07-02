import asyncio
import websockets
import json
import time
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template
from aiohttp import web
from aiohttp.web import Application
import aiohttp_cors

# Datos del entorno global
aircraft_positions = {}
towers_info = {}
airports = {
    "SABE": {"name": "Buenos Aires", "position": {"lat": -34.8222, "lon": -58.5358}, "runways": ["07/25", "13/31"]},
    "SAEZ": {"name": "Ezeiza", "position": {"lat": -34.8161, "lon": -58.5356}, "runways": ["11/29", "17/35"]},
    "SADP": {"name": "La Plata", "position": {"lat": -34.9722, "lon": -57.8944}, "runways": ["06/24"]}
}
airspace_limits = {
    "min_lat": -35.5, "max_lat": -34.0,
    "min_lon": -59.0, "max_lon": -57.5,
    "min_alt": 0, "max_alt": 40000
}

class EnvironmentAgent(Agent):
    class XMPPCommunicationBehaviour(CyclicBehaviour):
        """Comportamiento para comunicación XMPP con torres y aviones"""
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                try:
                    data = json.loads(msg.body)
                    msg_type = data.get("type")
                    
                    if msg_type == "tower_registration":
                        # Registro de torre
                        tower_id = data.get("tower_id")
                        towers_info[tower_id] = {
                            "jid": str(msg.sender),
                            "airport": data.get("airport"),
                            "status": "active",
                            "last_update": time.time()
                        }
                        print(f"[ENV] Torre registrada: {tower_id}")
                        
                        # Responder con información del entorno
                        response = Message(to=str(msg.sender))
                        response.body = json.dumps({
                            "type": "environment_info",
                            "airports": airports,
                            "airspace_limits": airspace_limits
                        })
                        await self.send(response)
                        
                    elif msg_type == "aircraft_position":
                        # Actualización de posición de aeronave
                        aircraft_id = data.get("aircraft_id")
                        aircraft_positions[aircraft_id] = {
                            "position": data.get("position"),
                            "altitude": data.get("altitude"),
                            "tower": data.get("tower"),
                            "heading": data.get("heading", 0),
                            "speed": data.get("speed", 0),
                            "jid": data.get("jid", ""),
                            "timestamp": time.time()
                        }
                        print(f"[ENV] Posición actualizada - {aircraft_id}: Lat: {data.get('position', {}).get('lat', 'N/A')}, Lon: {data.get('position', {}).get('lon', 'N/A')}")
                        
                    elif msg_type == "aircraft_created":
                        # Nueva aeronave creada por torre
                        aircraft_id = data.get("aircraft_id")
                        aircraft_positions[aircraft_id] = {
                            "position": data.get("position"),
                            "altitude": data.get("altitude"),
                            "tower": data.get("tower"),
                            "heading": data.get("heading", 0),
                            "speed": data.get("speed", 0),
                            "jid": data.get("jid", ""),
                            "timestamp": time.time(),
                            "status": "active"
                        }
                        print(f"[ENV] Nueva aeronave registrada: {aircraft_id} por torre {data.get('tower')}")
                        
                    elif msg_type == "aircraft_removed":
                        # Aeronave removida por torre
                        aircraft_id = data.get("aircraft_id")
                        if aircraft_id in aircraft_positions:
                            del aircraft_positions[aircraft_id]
                            print(f"[ENV] Aeronave removida: {aircraft_id}")
                        
                    elif msg_type == "query_aircraft":
                        # Consulta de información de aeronaves
                        response = Message(to=str(msg.sender))
                        response.body = json.dumps({
                            "type": "aircraft_data",
                            "aircraft": aircraft_positions
                        })
                        await self.send(response)
                        
                except json.JSONDecodeError:
                    print(f"[ENV] Error al decodificar mensaje: {msg.body}")

    class WebSocketBehaviour(CyclicBehaviour):
        """Mantiene el servidor WebSocket para compatibilidad"""
        async def run(self):
            await asyncio.sleep(10)  # Verificar cada 10 segundos

    async def setup(self):
        print(f"[ENV] Environment Agent iniciado como {str(self.jid)}")
        self.add_behaviour(self.XMPPCommunicationBehaviour())
        self.add_behaviour(self.WebSocketBehaviour())
        
        # Iniciar servidor web para interfaz gráfica
        asyncio.create_task(self.start_web_interface())
        # Mantener WebSocket para compatibilidad
        asyncio.create_task(self.websocket_server())

    async def start_web_interface(self):
        """Inicia la interfaz web para monitoreo"""
        app = Application()
        
        # Configurar CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # Rutas de la API
        app.router.add_get('/api/aircraft', self.get_aircraft_data)
        app.router.add_get('/api/towers', self.get_towers_data)
        app.router.add_get('/api/airports', self.get_airports_data)
        app.router.add_static('/', path='web/', name='static')
        
        # Aplicar CORS a todas las rutas
        for route in list(app.router.routes()):
            cors.add(route)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("[ENV] Interfaz web iniciada en http://0.0.0.0:8080")

    async def get_aircraft_data(self, request):
        """API endpoint para datos de aeronaves"""
        return web.json_response(aircraft_positions)

    async def get_towers_data(self, request):
        """API endpoint para datos de torres"""
        return web.json_response(towers_info)

    async def get_airports_data(self, request):
        """API endpoint para datos de aeropuertos"""
        return web.json_response(airports)

    async def websocket_server(self):
        async def handler(websocket, _):
            print("[ENV] Cliente WebSocket conectado.")
            try:
                async for message in websocket:
                    data = json.loads(message)
                    for av_id, pos in data.items():
                        aircraft_positions[av_id] = pos
                    print(f"[ENV] Actualización recibida: {data}")
            except websockets.ConnectionClosed:
                print("[ENV] WebSocket desconectado.")

        await websockets.serve(handler, "0.0.0.0", 8765)

async def main():
    import os
    xmpp_server = os.getenv("XMPP_SERVER", "localhost")
    
    agent = EnvironmentAgent(f"environment@{xmpp_server}", "environment123")
    await agent.start()
    
    print("[ENV] Agente corriendo...")
    try:
        # Mantener el agente corriendo
        while agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("[ENV] Deteniendo agente...")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
