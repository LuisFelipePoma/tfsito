from enum import Enum
import json
import time
from typing import Dict, List, Optional
import uuid
import asyncio
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from src.agent.libs.environment import GridPosition, TaxiState, GridNetwork, TaxiInfo
from src.agent.index import cleanup_agent
from src.utils.logger import logger
from src.config import config
from src.services.openfire_api import openfire_api

COORDINATOR_JID = f"coordinator@{config.openfire_container}"


# ==================== TAXI AGENT ====================
class TaxiAgent(Agent):
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

    def _to_serializable_dict(self, obj):
        """Convierte un dataclass a dict serializable por JSON, convirtiendo enums a string."""

        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for k, v in obj.__dict__.items():
                result[k] = self._to_serializable_dict(v)
            return result
        elif isinstance(obj, Enum):
            return obj.value  # Usar .value en lugar de .name para consistencia
        elif isinstance(obj, list):
            return [self._to_serializable_dict(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._to_serializable_dict(v) for k, v in obj.items()}
        else:
            return obj

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
                agent: "TaxiAgent" = self.agent  # type: ignore
                if not agent.info:
                    logger.info(
                        f"Taxi {agent.taxi_id} movement check - info not initialized"
                    )
                    return

                if not agent.grid:
                    logger.info(
                        f"Taxi {agent.taxi_id} movement check - grid not initialized"
                    )
                    return

                logger.info(
                    f"Taxi {agent.taxi_id} movement check - State: {agent.info.state.value}, Position: ({agent.info.position.x}, {agent.info.position.y}), Target: {agent.info.target_position}"
                )

                if agent.info.state == TaxiState.IDLE:
                    # Movimiento aleatorio de patrullaje
                    logger.info(f"Taxi {agent.taxi_id} patrolling...")
                    self._patrol_movement()
                elif agent.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]:
                    # Movimiento hacia objetivo
                    logger.info(
                        f"🚕 Taxi {agent.taxi_id} MOVING towards target: {agent.info.target_position}"
                    )
                    arrived = self._move_towards_target()
                    if arrived:
                        logger.info(f"🎯 Taxi {agent.taxi_id} ARRIVED at target!")
                        await self._handle_arrival()
                elif agent.info.state == TaxiState.ASSIGNED:
                    logger.info(
                        f"Taxi {agent.taxi_id} is assigned but not yet moving - checking state"
                    )
                else:
                    logger.warning(
                        f"Taxi {agent.taxi_id} in unknown state: {agent.info.state}"
                    )
            except Exception as e:
                logger.error(f"Error in MovementBehaviour for taxi {self.agent.taxi_id}: {e}")  # type: ignore
                import traceback

                logger.error(traceback.format_exc())

        async def _handle_arrival(self):
            """Maneja llegada al objetivo desde el comportamiento"""

            agent: "TaxiAgent" = self.agent  # type: ignore
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

            agent: "TaxiAgent" = self.agent  # type: ignore
            msg = Message(to=COORDINATOR_JID)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", event_type)

            payload = {"taxi_id": agent.taxi_id}
            if data:
                payload.update(data)

            msg.body = json.dumps(payload)
            await self.send(msg)

        def _patrol_movement(self):
            agent: "TaxiAgent" = self.agent  # type: ignore
            """Movimiento aleatorio de patrullaje"""

            if not agent.grid or not agent.info:
                logger.info(
                    f"Taxi {agent.taxi_id} cannot patrol: grid={bool(agent.grid)}, info={bool(agent.info)}"
                )
                return

            logger.info(
                f"Taxi {agent.taxi_id} patrolling - current position: ({agent.info.position.x}, {agent.info.position.y}), path index: {agent.path_index}, len path: {len(agent.path)}"
            )

            if not agent.path or agent.path_index >= len(agent.path):
                logger.info(
                    f"Taxi {agent.taxi_id} {agent.path} {agent.path_index} - recalculating patrol path"
                )
                # Elegir nuevo destino aleatorio
                target = agent.grid.get_random_intersection()
                agent.path = agent.grid.get_path(agent.info.position, target)
                agent.path_index = 0

            # Mover al siguiente punto en el path
            if agent.path_index < len(agent.path):
                logger.info(
                    f"Taxi {agent.taxi_id} patrolling to next position: {agent.path[agent.path_index]}"
                )
                agent.info.position = agent.path[agent.path_index]
                agent.path_index += 1

        def _move_towards_target(self):
            """Movimiento hacia objetivo específico"""
            agent: "TaxiAgent" = self.agent  # type: ignore

            if not agent.grid or not agent.info:
                logger.warning(
                    f"Taxi {agent.taxi_id} cannot move: grid={bool(agent.grid)}, info={bool(agent.info)}"
                )
                return False

            if not agent.info.target_position:
                logger.warning(
                    f"Taxi {agent.taxi_id} in state {agent.info.state.value} but no target position"
                )
                return False

            current_pos = agent.info.position
            target_pos = agent.info.target_position

            logger.info(
                f"🚕 Taxi {agent.taxi_id} current pos: ({current_pos.x}, {current_pos.y}), target: ({target_pos.x}, {target_pos.y})"
            )

            # Verificar si ya estamos en el target
            if current_pos == target_pos:
                logger.info(
                    f"🎯 Taxi {agent.taxi_id} already at target ({target_pos.x}, {target_pos.y})"
                )
                return True

            # Calcular o usar path existente
            if not agent.path or agent.path_index >= len(agent.path):
                # Calcular nuevo path hacia el objetivo
                try:
                    logger.info(
                        f"🗺️ Taxi {agent.taxi_id} calculating new path from ({current_pos.x}, {current_pos.y}) to ({target_pos.x}, {target_pos.y})"
                    )
                    agent.path = agent.grid.get_path(current_pos, target_pos)
                    agent.path_index = 0
                    logger.info(
                        f"✅ Taxi {agent.taxi_id} calculated path with {len(agent.path)} steps"
                    )

                    if len(agent.path) == 0:
                        logger.error(f"❌ Taxi {agent.taxi_id} got empty path!")
                        return False

                    if len(agent.path) <= 1:
                        logger.warning(
                            f"⚠️ Taxi {agent.taxi_id} got very short path: {len(agent.path)}"
                        )

                except Exception as e:
                    logger.error(
                        f"💥 Taxi {agent.taxi_id} failed to calculate path: {e}"
                    )
                    import traceback

                    logger.error(traceback.format_exc())
                    return False

            # Mover al siguiente punto en el path
            if agent.path_index < len(agent.path) - 1:
                agent.path_index += 1
                new_pos = agent.path[agent.path_index]
                old_pos = agent.info.position
                agent.info.position = new_pos

                logger.info(
                    f"🚶 Taxi {agent.taxi_id} moved from ({old_pos.x}, {old_pos.y}) to ({new_pos.x}, {new_pos.y}) (step {agent.path_index}/{len(agent.path)-1})"
                )

                # Verificar si llegamos al objetivo
                if agent.info.position == target_pos:
                    logger.info(
                        f"🎯 Taxi {agent.taxi_id} ARRIVED at target ({target_pos.x}, {target_pos.y})"
                    )
                    return True
            else:
                # Ya estamos en el último punto del path
                if current_pos == target_pos:
                    logger.info(
                        f"🎯 Taxi {agent.taxi_id} reached target at end of path ({current_pos.x}, {current_pos.y})"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ Taxi {agent.taxi_id} reached end of path but not at target. Position: ({current_pos.x}, {current_pos.y}), Target: ({target_pos.x}, {target_pos.y})"
                    )
                    # Recalcular path
                    agent.path = []
                    agent.path_index = 0
                    logger.info(
                        f"🔄 Taxi {agent.taxi_id} resetting path for recalculation"
                    )

            return False

    class CommunicationBehaviour(CyclicBehaviour):
        """Maneja comunicación XMPP"""

        async def run(self):
            # Get info of the grid from the coordinator
            agent: "TaxiAgent" = self.agent  # type: ignore
            if not agent.grid:
                #logger.info(f"Sending request for grid info { COORDINATOR_JID}")
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "request") # FIPA
                msg.set_metadata("type", "get_grid_info")
                msg.body = json.dumps({"request": "grid_info"})
                await self.send(msg)

            if not agent.info:
                #logger.info(f"Sending request for taxi info { COORDINATOR_JID}")
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "request") # FIPA
                msg.set_metadata("type", "get_taxi_info")
                msg.body = json.dumps({"taxi_id": agent.taxi_id})
                await self.send(msg)

            # Handle messages
            msg = await self.receive(timeout=1)
            if msg:
                await self._handle_message(msg)

        async def _handle_message(self, msg: Message):
            """Maneja mensajes recibidos"""

            agent: "TaxiAgent" = self.agent  # type: ignore
            if not msg or not msg.body:
                logger.warning(f"Taxi {agent.taxi_id} received empty message")
                return

            try:
                msg_type = msg.get_metadata("type")
                logger.info(f"Taxi {agent.taxi_id} received message type: {msg_type}")

                if msg_type == "assignment":
                    if not agent.info:
                        logger.warning(
                            f"Taxi {agent.taxi_id} received assignment but info not initialized"
                        )
                        return

                    if not agent.grid:
                        logger.warning(
                            f"Taxi {agent.taxi_id} received assignment but grid not initialized"
                        )
                        return

                    # Asignación de pasajero
                    data = json.loads(msg.body)
                    passenger_id = data["passenger_id"]
                    pickup_pos = GridPosition(data["pickup_x"], data["pickup_y"])
                    dropoff_pos = GridPosition(data["dropoff_x"], data["dropoff_y"])

                    # Verificar que el taxi está disponible
                    if agent.info.state != TaxiState.IDLE:
                        logger.warning(
                            f"Taxi {agent.taxi_id} received assignment but is not IDLE (current state: {agent.info.state.value})"
                        )
                        return

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
                        f"🚕 Taxi {agent.taxi_id} ASSIGNED to passenger {passenger_id}"
                    )
                    logger.info(
                        f"   📍 Current position: ({agent.info.position.x}, {agent.info.position.y})"
                    )
                    logger.info(
                        f"   🎯 Pickup target: ({pickup_pos.x}, {pickup_pos.y})"
                    )
                    logger.info(
                        f"   🏁 Dropoff destination: ({dropoff_pos.x}, {dropoff_pos.y})"
                    )
                    logger.info(f"   🔄 State changed to: {agent.info.state.value}")

                    # Calcular distancia y verificar que sea razonable
                    distance = agent.info.position.manhattan_distance(pickup_pos)
                    logger.info(f"   📏 Distance to pickup: {distance} cells")

                    if distance > 20:  # Sanity check
                        logger.warning(f"⚠️ Very long distance to pickup: {distance}")

                    # Enviar confirmación al coordinador
                    confirmation_msg = Message(to=COORDINATOR_JID)
                    confirmation_msg.set_metadata("performative", "inform")
                    confirmation_msg.set_metadata("type", "assignment_accepted")
                    confirmation_data = {
                        "taxi_id": agent.taxi_id,
                        "passenger_id": passenger_id,
                    }
                    confirmation_msg.body = json.dumps(confirmation_data)
                    await self.send(confirmation_msg)

                    logger.info(
                        f"✅ Taxi {agent.taxi_id} sent assignment confirmation to coordinator"
                    )

                    # Verificar inmediatamente después de la asignación
                    logger.info(f"🔍 POST-ASSIGNMENT CHECK:")
                    logger.info(f"   State: {agent.info.state.value}")
                    logger.info(f"   Target: {agent.info.target_position}")
                    logger.info(
                        f"   Assigned passenger: {agent.info.assigned_passenger_id}"
                    )
                    logger.info(
                        f"   Can move? {agent.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]}"
                    )

                if msg_type == "taxi_info":
                    # Actualizar información del taxi
                    data = json.loads(msg.body)
                    logger.info("Received taxi information from coordinator")

                    # Verificar si recibimos datos válidos
                    if not data or not data.get("taxi_id"):
                        logger.warning(
                            f"Taxi {agent.taxi_id} received empty or invalid taxi info, will wait for coordinator to create it"
                        )
                        return

                    try:
                        # Convertir datos JSON a objetos apropiados
                        position_data = data.get("position", {})
                        position = GridPosition(
                            position_data.get("x", 0), position_data.get("y", 0)
                        )

                        target_position = None
                        target_data = data.get("target_position")
                        if target_data:
                            target_position = GridPosition(
                                target_data.get("x", 0), target_data.get("y", 0)
                            )

                        # Convertir estado - manejar tanto strings como valores de enum
                        state_value = data["state"]
                        if isinstance(state_value, str):
                            # Convertir de mayúsculas a minúsculas para que coincida con enum values
                            state = TaxiState(state_value.lower())
                        else:
                            state = TaxiState.IDLE  # Default fallback

                        # Crear TaxiInfo con los datos recibidos
                        agent.info = TaxiInfo(
                            taxi_id=data["taxi_id"],
                            position=position,
                            target_position=target_position,
                            state=state,
                            capacity=data["capacity"],
                            current_passengers=data["current_passengers"],
                            assigned_passenger_id=data.get("assigned_passenger_id"),
                            speed=data.get("speed", 1.0),
                        )

                        logger.info(
                            f"Taxi {agent.taxi_id} info updated: position=({position.x}, {position.y}), state={agent.info.state.value}"
                        )

                    except (KeyError, ValueError, TypeError) as e:
                        logger.error(
                            f"Error processing taxi info for {agent.taxi_id}: {e}"
                        )
                        logger.error(f"Data received: {data}")

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
                        logger.info(
                            f"Taxi {agent.taxi_id} initialized at position ({initial_position.x}, {initial_position.y})"
                        )

                    logger.info(
                        f"Taxi {agent.taxi_id} grid updated: {agent.grid.width}x{agent.grid.height}"
                    )

            except Exception as e:
                logger.error(f"Error handling message in taxi {agent.taxi_id}: {e}")
                logger.error(f"Message body: {msg.body}")
                logger.error(f"Message metadata: {msg.metadata}")

    class StatusReportBehaviour(PeriodicBehaviour):
        """Reporta estado al coordinador"""

        async def run(self):
            agent: "TaxiAgent" = self.agent  # type: ignore
            if agent.info and agent.grid:
                msg = Message(to=COORDINATOR_JID)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("type", "status_report")
                # Usar función serializadora para enums
                serializable_info = agent._to_serializable_dict(agent.info)
                msg.body = json.dumps(serializable_info)
                await self.send(msg)


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
    """Spawn agents for this host"""

    logger.info(f"Spawning {n_agents} agents for host {config.openfire_host}")

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
    # return n_agents
