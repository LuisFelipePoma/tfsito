import asyncio
import json
import websockets
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

class TowerAgent(Agent):
    def __init__(self, jid, password, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.aircraft_buffer = {}  # {aircraft_id: {position, altitude}}

    class ReceiveFromAircrafts(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                data = json.loads(msg.body)
                aircraft_id = data.get("aircraft_id")
                self.agent.aircraft_buffer[aircraft_id] = {
                    "position": data.get("position"),
                    "altitude": data.get("altitude")
                }
                print(f"[TWR] Posición recibida de {aircraft_id}: {data}")

    class SendToEnvironment(CyclicBehaviour):
        async def run(self):
            await asyncio.sleep(1)  # Cada segundo
            try:
                if self.agent.aircraft_buffer:
                    async with websockets.connect("ws://localhost:8765") as websocket:
                        await websocket.send(json.dumps(self.agent.aircraft_buffer))
                        print(f"[TWR] Enviado al entorno: {self.agent.aircraft_buffer}")
            except Exception as e:
                print(f"[TWR] Error al enviar al entorno: {e}")

    async def setup(self):
        print(f"[TWR] Torre iniciada como {str(self.jid)}")
        self.add_behaviour(self.ReceiveFromAircrafts())
        self.add_behaviour(self.SendToEnvironment())
