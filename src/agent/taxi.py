from enum import Enum
import json
import time
from typing import Dict, List, Optional
import uuid
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from spade.template import Template
from src.agent.libs.environment import GridPosition, TaxiState, GridNetwork, TaxiInfo
from src.utils.logger import logger
from src.config import config
from src.agent.index import cleanup_agent
import asyncio
from src.services.openfire_api import openfire_api
from src.config import config

COORDINATOR_JID = f"coordinator@{config.openfire_container}"

# ==================== TAXI AGENT ====================
class TaxiAgent(Agent):
    def _to_serializable_dict(self, obj):
        """Convierte un dataclass a dict serializable por JSON, convirtiendo enums a string."""
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for k, v in obj.__dict__.items():
                result[k] = self._to_serializable_dict(v)
            return result
        elif isinstance(obj, Enum):
            return obj.name
        elif isinstance(obj, list):
            return [self._to_serializable_dict(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._to_serializable_dict(v) for k, v in obj.items()}
        else:
            return obj

    """Agente taxi que se comunica vía SPADE/OpenFire"""

  
    def __init__(
        self,
        jid: str,
        password: str,
        taxi_id: str,
    ):
        super().__init__(jid, password)
        self.taxi_id = taxi_id
        self.grid: Optional[GridNetwork] = None
        self.info: Optional[TaxiInfo] = None
        self.last_update = time.time()
        self.path: List[GridPosition] = []
        self.path_index = 0
        self.dropoff_position: Optional[GridPosition] = (
            None  # Para guardar destino del pasajero
        )

        logger.info(f"Taxi agent {taxi_id} created")

    async def setup(self):
        """Configuración inicial del agente"""
        logger.info(f"Setting up taxi agent {self.taxi_id}")

        # Comportamiento de movimiento - más frecuente para respuesta rápida
        movement_behaviour = self.MovementBehaviour(
            period=config.movement_update_interval
        )
        self.add_behaviour(movement_behaviour)

        # Comportamiento de comunicación
        comm_behaviour = self.CommunicationBehaviour()
        self.add_behaviour(comm_behaviour)

        # Comportamiento de reporte de estado - más frecuente para sincronización
        status_behaviour = self.StatusReportBehaviour(
            period=config.status_report_interval
        )
        self.add_behaviour(status_behaviour)

    class MovementBehaviour(PeriodicBehaviour):
        """Maneja el movimiento del taxi"""

        async def run(self):
            try:
                agent: 'TaxiAgent' = self.agent  # type: ignore
                if agent.info and agent.grid:
                    if agent.info.state == TaxiState.IDLE:
                        # Movimiento aleatorio de patrullaje
                        agent._patrol_movement()
                    elif agent.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]:
                        # Movimiento hacia objetivo
                        arrived = agent._move_towards_target()
                        if arrived:
                            await self._handle_arrival()
            except Exception as e:
                logger.error(
                    f"Error in MovementBehaviour for taxi {self.agent.taxi_id}: {e}"  # type: ignore
                )
                # Don't re-raise the exception to prevent behavior termination

        async def _handle_arrival(self):
            """Maneja llegada al objetivo desde el comportamiento"""
            agent: 'TaxiAgent' = self.agent  # type: ignore
            if not agent.info:
                return
                
            if agent.info.state == TaxiState.PICKUP:
                # Llegamos a recoger pasajero
                agent.info.state = TaxiState.DROPOFF
                agent.info.current_passengers += 1

                # Cambiar target al destino del pasajero
                if agent.dropoff_position:
                    agent.info.target_position = agent.dropoff_position
                    logger.info(
                        f"Taxi {agent.taxi_id} picked up passenger {agent.info.assigned_passenger_id}, heading to ({agent.dropoff_position.x}, {agent.dropoff_position.y})"
                    )
                else:
                    logger.error(
                        f"Taxi {agent.taxi_id} picked up passenger but no dropoff position saved!"
                    )

                # Resetear path para forzar recálculo hacia el nuevo destino
                agent.path = []
                agent.path_index = 0

                # Notificar al coordinador desde el comportamiento
                await self._notify_coordinator("passenger_picked_up")

            elif agent.info.state == TaxiState.DROPOFF:
                # Llegamos a entregar pasajero
                agent.info.state = TaxiState.IDLE
                agent.info.current_passengers = 0
                agent.info.target_position = None
                passenger_id = agent.info.assigned_passenger_id
                agent.info.assigned_passenger_id = None
                agent.dropoff_position = None  # Limpiar posición de destino

                logger.info(f"Taxi {agent.taxi_id} delivered passenger {passenger_id}")

                # Notificar al coordinador desde el comportamiento
                await self._notify_coordinator(
                    "passenger_delivered", {"passenger_id": passenger_id}
                )

        async def _notify_coordinator(
            self, event_type: str, data: Optional[Dict] = None
        ):
            """Notifica eventos al coordinador desde el comportamiento"""
            agent: 'TaxiAgent' = self.agent  # type: ignore
            # coordinator_jid = f"coordinator@{config.openfire_domain}"
            msg = Message(to=COORDINATOR_JID)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", event_type)

            payload = {"taxi_id": agent.taxi_id}
            if data:
                payload.update(data)

            msg.body = json.dumps(payload)
            await self.send(msg)

    class CommunicationBehaviour(CyclicBehaviour):
        """Maneja comunicación XMPP"""

        async def run(self):
            # Get info of the grid from the coordinator
            agent: 'TaxiAgent' = self.agent  # type: ignore
            if not agent.grid:
                logger.info(f"Sending request for grid info { COORDINATOR_JID}")
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "request")
                msg.set_metadata("type", "get_grid_info")
                msg.body = json.dumps({"request": "grid_info"})
                await self.send(msg)
            
            if not agent.info:
                logger.info(f"Sending request for taxi info { COORDINATOR_JID}")
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "request")
                msg.set_metadata("type", "get_taxi_info")
                msg.body = json.dumps({"taxi_id": agent.taxi_id})
                await self.send(msg)
                
            # handle messages
            msg = await self.receive(timeout=1)
            if msg:
                await self._handle_message(msg)

        async def _handle_message(self, msg: Message):
            """Maneja mensajes recibidos"""
            agent: 'TaxiAgent' = self.agent  # type: ignore
            if not msg or not msg.body:
                logger.warning(f"Taxi {agent.taxi_id} received empty message")
                return

            try:
                msg_type = msg.get_metadata("type")
                logger.info(
                    f"Taxi {agent.taxi_id} received message type: {msg_type}"
                )

                if msg_type == "assignment":
                    if not agent.info:
                        logger.warning(f"Taxi {agent.taxi_id} received assignment but info not initialized")
                        return
                        
                    # Asignación de pasajero
                    data = json.loads(msg.body)
                    passenger_id = data["passenger_id"]
                    pickup_pos = GridPosition(data["pickup_x"], data["pickup_y"])
                    dropoff_pos = GridPosition(data["dropoff_x"], data["dropoff_y"])

                    # Actualizar estado del taxi
                    agent.info.assigned_passenger_id = passenger_id
                    agent.info.target_position = pickup_pos
                    agent.info.state = TaxiState.PICKUP

                    # Guardar posición de destino para después del pickup
                    agent.dropoff_position = dropoff_pos

                    # Resetear path para forzar recálculo
                    agent.path = []
                    agent.path_index = 0

                    logger.info(
                        f"Taxi {agent.taxi_id} assigned to passenger {passenger_id} at ({pickup_pos.x}, {pickup_pos.y}) -> ({dropoff_pos.x}, {dropoff_pos.y})"
                    )
                    
                if msg_type == "taxi_info":
                    # Actualizar información del taxi
                    data = json.loads(msg.body)
                    logger.info("Received taxi information from coordinator")
                    agent.info = TaxiInfo(**data)
                        
                elif msg_type == "grid_info":
                    # Actualizar información de la cuadrícula
                    data = json.loads(msg.body)
                    logger.info("Received grid information from coordinator")
                    agent.grid = GridNetwork.from_dict(data)
                    
                    # Inicializar info del taxi con posición inicial
                    if not agent.info:
                        initial_position = agent.grid.get_random_intersection()
                        agent.info = TaxiInfo(
                            taxi_id=agent.taxi_id,
                            position=initial_position,
                            target_position=None,
                            state=TaxiState.IDLE,
                            capacity=4,
                            current_passengers=0,
                            assigned_passenger_id=None,
                        )
                        logger.info(f"Taxi {agent.taxi_id} initialized at position ({initial_position.x}, {initial_position.y})")
                    
                    logger.info(f"Taxi {agent.taxi_id} grid updated: {agent.grid.width}x{agent.grid.height}")
                    
            except Exception as e:
                logger.error(
                    f"Error handling message in taxi {agent.taxi_id}: {e}"
                )
                logger.error(f"Message body: {msg.body}")
                logger.error(f"Message metadata: {msg.metadata}")

    class StatusReportBehaviour(PeriodicBehaviour):
        """Reporta estado al coordinador"""

        async def run(self):
            agent: 'TaxiAgent' = self.agent  # type: ignore
            if agent.info and agent.grid:
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("type", "status_report")
                # Usar función serializadora para enums
                serializable_info = agent._to_serializable_dict(agent.info)
                msg.body = json.dumps(serializable_info)
                await self.send(msg)

    def _patrol_movement(self):
        """Movimiento aleatorio de patrullaje"""
        if not self.grid or not self.info:
            return
            
        if not self.path or self.path_index >= len(self.path):
            # Elegir nuevo destino aleatorio
            target = self.grid.get_random_intersection()
            self.path = self.grid.get_path(self.info.position, target)
            self.path_index = 0

        # Mover al siguiente punto en el path
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.info.position = self.path[self.path_index]

    def _move_towards_target(self):
        """Movimiento hacia objetivo específico"""
        if not self.grid or not self.info:
            return False
            
        if not self.info.target_position:
            logger.warning(
                f"Taxi {self.taxi_id} in state {self.info.state.value} but no target position"
            )
            return False

        # Verificar si ya estamos en el target
        if self.info.position == self.info.target_position:
            logger.info(
                f"Taxi {self.taxi_id} already at target ({self.info.target_position.x}, {self.info.target_position.y})"
            )
            return True

        if not self.path or self.path_index >= len(self.path):
            # Calcular nuevo path hacia el objetivo
            self.path = self.grid.get_path(
                self.info.position, self.info.target_position
            )
            self.path_index = 0
            logger.info(
                f"Taxi {self.taxi_id} calculated new path to ({self.info.target_position.x}, {self.info.target_position.y}), path length: {len(self.path)}"
            )

        # Mover al siguiente punto en el path
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            new_pos = self.path[self.path_index]
            logger.debug(
                f"Taxi {self.taxi_id} moving from ({self.info.position.x}, {self.info.position.y}) to ({new_pos.x}, {new_pos.y})"
            )
            self.info.position = new_pos

            # Verificar si llegamos al objetivo
            if self.info.position == self.info.target_position:
                logger.info(
                    f"Taxi {self.taxi_id} arrived at target ({self.info.target_position.x}, {self.info.target_position.y})"
                )
                return True
        else:
            # Ya estamos en el último punto del path
            logger.info(
                f"Taxi {self.taxi_id} reached end of path at ({self.info.position.x}, {self.info.position.y})"
            )
            return True

        return False


