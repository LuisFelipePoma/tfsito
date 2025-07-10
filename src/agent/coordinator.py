import asyncio
import json
import random
import traceback
from typing import Dict
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from src.agent.libs.constraint import ConstraintSolver
from src.agent.libs.environment import (
    GridNetwork,
    GridPosition,
    PassengerInfo,
    PassengerState,
    TaxiInfo,
    TaxiState,
)
from src.taxi_dispatch_gui import launch_taxi_gui
from src.utils.logger import logger
from src.config import config


# ==================== COORDINATOR AGENT ====================
class CoordinatorAgent(Agent):
    """Agente coordinador que maneja asignaciones"""

    def __init__(self, jid: str, password: str, grid: GridNetwork):
        super().__init__(jid, password)
        self.grid = grid
        self.taxis: Dict[str, TaxiInfo] = {}
        self.passengers: Dict[str, PassengerInfo] = {}
        self.solver = ConstraintSolver()
        self.passenger_counter = 0

        logger.info("Coordinator agent created")

    async def setup(self):
        """Configuración inicial del coordinador"""

        logger.info("Setting up coordinator agent")

        # Comportamiento de asignación - más frecuente para respuesta rápida
        assignment_behaviour = self.AssignmentBehaviour(
            period=config.assignment_interval
        )
        self.add_behaviour(assignment_behaviour)

        # Comportamiento de comunicación
        comm_behaviour = self.CommunicationBehaviour()
        self.add_behaviour(comm_behaviour)

        # Comportamiento de logica de pasajeros
        passengers_behaviour = self.PassengersBehaviour()
        self.add_behaviour(passengers_behaviour)

    class AssignmentBehaviour(PeriodicBehaviour):
        """Maneja las asignaciones usando constraint programming"""

        async def run(self):
            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            if not coordinator.taxis or not coordinator.passengers:
                return

            # Obtener listas actuales
            taxi_list = list(coordinator.taxis.values())
            passenger_list = [
                p
                for p in coordinator.passengers.values()
                if p.state == PassengerState.WAITING
            ]

            if not passenger_list:
                return

            # Resolver asignaciones
            assignments = coordinator.solver.solve_assignment(taxi_list, passenger_list)

            logger.info(f"Assignments found: {assignments}")

            # Enviar asignaciones a taxis
            for taxi_id, passenger_id in assignments.items():
                await self._send_assignment_message(taxi_id, passenger_id)

        async def _send_assignment_message(self, taxi_id: str, passenger_id: str):
            """Envía mensaje de asignación a un taxi (desde el comportamiento)"""

            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            if passenger_id not in coordinator.passengers:
                logger.warning(f"Passenger {passenger_id} not found for assignment")
                return

            passenger = coordinator.passengers[passenger_id]

            # Construir JID del taxi correctamente
            taxi_jid = f"{taxi_id}@{config.openfire_container}"

            msg = Message(to=taxi_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", "assignment")

            data = {
                "passenger_id": passenger_id,
                "pickup_x": passenger.pickup_position.x,
                "pickup_y": passenger.pickup_position.y,
                "dropoff_x": passenger.dropoff_position.x,
                "dropoff_y": passenger.dropoff_position.y,
            }
            msg.body = json.dumps(data)

            await self.send(msg)

            # Marcar asignación pendiente
            passenger.assigned_taxi_id = taxi_id

            logger.info(
                f"Sent assignment: {taxi_id} -> {passenger_id} at ({passenger.pickup_position.x}, {passenger.pickup_position.y}) -> ({passenger.dropoff_position.x}, {passenger.dropoff_position.y})"
            )

    class CommunicationBehaviour(CyclicBehaviour):
        """Maneja comunicación con taxis"""

        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                performative = msg.get_metadata("performative")
                if performative == "inform":
                    await self._handle_message(msg)
                elif performative == "request":
                    await self._handle_request(msg)

        async def _handle_request(self, msg: Message):
            """Maneja mensajes de request"""
            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            if not msg:
                return
            try:
                msg_type = msg.get_metadata("type")
                logger.info(f"Coordinator received request: {msg_type}")

                if msg_type == "get_grid_info":
                    # Responder con información de la cuadrícula
                    logger.info("Sending grid information to taxi")
                    response = Message(to=msg.sender)
                    response.set_metadata("performative", "inform")
                    response.set_metadata("type", "grid_info")
                    
                    # Convertir grid a dict manualmente
                    grid_dict = {
                        "width": coordinator.grid.width,
                        "height": coordinator.grid.height,
                        "intersections": [
                            {"x": pos.x, "y": pos.y} 
                            for pos in coordinator.grid.intersections
                        ]
                    }
                    response.body = json.dumps(grid_dict)
                    await self.send(response)

                if msg_type == "get_taxi_info":
                    # Responder con información del taxi
                    logger.info("Sending taxi information to client")
                    response = Message(to=msg.sender)
                    response.set_metadata("performative", "inform")
                    response.set_metadata("type", "taxi_info")
                    
                    # Obtener información del taxi de forma segura
                    taxi_id = str(msg.body) if msg.body else ""
                    taxi_info = coordinator.taxis.get(taxi_id)
                    
                    if taxi_info:
                        # Si el taxi existe, convertir a dict manualmente
                        taxi_dict = {
                            "taxi_id": taxi_info.taxi_id,
                            "position": {
                                "x": taxi_info.position.x,
                                "y": taxi_info.position.y
                            },
                            "target_position": {
                                "x": taxi_info.target_position.x,
                                "y": taxi_info.target_position.y
                            } if taxi_info.target_position else None,
                            "state": taxi_info.state.name,
                            "capacity": taxi_info.capacity,
                            "current_passengers": taxi_info.current_passengers,
                            "assigned_passenger_id": taxi_info.assigned_passenger_id,
                            "speed": taxi_info.speed
                        }
                        response.body = json.dumps(taxi_dict)
                    else:
                        # Si el taxi no existe, devolver objeto vacío
                        logger.warning(f"Taxi {taxi_id} not found")
                        response.body = json.dumps({})
                    
                    await self.send(response)

            except Exception as e:
                logger.error(f"Error handling request in coordinator: {e}")
                logger.error(f"Message body: {msg.body}")
                logger.error(f"Message metadata: {msg.metadata}")

        async def _handle_message(self, msg: Message):
            """Maneja mensajes de taxis"""
            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            if not msg or not msg.body:
                logger.warning("Coordinator received empty message")
                return

            try:
                msg_type = msg.get_metadata("type")

                if msg_type == "status_report":
                    # Actualizar estado de taxi
                    data = json.loads(msg.body)

                    # Convertir datos JSON a objetos apropiados
                    position_data = data.get("position", {})
                    if isinstance(position_data, dict):
                        position = GridPosition(
                            position_data.get("x", 0), position_data.get("y", 0)
                        )
                    else:
                        position = GridPosition(0, 0)

                    target_position = None
                    target_data = data.get("target_position")
                    if target_data and isinstance(target_data, dict):
                        target_position = GridPosition(
                            target_data.get("x", 0), target_data.get("y", 0)
                        )

                    # Convertir estado de string a enum
                    state_str = data.get("state", "IDLE")
                    if isinstance(state_str, str):
                        state = TaxiState(state_str.lower())
                    else:
                        state = TaxiState.IDLE

                    # Crear objeto TaxiInfo
                    taxi_info = TaxiInfo(
                        taxi_id=data.get("taxi_id", ""),
                        position=position,
                        target_position=target_position,
                        state=state,
                        capacity=data.get("capacity", 4),
                        current_passengers=data.get("current_passengers", 0),
                        assigned_passenger_id=data.get("assigned_passenger_id"),
                        speed=data.get("speed", 1.0),
                    )

                    coordinator.taxis[taxi_info.taxi_id] = taxi_info

                elif msg_type == "passenger_picked_up":
                    # Taxi notifica que recogió pasajero
                    data = json.loads(msg.body)
                    taxi_id = data.get("taxi_id")
                    if taxi_id:
                        # Buscar pasajero asignado a este taxi
                        for p in coordinator.passengers.values():
                            if (
                                p.assigned_taxi_id == taxi_id
                                and p.state == PassengerState.WAITING
                            ):
                                p.state = PassengerState.PICKED_UP
                                logger.info(
                                    f"Passenger {p.passenger_id} picked up by taxi {taxi_id}"
                                )
                                break

                elif msg_type == "passenger_delivered":
                    # Pasajero entregado, crear nuevo pasajero
                    data = json.loads(msg.body)
                    passenger_id = data.get("passenger_id")
                    if passenger_id and passenger_id in coordinator.passengers:
                        coordinator.passengers[passenger_id].state = (
                            PassengerState.DELIVERED
                        )
                        del coordinator.passengers[passenger_id]
                        logger.info(f"Passenger {passenger_id} delivered successfully")

            except Exception as e:
                logger.error(f"Error handling message in coordinator: {e}")
                logger.error(f"Message body: {msg.body}")
                logger.error(f"Message metadata: {msg.metadata}")

    class PassengersBehaviour(CyclicBehaviour):
        async def run(self):
            while True:
                self._generate_initial_passengers()
                await asyncio.sleep(15)

        def _generate_initial_passengers(self):
            """Genera 4 pasajeros iniciales"""
            for i in range(4):
                self._create_new_passenger()

        def _create_new_passenger(
            self,
            is_disabled=False,
            is_elderly=False,
            is_child=False,
            is_pregnant=False,
            price=10.0,
        ):
            """Crea un nuevo pasajero con opciones de discapacidad y precio"""
            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            passenger_id = f"P{coordinator.passenger_counter}"
            coordinator.passenger_counter += 1

            # Generar posiciones aleatorias con distancia mínima
            pickup = coordinator.grid.get_random_intersection()
            dropoff = coordinator.grid.get_random_intersection()

            # Asegurar distancia mínima entre pickup y dropoff
            max_attempts = 10
            attempts = 0
            while pickup.manhattan_distance(dropoff) < 5 and attempts < max_attempts:
                dropoff = coordinator.grid.get_random_intersection()
                attempts += 1

            # Determinar prioridades y precio aleatorio
            if not any([is_disabled, is_elderly, is_child, is_pregnant]):
                # Asignar aleatoriamente algunas prioridades
                if random.random() < 0.1:  # 10% discapacitado
                    is_disabled = True
                elif random.random() < 0.15:  # 15% adulto mayor
                    is_elderly = True
                elif random.random() < 0.1:  # 10% niño
                    is_child = True
                elif random.random() < 0.1:  # 10% embarazada
                    is_pregnant = True

            # Precio aleatorio con variación
            if price == 10.0:
                price = random.uniform(8.0, 25.0)

            passenger = PassengerInfo(
                passenger_id=passenger_id,
                pickup_position=pickup,
                dropoff_position=dropoff,
                state=PassengerState.WAITING,
                wait_time=0.0,
                is_disabled=is_disabled,
                is_elderly=is_elderly,
                is_child=is_child,
                is_pregnant=is_pregnant,
                price=price,
            )

            coordinator.passengers[passenger_id] = passenger

            # Log detallado
            priorities = []
            if is_disabled:
                priorities.append("DISABLED")
            if is_elderly:
                priorities.append("ELDERLY")
            if is_child:
                priorities.append("CHILD")
            if is_pregnant:
                priorities.append("PREGNANT")

            priority_str = f" [{', '.join(priorities)}]" if priorities else ""
            logger.info(
                f"Created passenger {passenger_id}{priority_str} at ({pickup.x}, {pickup.y}) -> ({dropoff.x}, {dropoff.y}), price: S/{price:.2f}"
            )

            return passenger

        def update_passenger_wait_times(self, dt: float):
            """Actualiza tiempos de espera de pasajeros"""
            coordinator: "CoordinatorAgent" = self.agent  # type: ignore

            for passenger in coordinator.passengers.values():
                if passenger.state == PassengerState.WAITING:
                    passenger.wait_time += dt


## LAUNCHER
def launch_agent_coordinator():
    """Función principal del sistema"""

    print("🚕 Sistema de Taxis con Constraint Programming")
    print("=" * 50)

    try:
        print("✅ Módulos cargados correctamente")
        print("🔥 Iniciando sistema...")
        # Lanzar la interfaz gráfica
        launch_taxi_gui()

    except KeyboardInterrupt:
        print("\n🛑 Sistema interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error al iniciar el sistema: {e}")
        traceback.print_exc()
        return 1

    return 0
