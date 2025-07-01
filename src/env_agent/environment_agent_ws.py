import asyncio
import websockets
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

aircraft_positions = {}

class EnvironmentAgent(Agent):
    class DummyBehaviour(CyclicBehaviour):
        async def run(self):
            await asyncio.sleep(5)  # solo para mantener SPADE vivo

    async def setup(self):
        print(f"[ENV] Agente iniciado como {str(self.jid)}")
        self.add_behaviour(self.DummyBehaviour())
        asyncio.create_task(self.websocket_server())

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