async def create_agent_taxi(agent_id: str):
    """Create and initialize an ideological agent"""

    try:
        # Create user in Openfire if not exists
        password = f"agent_taxi_{agent_id}_pass"
        jid = f"{agent_id}@{config.openfire_domain}"

        if not openfire_api.create_user(agent_id, password):
            logger.error(f"Failed to create Openfire user for agent {agent_id}")
            return None

        # Create and start the agent
        agent = TaxiAgent(jid, password, agent_id)

        # Start the agent
        await agent.start(auto_register=True)

        await asyncio.sleep(0.5)

        if agent.is_alive():
            logger.info(f"Successfully created agent {agent_id}")
            return agent
        else:
            logger.error(f"Agent {agent_id} failed to start properly")
            await cleanup_agent(agent)
            return None

    except Exception as e:
        logger.error(f"Exception creating agent {agent_id}: {e}")
        return None


## LAUNCHER
async def launch_agent_taxi(n_agents: int):
    """Spawn ideological agents for this host"""
    logger.info(
        f"Spawning {n_agents} ideological agents for host {config.openfire_host}"
    )

    agents = []

    # Create agents
    agent_count = 0
    for i in range(n_agents):
        agent_id = f"{config.host_name}_agent_taxi_{i}_{uuid.uuid4().hex[:8]}"

        agent = await create_agent_taxi(agent_id)
        if agent:
            agents.append(agent)
            agent_count += 1

        # Small delay between creations
        await asyncio.sleep(0.2)

    logger.info(f"Spawned {n_agents} agents successfully")
    while True:
        await asyncio.sleep(0.5)
    return n_agents
