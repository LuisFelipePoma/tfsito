"""
Sistema Completo de Despacho de Taxis con Constraint Programming
==============================================================

Sistema distribuido que utiliza:
- OR-Tools para asignación óptima
- OpenFire/XMPP para comunicación entre agentes
- Mapa de grilla con movimiento Manhattan
- Interfaz gráfica con Tkinter

Autor: Sistema de Taxis Inteligente
Fecha: 2025
"""

import asyncio
import json
import logging
import math
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
import uuid
import requests

# Imports para SPADE y OpenFire
try:
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
    from spade.message import Message
    from spade.template import Template
    SPADE_AVAILABLE = True
except ImportError:
    SPADE_AVAILABLE = False
    print("Warning: SPADE not available. Install with: pip install spade")

# Import para constraint programming
try:
    from ortools.constraint_solver import pywrapcp
    OR_TOOLS_AVAILABLE = True
except ImportError:
    OR_TOOLS_AVAILABLE = False
    print("Warning: OR-Tools not available. Install with: pip install ortools")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not available. Install with: pip install numpy")

# Import locales
try:
    from config import config
    from services.openfire_api import openfire_api
except ImportError:
    # Fallback config if imports fail
    class FallbackConfig:
        grid_width = 20
        grid_height = 20
        gui_width = 1200
        gui_height = 800
        grid_cell_size = 20
        fps = 20
        openfire_host = "localhost"
        openfire_port = 9090
        openfire_domain = "localhost"
    
    config = FallbackConfig()
    
    class FallbackOpenFireAPI:
        def create_user(self, username, password, name):
            print(f"Fallback: Creating user {username}")
    
    openfire_api = FallbackOpenFireAPI()

# Configure logging
logger = logging.getLogger(__name__)

# ==================== ESTRUCTURAS DE DATOS ====================

class TaxiState(Enum):
    """Estados posibles del taxi"""
    IDLE = "idle"           # Patrullando aleatoriamente
    ASSIGNED = "assigned"   # Asignado a un pasajero
    PICKUP = "pickup"       # Yendo a recoger pasajero
    DROPOFF = "dropoff"     # Llevando pasajero al destino

class PassengerState(Enum):
    """Estados posibles del pasajero"""
    WAITING = "waiting"     # Esperando taxi
    PICKED_UP = "picked_up" # En el taxi
    DELIVERED = "delivered" # Entregado

@dataclass
class GridPosition:
    """Posición en la grilla"""
    x: int
    y: int
    
    def manhattan_distance(self, other: 'GridPosition') -> int:
        """Calcula distancia Manhattan"""
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        if isinstance(other, GridPosition):
            return self.x == other.x and self.y == other.y
        return False

@dataclass
class TaxiInfo:
    """Información completa del taxi"""
    taxi_id: str
    position: GridPosition
    target_position: Optional[GridPosition]
    state: TaxiState
    capacity: int
    current_passengers: int
    assigned_passenger_id: Optional[str]
    speed: float = 1.0  # Celdas por segundo
    
@dataclass
class PassengerInfo:
    """Información completa del pasajero"""
    passenger_id: str
    pickup_position: GridPosition
    dropoff_position: GridPosition
    state: PassengerState
    wait_time: float
    assigned_taxi_id: Optional[str] = None

# ==================== GRID NETWORK ====================

class GridNetwork:
    """Red de grilla para movimiento de taxis y pasajeros"""
    
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.intersections: Set[GridPosition] = set()
        self._generate_intersections()
        
        logger.info(f"Grid network created: {width}x{height} with {len(self.intersections)} intersections")
    
    def _generate_intersections(self):
        """Genera todas las intersecciones de la grilla"""
        for x in range(self.width):
            for y in range(self.height):
                self.intersections.add(GridPosition(x, y))
    
    def get_random_intersection(self) -> GridPosition:
        """Obtiene una intersección aleatoria"""
        return random.choice(list(self.intersections))
    
    def get_adjacent_positions(self, pos: GridPosition) -> List[GridPosition]:
        """Obtiene posiciones adyacentes válidas (solo horizontal/vertical)"""
        adjacent = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # N, S, E, W
        
        for dx, dy in directions:
            new_x, new_y = pos.x + dx, pos.y + dy
            if 0 <= new_x < self.width and 0 <= new_y < self.height:
                adjacent.append(GridPosition(new_x, new_y))
        
        return adjacent
    
    def is_valid_position(self, pos: GridPosition) -> bool:
        """Verifica si una posición es válida"""
        return pos in self.intersections
    
    def get_path(self, start: GridPosition, end: GridPosition) -> List[GridPosition]:
        """Calcula ruta usando pathfinding Manhattan simple"""
        if start == end:
            return [start]
        
        path = [start]
        current = GridPosition(start.x, start.y)
        
        # Simple pathfinding: moverse primero horizontalmente, luego verticalmente
        while current.x != end.x:
            if current.x < end.x:
                current.x += 1
            else:
                current.x -= 1
            path.append(GridPosition(current.x, current.y))
        
        while current.y != end.y:
            if current.y < end.y:
                current.y += 1
            else:
                current.y -= 1
            path.append(GridPosition(current.x, current.y))
        
        return path

