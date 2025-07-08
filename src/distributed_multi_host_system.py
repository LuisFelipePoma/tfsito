"""
Sistema de Despacho de Taxis Distribuido Multi-Host
==================================================

Arquitectura para despliegue distribuido usando OpenFire/XMPP:
- Host Central (Coordinador): Gestiona la grilla global y coordinación
- Host de Taxis: Ejecuta agentes taxi individuales 
- Host de Pasajeros: Gestiona generación y seguimiento de pasajeros
- Comunicación via OpenFire/XMPP para sincronización de estado

Autor: Sistema de Taxis Inteligente Distribuido
Fecha: 2025
"""

import asyncio
import json
import logging
import random
import time
import argparse
import socket
import threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import uuid
import os

# Optional imports
try:
    from ortools.constraint_solver import pywrapcp
    OR_TOOLS_AVAILABLE = True
except ImportError:
    OR_TOOLS_AVAILABLE = False

try:
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
    from spade.message import Message
    from spade.template import Template
    SPADE_AVAILABLE = True
except ImportError:
    SPADE_AVAILABLE = False

# Local imports
from config import config, taxi_config
from services.openfire_api import openfire_api
from distributed_taxi_system import (
    GridPosition, TaxiState, PassengerState, TaxiInfo, PassengerInfo,
    GridNetwork, ConstraintSolver, GridTaxi, GridPassenger
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

@dataclass
class DistributedConfig:
    """Configuración para despliegue distribuido"""
    # Host identification
    host_id: str = ""
    host_type: str = "coordinator"  # coordinator, taxi_host, passenger_host
    host_ip: str = "localhost"
    
    # OpenFire configuration
    openfire_host: str = "localhost"
    openfire_domain: str = "localhost"
    openfire_port: int = 9090
    openfire_xmpp_port: int = 5222
    
    # Distributed system parameters
    coordinator_jid: str = "coordinator@localhost"
    heartbeat_interval: float = 5.0
    state_sync_interval: float = 2.0
    message_timeout: float = 10.0
    
    # Host capacity limits
    max_taxis_per_host: int = 10
    max_passengers_per_host: int = 50
    
    # Grid partitioning (for load balancing)
    grid_partition_x: int = 0
    grid_partition_y: int = 0
    partition_width: int = 20
    partition_height: int = 20

# Global distributed config
dist_config = DistributedConfig()

def load_distributed_config():
    """Carga configuración distribuida desde variables de entorno"""
    dist_config.host_id = os.getenv("HOST_ID", socket.gethostname())
    dist_config.host_type = os.getenv("HOST_TYPE", "coordinator")
    dist_config.host_ip = os.getenv("HOST_IP", get_local_ip())
    dist_config.openfire_host = os.getenv("OPENFIRE_HOST", "localhost")
    dist_config.openfire_domain = os.getenv("OPENFIRE_DOMAIN", "localhost")
    dist_config.coordinator_jid = f"coordinator@{dist_config.openfire_domain}"
    
    logger.info(f"Configuración distribuida cargada: {dist_config.host_id} ({dist_config.host_type})")
    return dist_config

def get_local_ip():
    """Obtiene la IP local del host"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

# ==================== MESSAGE TYPES ====================

class MessageType(Enum):
    """Tipos de mensajes para comunicación distribuida"""
    # System management
    HOST_REGISTER = "host_register"
    HOST_HEARTBEAT = "host_heartbeat"
    HOST_SHUTDOWN = "host_shutdown"
    
    # State synchronization
    STATE_UPDATE = "state_update"
    STATE_REQUEST = "state_request"
    STATE_RESPONSE = "state_response"
    
    # Taxi operations
    TAXI_ASSIGNMENT = "taxi_assignment"
    TAXI_STATUS_UPDATE = "taxi_status_update"
    TAXI_PICKUP_COMPLETE = "taxi_pickup_complete"
    TAXI_DELIVERY_COMPLETE = "taxi_delivery_complete"
    
    # Passenger operations
    PASSENGER_REQUEST = "passenger_request"
    PASSENGER_CREATED = "passenger_created"
    PASSENGER_STATUS_UPDATE = "passenger_status_update"
    
    # Coordination
    ASSIGNMENT_REQUEST = "assignment_request"
    ASSIGNMENT_RESPONSE = "assignment_response"
    CONSTRAINT_SOLVE_REQUEST = "constraint_solve_request"
    CONSTRAINT_SOLVE_RESPONSE = "constraint_solve_response"

@dataclass
class DistributedMessage:
    """Mensaje estructurado para comunicación distribuida"""
    message_type: MessageType
    sender_id: str
    recipient_id: str
    timestamp: float
    data: Dict[str, Any]
    message_id: str = ""
    
    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

# ==================== COORDINATOR AGENT ====================

if SPADE_AVAILABLE:
    class CoordinatorAgent(Agent):
        """Agente coordinador central del sistema distribuido"""
        
        def __init__(self, jid: str, password: str):
            super().__init__(jid, password)
            self.grid = GridNetwork(taxi_config.taxi_grid_width, taxi_config.taxi_grid_height)
            self.solver = ConstraintSolver()
            
            # Global system state
            self.registered_hosts: Dict[str, Dict] = {}
            self.global_taxis: Dict[str, TaxiInfo] = {}
            self.global_passengers: Dict[str, PassengerInfo] = {}
            self.assignments: Dict[str, str] = {}  # {taxi_id: passenger_id}
            
            # Statistics
            self.total_assignments = 0
            self.total_deliveries = 0
            self.start_time = time.time()
            
            logger.info(f"Coordinador iniciado: {jid}")
        
        async def setup(self):
            """Configuración inicial del coordinador"""
            logger.info("Configurando coordinador...")
            
            # Comportamiento de registro de hosts
            self.add_behaviour(self.HostRegistrationBehaviour())
            
            # Comportamiento de asignación
            self.add_behaviour(self.AssignmentBehaviour(period=taxi_config.assignment_interval))
            
            # Comportamiento de sincronización de estado
            self.add_behaviour(self.StateSyncBehaviour(period=dist_config.state_sync_interval))
            
            # Comportamiento de heartbeat
            self.add_behaviour(self.HeartbeatBehaviour(period=dist_config.heartbeat_interval))
            
            logger.info("Coordinador configurado y listo")
        
        class HostRegistrationBehaviour(CyclicBehaviour):
            """Maneja registro y comunicación con hosts"""
            
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    await self.handle_message(msg)
            
            async def handle_message(self, msg):
                """Procesa mensajes recibidos"""
                try:
                    data = json.loads(msg.body)
                    message = DistributedMessage(**data)
                    coordinator = self.agent
                    
                    if message.message_type == MessageType.HOST_REGISTER:
                        await self.handle_host_registration(message)
                    elif message.message_type == MessageType.HOST_HEARTBEAT:
                        await self.handle_host_heartbeat(message)
                    elif message.message_type == MessageType.TAXI_STATUS_UPDATE:
                        await self.handle_taxi_status_update(message)
                    elif message.message_type == MessageType.PASSENGER_CREATED:
                        await self.handle_passenger_created(message)
                    elif message.message_type == MessageType.TAXI_PICKUP_COMPLETE:
                        await self.handle_taxi_pickup_complete(message)
                    elif message.message_type == MessageType.TAXI_DELIVERY_COMPLETE:
                        await self.handle_taxi_delivery_complete(message)
                    
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")
            
            async def handle_host_registration(self, message):
                """Maneja registro de nuevo host"""
                host_id = message.sender_id
                host_data = message.data
                
                self.agent.registered_hosts[host_id] = {
                    **host_data,
                    'last_heartbeat': time.time(),
                    'status': 'active'
                }
                
                logger.info(f"Host registrado: {host_id} ({host_data.get('host_type', 'unknown')})")
                
                # Responder con configuración global
                response = DistributedMessage(
                    message_type=MessageType.STATE_RESPONSE,
                    sender_id=str(self.agent.jid),
                    recipient_id=host_id,
                    timestamp=time.time(),
                    data={
                        'grid_config': {
                            'width': self.agent.grid.width,
                            'height': self.agent.grid.height
                        },
                        'global_taxis': {tid: asdict(taxi) for tid, taxi in self.agent.global_taxis.items()},
                        'global_passengers': {pid: asdict(passenger) for pid, passenger in self.agent.global_passengers.items()}
                    }
                )
                
                await self.send_message(response, f"{host_id}@{dist_config.openfire_domain}")
            
            async def handle_host_heartbeat(self, message):
                """Actualiza último heartbeat del host"""
                host_id = message.sender_id
                if host_id in self.agent.registered_hosts:
                    self.agent.registered_hosts[host_id]['last_heartbeat'] = time.time()
            
            async def handle_taxi_status_update(self, message):
                """Actualiza estado de taxi"""
                taxi_data = message.data.get('taxi_info', {})
                if taxi_data:
                    taxi_info = TaxiInfo(**taxi_data)
                    self.agent.global_taxis[taxi_info.taxi_id] = taxi_info
            
            async def handle_passenger_created(self, message):
                """Registra nuevo pasajero"""
                passenger_data = message.data.get('passenger_info', {})
                if passenger_data:
                    passenger_info = PassengerInfo(**passenger_data)
                    self.agent.global_passengers[passenger_info.passenger_id] = passenger_info
                    logger.info(f"Pasajero registrado: {passenger_info.passenger_id}")
            
            async def handle_taxi_pickup_complete(self, message):
                """Maneja recogida completada"""
                taxi_id = message.data.get('taxi_id')
                passenger_id = message.data.get('passenger_id')
                
                if passenger_id in self.agent.global_passengers:
                    self.agent.global_passengers[passenger_id].state = PassengerState.PICKED_UP
                    logger.info(f"Pasajero {passenger_id} recogido por taxi {taxi_id}")
            
            async def handle_taxi_delivery_complete(self, message):
                """Maneja entrega completada"""
                passenger_id = message.data.get('passenger_id')
                
                if passenger_id in self.agent.global_passengers:
                    self.agent.global_passengers[passenger_id].state = PassengerState.DELIVERED
                    self.agent.total_deliveries += 1
                    logger.info(f"Pasajero {passenger_id} entregado. Total entregas: {self.agent.total_deliveries}")
            
            async def send_message(self, dist_msg: DistributedMessage, recipient_jid: str):
                """Envía mensaje SPADE"""
                msg = Message(to=recipient_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(dist_msg))
                await self.send(msg)
        
        class AssignmentBehaviour(PeriodicBehaviour):
            """Realiza asignaciones usando constraint programming"""
            
            async def run(self):
                coordinator = self.agent
                
                # Obtener taxis y pasajeros disponibles
                available_taxis = [taxi for taxi in coordinator.global_taxis.values() 
                                 if taxi.state == TaxiState.IDLE]
                waiting_passengers = [passenger for passenger in coordinator.global_passengers.values() 
                                    if passenger.state == PassengerState.WAITING]
                
                if not available_taxis or not waiting_passengers:
                    return
                
                logger.info(f"Ejecutando asignación: {len(available_taxis)} taxis, {len(waiting_passengers)} pasajeros")
                
                # Resolver asignaciones
                assignments = coordinator.solver.solve_assignment(available_taxis, waiting_passengers)
                
                # Enviar asignaciones a hosts de taxis
                for taxi_id, passenger_id in assignments.items():
                    await self.send_assignment(taxi_id, passenger_id)
                    coordinator.total_assignments += 1
            
            async def send_assignment(self, taxi_id: str, passenger_id: str):
                """Envía asignación a host de taxi"""
                coordinator = self.agent
                
                if taxi_id not in coordinator.global_taxis or passenger_id not in coordinator.global_passengers:
                    return
                
                taxi = coordinator.global_taxis[taxi_id]
                passenger = coordinator.global_passengers[passenger_id]
                
                # Encontrar host del taxi
                taxi_host = None
                for host_id, host_data in coordinator.registered_hosts.items():
                    if host_data.get('host_type') == 'taxi_host':
                        # Asumir que el taxi pertenece al primer host de taxis encontrado
                        # En implementación real, se mantendría un mapeo taxi -> host
                        taxi_host = host_id
                        break
                
                if not taxi_host:
                    logger.warning(f"No se encontró host para taxi {taxi_id}")
                    return
                
                # Crear mensaje de asignación
                assignment_msg = DistributedMessage(
                    message_type=MessageType.TAXI_ASSIGNMENT,
                    sender_id=str(coordinator.jid),
                    recipient_id=taxi_host,
                    timestamp=time.time(),
                    data={
                        'taxi_id': taxi_id,
                        'passenger_id': passenger_id,
                        'pickup_position': asdict(passenger.pickup_position),
                        'dropoff_position': asdict(passenger.dropoff_position)
                    }
                )
                
                # Enviar a host de taxi
                taxi_host_jid = f"{taxi_host}@{dist_config.openfire_domain}"
                msg = Message(to=taxi_host_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(assignment_msg))
                await self.send(msg)
                
                # Actualizar estados
                coordinator.global_taxis[taxi_id].state = TaxiState.PICKUP
                coordinator.global_taxis[taxi_id].assigned_passenger_id = passenger_id
                coordinator.global_passengers[passenger_id].assigned_taxi_id = taxi_id
                
                logger.info(f"Asignación enviada: {taxi_id} -> {passenger_id}")
        
        class StateSyncBehaviour(PeriodicBehaviour):
            """Sincroniza estado global con hosts"""
            
            async def run(self):
                coordinator = self.agent
                
                # Preparar estado global
                global_state = {
                    'timestamp': time.time(),
                    'statistics': {
                        'total_hosts': len(coordinator.registered_hosts),
                        'total_taxis': len(coordinator.global_taxis),
                        'total_passengers': len(coordinator.global_passengers),
                        'total_assignments': coordinator.total_assignments,
                        'total_deliveries': coordinator.total_deliveries,
                        'uptime': time.time() - coordinator.start_time
                    },
                    'active_assignments': len([t for t in coordinator.global_taxis.values() 
                                             if t.state != TaxiState.IDLE])
                }
                
                # Enviar a todos los hosts activos
                for host_id, host_data in coordinator.registered_hosts.items():
                    if time.time() - host_data['last_heartbeat'] < dist_config.heartbeat_interval * 2:
                        await self.send_state_sync(host_id, global_state)
            
            async def send_state_sync(self, host_id: str, state_data: Dict):
                """Envía sincronización de estado a un host"""
                sync_msg = DistributedMessage(
                    message_type=MessageType.STATE_UPDATE,
                    sender_id=str(self.agent.jid),
                    recipient_id=host_id,
                    timestamp=time.time(),
                    data=state_data
                )
                
                host_jid = f"{host_id}@{dist_config.openfire_domain}"
                msg = Message(to=host_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(sync_msg))
                await self.send(msg)
        
        class HeartbeatBehaviour(PeriodicBehaviour):
            """Monitorea salud de hosts"""
            
            async def run(self):
                coordinator = self.agent
                current_time = time.time()
                
                # Verificar hosts inactivos
                inactive_hosts = []
                for host_id, host_data in coordinator.registered_hosts.items():
                    if current_time - host_data['last_heartbeat'] > dist_config.heartbeat_interval * 3:
                        inactive_hosts.append(host_id)
                
                # Marcar hosts como inactivos
                for host_id in inactive_hosts:
                    coordinator.registered_hosts[host_id]['status'] = 'inactive'
                    logger.warning(f"Host {host_id} marcado como inactivo")

# ==================== TAXI HOST AGENT ====================

if SPADE_AVAILABLE:
    class TaxiHostAgent(Agent):
        """Agente host que maneja múltiples taxis"""
        
        def __init__(self, jid: str, password: str, host_id: str):
            super().__init__(jid, password)
            self.host_id = host_id
            self.grid = None  # Se configura después del registro
            self.taxis: Dict[str, GridTaxi] = {}
            self.coordinator_jid = dist_config.coordinator_jid
            self.registered = False
            
            logger.info(f"Host de taxis iniciado: {host_id}")
        
        async def setup(self):
            """Configuración inicial del host de taxis"""
            logger.info(f"Configurando host de taxis {self.host_id}...")
            
            # Registrarse con el coordinador
            await self.register_with_coordinator()
            
            # Comportamientos
            self.add_behaviour(self.MessageHandlerBehaviour())
            self.add_behaviour(self.TaxiUpdateBehaviour(period=0.5))  # 2 FPS
            self.add_behaviour(self.HeartbeatBehaviour(period=dist_config.heartbeat_interval))
            
            logger.info(f"Host de taxis {self.host_id} configurado")
        
        async def register_with_coordinator(self):
            """Se registra con el coordinador"""
            registration_msg = DistributedMessage(
                message_type=MessageType.HOST_REGISTER,
                sender_id=self.host_id,
                recipient_id="coordinator",
                timestamp=time.time(),
                data={
                    'host_type': 'taxi_host',
                    'host_ip': dist_config.host_ip,
                    'max_capacity': dist_config.max_taxis_per_host
                }
            )
            
            msg = Message(to=self.coordinator_jid)
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps(asdict(registration_msg))
            await self.send(msg)
            
            logger.info(f"Registro enviado al coordinador: {self.coordinator_jid}")
        
        def create_local_taxis(self, count: int = 3):
            """Crea taxis locales en este host"""
            if not self.grid:
                logger.error("Grid no configurado. No se pueden crear taxis.")
                return
            
            for i in range(count):
                taxi_id = f"{self.host_id}_taxi_{i+1}"
                position = self.grid.get_random_intersection()
                taxi = GridTaxi(taxi_id, position, self.grid)
                self.taxis[taxi_id] = taxi
                logger.info(f"Taxi {taxi_id} creado en posición {position.x}, {position.y}")
        
        class MessageHandlerBehaviour(CyclicBehaviour):
            """Maneja mensajes del coordinador"""
            
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    await self.handle_message(msg)
            
            async def handle_message(self, msg):
                """Procesa mensajes recibidos"""
                try:
                    data = json.loads(msg.body)
                    message = DistributedMessage(**data)
                    taxi_host = self.agent
                    
                    if message.message_type == MessageType.STATE_RESPONSE and not taxi_host.registered:
                        await self.handle_initial_config(message)
                    elif message.message_type == MessageType.TAXI_ASSIGNMENT:
                        await self.handle_taxi_assignment(message)
                    elif message.message_type == MessageType.STATE_UPDATE:
                        await self.handle_state_update(message)
                    
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")
            
            async def handle_initial_config(self, message):
                """Maneja configuración inicial del coordinador"""
                taxi_host = self.agent
                config_data = message.data
                
                # Configurar grid
                grid_config = config_data.get('grid_config', {})
                taxi_host.grid = GridNetwork(
                    grid_config.get('width', 20),
                    grid_config.get('height', 20)
                )
                
                # Crear taxis locales
                taxi_host.create_local_taxis()
                taxi_host.registered = True
                
                logger.info(f"Host {taxi_host.host_id} configurado con grid {grid_config}")
            
            async def handle_taxi_assignment(self, message):
                """Maneja asignación de taxi"""
                taxi_host = self.agent
                assignment_data = message.data
                
                taxi_id = assignment_data.get('taxi_id')
                passenger_id = assignment_data.get('passenger_id')
                pickup_pos = GridPosition(**assignment_data.get('pickup_position', {}))
                dropoff_pos = GridPosition(**assignment_data.get('dropoff_position', {}))
                
                if taxi_id in taxi_host.taxis:
                    taxi = taxi_host.taxis[taxi_id]
                    success = taxi.assign_passenger(passenger_id, pickup_pos, dropoff_pos)
                    
                    if success:
                        logger.info(f"Taxi {taxi_id} asignado a pasajero {passenger_id}")
                    else:
                        logger.warning(f"Falló asignación de taxi {taxi_id}")
                else:
                    logger.warning(f"Taxi {taxi_id} no encontrado en host {taxi_host.host_id}")
            
            async def handle_state_update(self, message):
                """Maneja actualización de estado global"""
                state_data = message.data
                statistics = state_data.get('statistics', {})
                
                logger.debug(f"Estado global: {statistics.get('total_taxis', 0)} taxis, "
                           f"{statistics.get('total_passengers', 0)} pasajeros, "
                           f"{statistics.get('total_deliveries', 0)} entregas")
        
        class TaxiUpdateBehaviour(PeriodicBehaviour):
            """Actualiza taxis locales y reporta al coordinador"""
            
            async def run(self):
                taxi_host = self.agent
                
                if not taxi_host.registered:
                    return
                
                # Actualizar todos los taxis
                for taxi in taxi_host.taxis.values():
                    event = taxi.update(0.5)  # 0.5 seconds update
                    
                    # Reportar eventos importantes
                    if event == "passenger_picked_up":
                        await self.report_pickup_complete(taxi)
                    elif event == "passenger_delivered":
                        await self.report_delivery_complete(taxi)
                    
                    # Reportar estado actualizado
                    await self.report_taxi_status(taxi)
            
            async def report_pickup_complete(self, taxi: GridTaxi):
                """Reporta recogida completada"""
                pickup_msg = DistributedMessage(
                    message_type=MessageType.TAXI_PICKUP_COMPLETE,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'taxi_id': taxi.info.taxi_id,
                        'passenger_id': taxi.info.assigned_passenger_id
                    }
                )
                
                await self.send_to_coordinator(pickup_msg)
            
            async def report_delivery_complete(self, taxi: GridTaxi):
                """Reporta entrega completada"""
                delivery_msg = DistributedMessage(
                    message_type=MessageType.TAXI_DELIVERY_COMPLETE,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'taxi_id': taxi.info.taxi_id,
                        'passenger_id': taxi.info.assigned_passenger_id
                    }
                )
                
                await self.send_to_coordinator(delivery_msg)
            
            async def report_taxi_status(self, taxi: GridTaxi):
                """Reporta estado del taxi"""
                status_msg = DistributedMessage(
                    message_type=MessageType.TAXI_STATUS_UPDATE,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'taxi_info': asdict(taxi.info)
                    }
                )
                
                await self.send_to_coordinator(status_msg)
            
            async def send_to_coordinator(self, dist_msg: DistributedMessage):
                """Envía mensaje al coordinador"""
                msg = Message(to=self.agent.coordinator_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(dist_msg))
                await self.send(msg)
        
        class HeartbeatBehaviour(PeriodicBehaviour):
            """Envía heartbeat al coordinador"""
            
            async def run(self):
                if not self.agent.registered:
                    return
                
                heartbeat_msg = DistributedMessage(
                    message_type=MessageType.HOST_HEARTBEAT,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'active_taxis': len(self.agent.taxis),
                        'host_status': 'active'
                    }
                )
                
                msg = Message(to=self.agent.coordinator_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(heartbeat_msg))
                await self.send(msg)

# ==================== PASSENGER HOST AGENT ====================

if SPADE_AVAILABLE:
    class PassengerHostAgent(Agent):
        """Agente host que maneja generación de pasajeros"""
        
        def __init__(self, jid: str, password: str, host_id: str):
            super().__init__(jid, password)
            self.host_id = host_id
            self.grid = None
            self.passengers: Dict[str, GridPassenger] = {}
            self.coordinator_jid = dist_config.coordinator_jid
            self.registered = False
            self.passenger_counter = 0
            
            logger.info(f"Host de pasajeros iniciado: {host_id}")
        
        async def setup(self):
            """Configuración inicial del host de pasajeros"""
            logger.info(f"Configurando host de pasajeros {self.host_id}...")
            
            # Registrarse con el coordinador
            await self.register_with_coordinator()
            
            # Comportamientos
            self.add_behaviour(self.MessageHandlerBehaviour())
            self.add_behaviour(self.PassengerGeneratorBehaviour(period=10.0))  # Nuevo pasajero cada 10s
            self.add_behaviour(self.PassengerUpdateBehaviour(period=1.0))
            self.add_behaviour(self.HeartbeatBehaviour(period=dist_config.heartbeat_interval))
            
            logger.info(f"Host de pasajeros {self.host_id} configurado")
        
        async def register_with_coordinator(self):
            """Se registra con el coordinador"""
            registration_msg = DistributedMessage(
                message_type=MessageType.HOST_REGISTER,
                sender_id=self.host_id,
                recipient_id="coordinator",
                timestamp=time.time(),
                data={
                    'host_type': 'passenger_host',
                    'host_ip': dist_config.host_ip,
                    'max_capacity': dist_config.max_passengers_per_host
                }
            )
            
            msg = Message(to=self.coordinator_jid)
            msg.set_metadata("performative", "inform")
            msg.body = json.dumps(asdict(registration_msg))
            await self.send(msg)
            
            logger.info(f"Registro enviado al coordinador: {self.coordinator_jid}")
        
        def create_passenger(self):
            """Crea un nuevo pasajero"""
            if not self.grid:
                return None
            
            passenger_id = f"{self.host_id}_passenger_{self.passenger_counter}"
            self.passenger_counter += 1
            
            pickup_pos = self.grid.get_random_intersection()
            dropoff_pos = self.grid.get_random_intersection()
            
            # Asegurar distancia mínima
            while pickup_pos.manhattan_distance(dropoff_pos) < 5:
                dropoff_pos = self.grid.get_random_intersection()
            
            passenger = GridPassenger(passenger_id, pickup_pos, dropoff_pos)
            self.passengers[passenger_id] = passenger
            
            logger.info(f"Pasajero {passenger_id} creado: {pickup_pos.x},{pickup_pos.y} -> {dropoff_pos.x},{dropoff_pos.y}")
            return passenger
        
        class MessageHandlerBehaviour(CyclicBehaviour):
            """Maneja mensajes del coordinador"""
            
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    await self.handle_message(msg)
            
            async def handle_message(self, msg):
                """Procesa mensajes recibidos"""
                try:
                    data = json.loads(msg.body)
                    message = DistributedMessage(**data)
                    passenger_host = self.agent
                    
                    if message.message_type == MessageType.STATE_RESPONSE and not passenger_host.registered:
                        await self.handle_initial_config(message)
                    elif message.message_type == MessageType.STATE_UPDATE:
                        await self.handle_state_update(message)
                    
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")
            
            async def handle_initial_config(self, message):
                """Maneja configuración inicial del coordinador"""
                passenger_host = self.agent
                config_data = message.data
                
                # Configurar grid
                grid_config = config_data.get('grid_config', {})
                passenger_host.grid = GridNetwork(
                    grid_config.get('width', 20),
                    grid_config.get('height', 20)
                )
                
                # Crear pasajeros iniciales
                for _ in range(2):
                    passenger = passenger_host.create_passenger()
                    if passenger:
                        await self.report_passenger_created(passenger)
                
                passenger_host.registered = True
                logger.info(f"Host {passenger_host.host_id} configurado con grid {grid_config}")
            
            async def handle_state_update(self, message):
                """Maneja actualización de estado global"""
                state_data = message.data
                statistics = state_data.get('statistics', {})
                
                logger.debug(f"Estado global recibido en host de pasajeros: {statistics}")
            
            async def report_passenger_created(self, passenger: GridPassenger):
                """Reporta nuevo pasajero al coordinador"""
                passenger_msg = DistributedMessage(
                    message_type=MessageType.PASSENGER_CREATED,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'passenger_info': asdict(passenger.info)
                    }
                )
                
                msg = Message(to=self.agent.coordinator_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(passenger_msg))
                await self.send(msg)
        
        class PassengerGeneratorBehaviour(PeriodicBehaviour):
            """Genera nuevos pasajeros periódicamente"""
            
            async def run(self):
                passenger_host = self.agent
                
                if not passenger_host.registered:
                    return
                
                # Crear nuevo pasajero si no hay demasiados
                waiting_passengers = len([p for p in passenger_host.passengers.values() 
                                        if p.info.state == PassengerState.WAITING])
                
                if waiting_passengers < 5:  # Máximo 5 pasajeros esperando por host
                    passenger = passenger_host.create_passenger()
                    if passenger:
                        await self.report_passenger_created(passenger)
            
            async def report_passenger_created(self, passenger: GridPassenger):
                """Reporta nuevo pasajero al coordinador"""
                passenger_msg = DistributedMessage(
                    message_type=MessageType.PASSENGER_CREATED,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'passenger_info': asdict(passenger.info)
                    }
                )
                
                msg = Message(to=self.agent.coordinator_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(passenger_msg))
                await self.send(msg)
        
        class PassengerUpdateBehaviour(PeriodicBehaviour):
            """Actualiza pasajeros locales"""
            
            async def run(self):
                passenger_host = self.agent
                
                if not passenger_host.registered:
                    return
                
                # Actualizar tiempo de espera de pasajeros
                for passenger in passenger_host.passengers.values():
                    passenger.update(1.0)  # 1 second update
        
        class HeartbeatBehaviour(PeriodicBehaviour):
            """Envía heartbeat al coordinador"""
            
            async def run(self):
                if not self.agent.registered:
                    return
                
                heartbeat_msg = DistributedMessage(
                    message_type=MessageType.HOST_HEARTBEAT,
                    sender_id=self.agent.host_id,
                    recipient_id="coordinator",
                    timestamp=time.time(),
                    data={
                        'active_passengers': len(self.agent.passengers),
                        'host_status': 'active'
                    }
                )
                
                msg = Message(to=self.agent.coordinator_jid)
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(asdict(heartbeat_msg))
                await self.send(msg)

# ==================== DISTRIBUTED SYSTEM MANAGER ====================

class DistributedTaxiManager:
    """Gestor principal del sistema distribuido"""
    
    def __init__(self, host_type: str):
        self.host_type = host_type
        self.host_id = dist_config.host_id
        self.agent = None
        self.running = False
        
        # Configurar OpenFire API
        self.setup_openfire_users()
        
        logger.info(f"Manager distribuido iniciado: {host_type} en {self.host_id}")
    
    def setup_openfire_users(self):
        """Configura usuarios en OpenFire"""
        if not SPADE_AVAILABLE:
            logger.warning("SPADE no disponible, saltando configuración de OpenFire")
            return
        
        try:
            # Crear usuario para el coordinador
            if self.host_type == "coordinator":
                openfire_api.create_user("coordinator", "password", "Coordinator Agent")
            
            # Crear usuario para este host
            openfire_api.create_user(self.host_id, "password", f"Host {self.host_id}")
            
            logger.info(f"Usuario OpenFire configurado: {self.host_id}")
            
        except Exception as e:
            logger.error(f"Error configurando OpenFire: {e}")
    
    async def start_agent(self):
        """Inicia el agente apropiado según el tipo de host"""
        if not SPADE_AVAILABLE:
            logger.error("SPADE no disponible. Sistema distribuido requiere SPADE.")
            return False
        
        try:
            jid = f"{self.host_id}@{dist_config.openfire_domain}"
            
            if self.host_type == "coordinator":
                self.agent = CoordinatorAgent(jid, "password")
            elif self.host_type == "taxi_host":
                self.agent = TaxiHostAgent(jid, "password", self.host_id)
            elif self.host_type == "passenger_host":
                self.agent = PassengerHostAgent(jid, "password", self.host_id)
            else:
                logger.error(f"Tipo de host desconocido: {self.host_type}")
                return False
            
            await self.agent.start()
            self.running = True
            logger.info(f"Agente {self.host_type} iniciado: {jid}")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando agente: {e}")
            return False
    
    async def stop_agent(self):
        """Detiene el agente"""
        if self.agent and self.running:
            try:
                await self.agent.stop()
                self.running = False
                logger.info(f"Agente {self.host_type} detenido")
            except Exception as e:
                logger.error(f"Error deteniendo agente: {e}")
    
    async def run_forever(self):
        """Ejecuta el sistema indefinidamente"""
        if await self.start_agent():
            try:
                while self.running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Interrupción por teclado recibida")
            finally:
                await self.stop_agent()
        else:
            logger.error("No se pudo iniciar el agente")

# ==================== MAIN ENTRY POINTS ====================

async def run_coordinator():
    """Ejecuta el coordinador"""
    load_distributed_config()
    manager = DistributedTaxiManager("coordinator")
    await manager.run_forever()

async def run_taxi_host():
    """Ejecuta un host de taxis"""
    load_distributed_config()
    manager = DistributedTaxiManager("taxi_host")
    await manager.run_forever()

async def run_passenger_host():
    """Ejecuta un host de pasajeros"""
    load_distributed_config()
    manager = DistributedTaxiManager("passenger_host")
    await manager.run_forever()

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sistema de Taxis Distribuido')
    parser.add_argument('--type', choices=['coordinator', 'taxi_host', 'passenger_host'],
                      required=True, help='Tipo de host a ejecutar')
    parser.add_argument('--host-id', help='ID único del host (opcional)')
    parser.add_argument('--openfire-host', default='localhost', help='Host de OpenFire')
    parser.add_argument('--openfire-domain', default='localhost', help='Dominio de OpenFire')
    
    args = parser.parse_args()
    
    # Configurar variables de entorno
    if args.host_id:
        os.environ['HOST_ID'] = args.host_id
    os.environ['HOST_TYPE'] = args.type
    os.environ['OPENFIRE_HOST'] = args.openfire_host
    os.environ['OPENFIRE_DOMAIN'] = args.openfire_domain
    
    # Ejecutar el tipo de host apropiado
    if args.type == 'coordinator':
        asyncio.run(run_coordinator())
    elif args.type == 'taxi_host':
        asyncio.run(run_taxi_host())
    elif args.type == 'passenger_host':
        asyncio.run(run_passenger_host())

if __name__ == "__main__":
    main()