# ==================== CONSTRAINT PROGRAMMING SOLVER ====================

class ConstraintSolver:
    """Solver de constraint programming para asignación óptima"""
    
    def __init__(self):
        self.max_pickup_distance = 15  # Distancia máxima para pickup
        self.wait_time_penalty = 2     # Penalización por tiempo de espera
        
    def solve_assignment(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Resuelve el problema de asignación taxi-pasajero
        Retorna: {taxi_id: passenger_id}
        """
        # Filtrar taxis disponibles y pasajeros esperando
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in passengers if p.state == PassengerState.WAITING]
        
        if not available_taxis or not waiting_passengers:
            return {}
        
        logger.info(f"Solving assignment: {len(available_taxis)} taxis, {len(waiting_passengers)} passengers")
        
        if OR_TOOLS_AVAILABLE:
            try:
                return self._solve_with_ortools(available_taxis, waiting_passengers)
            except Exception as e:
                logger.warning(f"OR-Tools failed, using fallback: {e}")
                return self._greedy_fallback(available_taxis, waiting_passengers)
        else:
            return self._greedy_fallback(available_taxis, waiting_passengers)
    
    def _solve_with_ortools(self, taxis: List[TaxiInfo], 
                           passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Solver usando OR-Tools constraint programming"""
        solver = pywrapcp.Solver("TaxiAssignment")
        
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        
        # Variables de decisión: assignment[i][j] = 1 si taxi i asignado a pasajero j
        assignment = {}
        for i in range(n_taxis):
            assignment[i] = {}
            for j in range(n_passengers):
                assignment[i][j] = solver.IntVar(0, 1, f"assign_{i}_{j}")
        
        # Restricción: cada taxi asignado a máximo un pasajero
        for i in range(n_taxis):
            solver.Add(solver.Sum([assignment[i][j] for j in range(n_passengers)]) <= 1)
        
        # Restricción: cada pasajero asignado a máximo un taxi
        for j in range(n_passengers):
            solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) <= 1)
        
        # Restricciones de capacidad y distancia
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                
                # Capacidad disponible
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                
                # Distancia máxima
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    solver.Add(assignment[i][j] == 0)
        
        # Función objetivo: minimizar costo total
        cost_terms = []
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                
                # Costo = distancia + penalización por tiempo de espera
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                wait_penalty = int(passenger.wait_time * self.wait_time_penalty)
                total_cost = distance + wait_penalty
                
                cost_terms.append(assignment[i][j] * total_cost)
        
        objective = solver.Minimize(solver.Sum(cost_terms), 1)
        
        # Resolver
        decision_builder = solver.Phase(
            [assignment[i][j] for i in range(n_taxis) for j in range(n_passengers)],
            solver.CHOOSE_FIRST_UNBOUND,
            solver.ASSIGN_MIN_VALUE
        )
        
        solver.NewSearch(decision_builder, [objective])
        
        assignments = {}
        if solver.NextSolution():
            for i in range(n_taxis):
                for j in range(n_passengers):
                    if assignment[i][j].Value() == 1:
                        assignments[taxis[i].taxi_id] = passengers[j].passenger_id
                        distance = taxis[i].position.manhattan_distance(passengers[j].pickup_position)
                        logger.info(f"OR-Tools assignment: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (distance: {distance})")
        
        solver.EndSearch()
        return assignments
    
    def _greedy_fallback(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Algoritmo greedy como fallback"""
        assignments = {}
        assigned_taxis = set()
        
        # Ordenar pasajeros por tiempo de espera (mayor primero)
        passengers_sorted = sorted(passengers, key=lambda p: p.wait_time, reverse=True)
        
        for passenger in passengers_sorted:
            best_taxi = None
            best_score = float('inf')
            
            for taxi in taxis:
                if taxi.taxi_id in assigned_taxis:
                    continue
                
                if taxi.current_passengers >= taxi.capacity:
                    continue
                
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    continue
                
                # Score = distancia + penalización por tiempo de espera
                score = distance + passenger.wait_time * self.wait_time_penalty
                
                if score < best_score:
                    best_score = score
                    best_taxi = taxi
            
            if best_taxi:
                assignments[best_taxi.taxi_id] = passenger.passenger_id
                assigned_taxis.add(best_taxi.taxi_id)
                logger.info(f"Greedy assignment: {best_taxi.taxi_id} -> {passenger.passenger_id} (score: {best_score:.1f})")
        
        return assignments

# ==================== TAXI AGENT ====================

class TaxiAgent(Agent):
    """Agente taxi que se comunica vía SPADE/OpenFire"""
    
    def __init__(self, jid: str, password: str, taxi_id: str, 
                 initial_position: GridPosition, grid: GridNetwork):
        super().__init__(jid, password)
        self.taxi_id = taxi_id
        self.grid = grid
        self.info = TaxiInfo(
            taxi_id=taxi_id,
            position=initial_position,
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None
        )
        self.last_update = time.time()
        self.path: List[GridPosition] = []
        self.path_index = 0
        
        logger.info(f"Taxi agent {taxi_id} created at position ({initial_position.x}, {initial_position.y})")
    
    async def setup(self):
        """Configuración inicial del agente"""
        logger.info(f"Setting up taxi agent {self.taxi_id}")
        
        # Comportamiento de movimiento
        movement_behaviour = self.MovementBehaviour(period=0.5)  # 2 FPS
        self.add_behaviour(movement_behaviour)
        
        # Comportamiento de comunicación
        comm_behaviour = self.CommunicationBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(comm_behaviour, template)
        
        # Comportamiento de reporte de estado
        status_behaviour = self.StatusReportBehaviour(period=1.0)
        self.add_behaviour(status_behaviour)
    
    class MovementBehaviour(PeriodicBehaviour):
        """Maneja el movimiento del taxi"""
        
        async def run(self):
            agent = self.agent
            
            if agent.info.state == TaxiState.IDLE:
                # Movimiento aleatorio de patrullaje
                agent._patrol_movement()
            
            elif agent.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]:
                # Movimiento hacia objetivo
                agent._move_towards_target()
    
    class CommunicationBehaviour(CyclicBehaviour):
        """Maneja comunicación XMPP"""
        
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                await self.agent._handle_message(msg)
    
    class StatusReportBehaviour(PeriodicBehaviour):
        """Reporta estado al coordinador"""
        
        async def run(self):
            coordinator_jid = f"coordinator@{config.openfire_domain}"
            msg = Message(to=coordinator_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", "status_report")
            msg.body = json.dumps(asdict(self.agent.info))
            await self.send(msg)
    
    def _patrol_movement(self):
        """Movimiento aleatorio de patrullaje"""
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
        if not self.info.target_position:
            return
        
        if not self.path or self.path_index >= len(self.path):
            # Calcular nuevo path hacia el objetivo
            self.path = self.grid.get_path(self.info.position, self.info.target_position)
            self.path_index = 0
        
        # Mover al siguiente punto en el path
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.info.position = self.path[self.path_index]
            
            # Verificar si llegamos al objetivo
            if self.info.position == self.info.target_position:
                await self._handle_arrival()
    
    async def _handle_arrival(self):
        """Maneja llegada al objetivo"""
        if self.info.state == TaxiState.PICKUP:
            # Llegamos a recoger pasajero
            self.info.state = TaxiState.DROPOFF
            self.info.current_passengers += 1
            logger.info(f"Taxi {self.taxi_id} picked up passenger {self.info.assigned_passenger_id}")
            
            # Notificar al coordinador
            await self._notify_coordinator("passenger_picked_up")
            
        elif self.info.state == TaxiState.DROPOFF:
            # Llegamos a entregar pasajero
            self.info.state = TaxiState.IDLE
            self.info.current_passengers = 0
            self.info.target_position = None
            passenger_id = self.info.assigned_passenger_id
            self.info.assigned_passenger_id = None
            
            logger.info(f"Taxi {self.taxi_id} delivered passenger {passenger_id}")
            
            # Notificar al coordinador
            await self._notify_coordinator("passenger_delivered", {"passenger_id": passenger_id})
    
    async def _notify_coordinator(self, event_type: str, data: Dict = None):
        """Notifica eventos al coordinador"""
        coordinator_jid = f"coordinator@{config.openfire_domain}"
        msg = Message(to=coordinator_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("type", event_type)
        
        payload = {"taxi_id": self.taxi_id}
        if data:
            payload.update(data)
        
        msg.body = json.dumps(payload)
        await self.send(msg)
    
    async def _handle_message(self, msg: Message):
        """Maneja mensajes recibidos"""
        msg_type = msg.get_metadata("type")
        
        if msg_type == "assignment":
            # Asignación de pasajero
            data = json.loads(msg.body)
            passenger_id = data["passenger_id"]
            pickup_pos = GridPosition(data["pickup_x"], data["pickup_y"])
            dropoff_pos = GridPosition(data["dropoff_x"], data["dropoff_y"])
            
            self.info.assigned_passenger_id = passenger_id
            self.info.target_position = pickup_pos
            self.info.state = TaxiState.PICKUP
            
            logger.info(f"Taxi {self.taxi_id} assigned to passenger {passenger_id}")

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
        
        # Comportamiento de asignación
        assignment_behaviour = self.AssignmentBehaviour(period=2.0)
        self.add_behaviour(assignment_behaviour)
        
        # Comportamiento de comunicación
        comm_behaviour = self.CommunicationBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(comm_behaviour, template)
        
        # Generar pasajeros iniciales
        self._generate_initial_passengers()
    
    class AssignmentBehaviour(PeriodicBehaviour):
        """Maneja las asignaciones usando constraint programming"""
        
        async def run(self):
            coordinator = self.agent
            
            if not coordinator.taxis or not coordinator.passengers:
                return
            
            # Obtener listas actuales
            taxi_list = list(coordinator.taxis.values())
            passenger_list = [p for p in coordinator.passengers.values() 
                            if p.state == PassengerState.WAITING]
            
            if not passenger_list:
                return
            
            # Resolver asignaciones
            assignments = coordinator.solver.solve_assignment(taxi_list, passenger_list)
            
            # Enviar asignaciones a taxis
            for taxi_id, passenger_id in assignments.items():
                await coordinator._send_assignment(taxi_id, passenger_id)
    
    class CommunicationBehaviour(CyclicBehaviour):
        """Maneja comunicación con taxis"""
        
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                await self.agent._handle_message(msg)
    
    def _generate_initial_passengers(self):
        """Genera 4 pasajeros iniciales"""
        for i in range(4):
            self._create_new_passenger()
    
    def _create_new_passenger(self):
        """Crea un nuevo pasajero"""
        passenger_id = f"P{self.passenger_counter}"
        self.passenger_counter += 1
        
        pickup = self.grid.get_random_intersection()
        dropoff = self.grid.get_random_intersection()
        
        # Asegurar distancia mínima razonable
        while pickup.manhattan_distance(dropoff) < 5:
            dropoff = self.grid.get_random_intersection()
        
        passenger = PassengerInfo(
            passenger_id=passenger_id,
            pickup_position=pickup,
            dropoff_position=dropoff,
            state=PassengerState.WAITING,
            wait_time=0.0
        )
        
        self.passengers[passenger_id] = passenger
        logger.info(f"Created passenger {passenger_id} at ({pickup.x}, {pickup.y}) -> ({dropoff.x}, {dropoff.y})")
    
    async def _send_assignment(self, taxi_id: str, passenger_id: str):
        """Envía asignación a un taxi"""
        if passenger_id not in self.passengers:
            return
        
        passenger = self.passengers[passenger_id]
        
        taxi_jid = f"taxi_{taxi_id}@{config.openfire_domain}"
        msg = Message(to=taxi_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("type", "assignment")
        
        data = {
            "passenger_id": passenger_id,
            "pickup_x": passenger.pickup_position.x,
            "pickup_y": passenger.pickup_position.y,
            "dropoff_x": passenger.dropoff_position.x,
            "dropoff_y": passenger.dropoff_position.y
        }
        
        msg.body = json.dumps(data)
        await self.send(msg)
        
        # Actualizar estados
        passenger.state = PassengerState.PICKED_UP
        passenger.assigned_taxi_id = taxi_id
        
        if taxi_id in self.taxis:
            self.taxis[taxi_id].state = TaxiState.ASSIGNED
        
        logger.info(f"Sent assignment: {taxi_id} -> {passenger_id}")
    
    async def _handle_message(self, msg: Message):
        """Maneja mensajes de taxis"""
        msg_type = msg.get_metadata("type")
        
        if msg_type == "status_report":
            # Actualizar estado de taxi
            data = json.loads(msg.body)
            taxi_info = TaxiInfo(**data)
            self.taxis[taxi_info.taxi_id] = taxi_info
            
        elif msg_type == "passenger_delivered":
            # Pasajero entregado, crear nuevo pasajero
            data = json.loads(msg.body)
            passenger_id = data["passenger_id"]
            
            if passenger_id in self.passengers:
                self.passengers[passenger_id].state = PassengerState.DELIVERED
                del self.passengers[passenger_id]
            
            # Crear nuevo pasajero
            self._create_new_passenger()
    
    def update_passenger_wait_times(self, dt: float):
        """Actualiza tiempos de espera de pasajeros"""
        for passenger in self.passengers.values():
            if passenger.state == PassengerState.WAITING:
                passenger.wait_time += dt

# El resto del código continuará en la siguiente parte...
