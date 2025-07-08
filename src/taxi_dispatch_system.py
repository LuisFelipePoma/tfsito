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
        assignment_interval = 2.0
        movement_update_interval = 0.5
        status_report_interval = 1.0
    
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
    is_disabled: bool = False  # Prioridad: discapacidad
    is_elderly: bool = False   # Prioridad: adulto mayor
    is_child: bool = False     # Prioridad: niño
    is_pregnant: bool = False  # Prioridad: embarazada
    price: float = 10.0        # Precio ofrecido

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
        
    def solve_assignment(self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Resuelve el problema de asignación taxi-pasajero
        Retorna: {taxi_id: passenger_id}
        """
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in passengers if p.state == PassengerState.WAITING]
        if not available_taxis or not waiting_passengers:
            return {}
        logger.info(f"Solving assignment: {len(available_taxis)} taxis, {len(waiting_passengers)} passengers")
        if OR_TOOLS_AVAILABLE:
            try:
                return self._solve_with_ortools_realistic(available_taxis, waiting_passengers)
            except Exception as e:
                logger.warning(f"OR-Tools failed, using fallback: {e}")
                return self._greedy_fallback_realistic(available_taxis, waiting_passengers)
        else:
            return self._greedy_fallback_realistic(available_taxis, waiting_passengers)

    def _passenger_vulnerability(self, p: PassengerInfo) -> bool:
        return p.is_disabled or p.is_elderly or p.is_child or p.is_pregnant

    def _zone_demand_score(self, pos: GridPosition) -> int:
        # Ejemplo: zonas de alta demanda (puedes personalizar)
        # Aquí, las esquinas y el centro tienen más demanda
        center_x, center_y = config.grid_width // 2, config.grid_height // 2
        if (abs(pos.x - center_x) <= 2 and abs(pos.y - center_y) <= 2):
            return 2  # Centro: alta demanda
        if (pos.x < 3 or pos.x > config.grid_width - 4 or pos.y < 3 or pos.y > config.grid_height - 4):
            return 1  # Esquinas: demanda media
        return 0  # Resto: baja demanda

    def _solve_with_ortools_realistic(self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Solver usando OR-Tools con restricciones realistas:
        - Prioridad absoluta a vulnerables
        - Maximizar ganancia por minuto/km
        - Prioridad a mayor tiempo de espera
        - Prioridad a zonas de alta demanda
        - Minimizar ETA
        """
        solver = pywrapcp.Solver("TaxiAssignmentRealistic")
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        assignment = {}
        for i in range(n_taxis):
            assignment[i] = {}
            for j in range(n_passengers):
                assignment[i][j] = solver.IntVar(0, 1, f"assign_{i}_{j}")
        # Restricción: cada taxi a máximo un pasajero
        for i in range(n_taxis):
            solver.Add(solver.Sum([assignment[i][j] for j in range(n_passengers)]) <= 1)
        # Restricción: cada pasajero a máximo un taxi
        for j in range(n_passengers):
            solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) <= 1)
        # Restricciones de capacidad y distancia
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    solver.Add(assignment[i][j] == 0)
        # Prioridad absoluta: vulnerables
        for j in range(n_passengers):
            passenger = passengers[j]
            if self._passenger_vulnerability(passenger):
                solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) >= 1)
        # Función objetivo realista
        cost_terms = []
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                pickup_dist = taxi.position.manhattan_distance(passenger.pickup_position)
                trip_dist = passenger.pickup_position.manhattan_distance(passenger.dropoff_position)
                eta = pickup_dist / max(taxi.speed, 0.1)
                wait_penalty = -int(passenger.wait_time)  # Más espera, menor penalización
                demand_score = self._zone_demand_score(passenger.dropoff_position)
                # Ganancia por km/min
                gain_per_km = passenger.price / max(trip_dist, 1)
                # Vulnerabilidad: gran prioridad negativa (OR-Tools minimiza)
                vulnerability = -10000 if self._passenger_vulnerability(passenger) else 0
                # Costo total: combina criterios
                cost = (
                    pickup_dist * 5  # Minimizar ETA
                    - int(gain_per_km * 100)  # Maximizar ganancia/km
                    + eta * 2  # Minimizar ETA
                    - demand_score * 50  # Prioridad a zonas de demanda
                    + wait_penalty * 3  # Prioridad a más espera
                    + vulnerability  # Prioridad absoluta a vulnerables
                )
                cost_terms.append(assignment[i][j] * int(cost))
        objective = solver.Minimize(solver.Sum(cost_terms), 1)
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
                        logger.info(f"OR-Tools assignment: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (dist: {taxis[i].position.manhattan_distance(passengers[j].pickup_position)}, price: {passengers[j].price}, vulnerable: {self._passenger_vulnerability(passengers[j])})")
        solver.EndSearch()
        return assignments

    def _greedy_fallback_realistic(self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Algoritmo greedy realista: vulnerables primero, luego ganancia/km, espera, demanda, ETA
        """
        assignments = {}
        assigned_passengers = set()
        def passenger_score(p, taxi):
            pickup_dist = taxi.position.manhattan_distance(p.pickup_position)
            trip_dist = p.pickup_position.manhattan_distance(p.dropoff_position)
            eta = pickup_dist / max(taxi.speed, 0.1)
            gain_per_km = p.price / max(trip_dist, 1)
            demand_score = self._zone_demand_score(p.dropoff_position)
            vulnerability = -10000 if self._passenger_vulnerability(p) else 0
            wait_penalty = -int(p.wait_time)
            # Menor score es mejor
            return (
                vulnerability,
                -gain_per_km,
                wait_penalty,
                -demand_score,
                eta,
                pickup_dist
            )
        for taxi in taxis:
            best_p = None
            best_score = (float('inf'),)*6
            for p in passengers:
                if p.state != PassengerState.WAITING:
                    continue
                if p.passenger_id in assigned_passengers:
                    continue
                if taxi.current_passengers >= taxi.capacity:
                    continue
                pickup_dist = taxi.position.manhattan_distance(p.pickup_position)
                if pickup_dist > self.max_pickup_distance:
                    continue
                score = passenger_score(p, taxi)
                if score < best_score:
                    best_score = score
                    best_p = p
            if best_p:
                assignments[taxi.taxi_id] = best_p.passenger_id
                assigned_passengers.add(best_p.passenger_id)
                logger.info(f"Greedy assignment: {taxi.taxi_id} -> {best_p.passenger_id} (dist: {taxi.position.manhattan_distance(best_p.pickup_position)}, price: {best_p.price}, vulnerable: {self._passenger_vulnerability(best_p)})")
        return assignments
    
    def _solve_with_ortools(self, taxis: List[TaxiInfo], 
                           passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Solver usando OR-Tools con prioridad a discapacitados y maximizar ganancia"""
        solver = pywrapcp.Solver("TaxiAssignment")
        n_taxis = len(taxis)
        n_passengers = len(passengers)
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
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    solver.Add(assignment[i][j] == 0)
        # Prioridad: discapacitados primero
        for j in range(n_passengers):
            passenger = passengers[j]
            if passenger.is_disabled:
                # Al menos un taxi debe intentar tomarlo si hay taxis libres
                solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) >= 1)
        # Función objetivo: maximizar suma de precios (con gran peso a discapacitados), minimizar distancia
        cost_terms = []
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                # Penalización fuerte si no es discapacitado (para que discapacitados tengan prioridad)
                priority = 1000 if passenger.is_disabled else 0
                # Maximizar precio, pero prioridad a discapacitado
                # Como OR-Tools minimiza, restamos el precio (maximizar)
                cost = distance - int(passenger.price * 10) - priority
                cost_terms.append(assignment[i][j] * cost)
        objective = solver.Minimize(solver.Sum(cost_terms), 1)
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
                        logger.info(f"OR-Tools assignment: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (dist: {taxis[i].position.manhattan_distance(passengers[j].pickup_position)}, price: {passengers[j].price}, disabled: {passengers[j].is_disabled})")
        solver.EndSearch()
        return assignments
    
    def _greedy_fallback(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Algoritmo greedy: prioridad discapacitado, luego precio, luego distancia"""
        assignments = {}
        assigned_taxis = set()
        # Ordenar pasajeros: discapacitados primero, luego mayor precio, luego menor distancia
        def passenger_priority(p, taxi):
            distance = taxi.position.manhattan_distance(p.pickup_position)
            return (-int(p.is_disabled), -p.price, distance)
        for taxi in taxis:
            best_passenger = None
            best_score = (1, 0, float('inf'))
            for passenger in passengers:
                if passenger.state != PassengerState.WAITING:
                    continue
                if passenger.passenger_id in assignments.values():
                    continue
                if taxi.current_passengers >= taxi.capacity:
                    continue
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    continue
                score = passenger_priority(passenger, taxi)
                if score < best_score:
                    best_score = score
                    best_passenger = passenger
            if best_passenger:
                assignments[taxi.taxi_id] = best_passenger.passenger_id
                logger.info(f"Greedy assignment: {taxi.taxi_id} -> {best_passenger.passenger_id} (dist: {taxi.position.manhattan_distance(best_passenger.pickup_position)}, price: {best_passenger.price}, disabled: {best_passenger.is_disabled})")
        return assignments

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
        self.dropoff_position: Optional[GridPosition] = None  # Para guardar destino del pasajero
        
        logger.info(f"Taxi agent {taxi_id} created at position ({initial_position.x}, {initial_position.y})")
    
    async def setup(self):
        """Configuración inicial del agente"""
        logger.info(f"Setting up taxi agent {self.taxi_id}")
        
        # Comportamiento de movimiento - más frecuente para respuesta rápida
        movement_behaviour = self.MovementBehaviour(period=config.movement_update_interval)
        self.add_behaviour(movement_behaviour)
        
        # Comportamiento de comunicación
        comm_behaviour = self.CommunicationBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(comm_behaviour, template)
        
        # Comportamiento de reporte de estado - más frecuente para sincronización
        status_behaviour = self.StatusReportBehaviour(period=config.status_report_interval)
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
                arrived = agent._move_towards_target()
                if arrived:
                    await self._handle_arrival()
        
        async def _handle_arrival(self):
            """Maneja llegada al objetivo desde el comportamiento"""
            agent = self.agent
            if agent.info.state == TaxiState.PICKUP:
                # Llegamos a recoger pasajero
                agent.info.state = TaxiState.DROPOFF
                agent.info.current_passengers += 1
                
                # Cambiar target al destino del pasajero
                if agent.dropoff_position:
                    agent.info.target_position = agent.dropoff_position
                    logger.info(f"Taxi {agent.taxi_id} picked up passenger {agent.info.assigned_passenger_id}, heading to ({agent.dropoff_position.x}, {agent.dropoff_position.y})")
                else:
                    logger.error(f"Taxi {agent.taxi_id} picked up passenger but no dropoff position saved!")
                    
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
                await self._notify_coordinator("passenger_delivered", {"passenger_id": passenger_id})
        
        async def _notify_coordinator(self, event_type: str, data: Optional[Dict] = None):
            """Notifica eventos al coordinador desde el comportamiento"""
            agent = self.agent
            coordinator_jid = f"coordinator@{config.openfire_domain}"
            msg = Message(to=coordinator_jid)
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
            # Usar función serializadora para enums
            serializable_info = self.agent._to_serializable_dict(self.agent.info)
            msg.body = json.dumps(serializable_info)
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
            logger.warning(f"Taxi {self.taxi_id} in state {self.info.state.value} but no target position")
            return False
            
        # Verificar si ya estamos en el target
        if self.info.position == self.info.target_position:
            logger.info(f"Taxi {self.taxi_id} already at target ({self.info.target_position.x}, {self.info.target_position.y})")
            return True
            
        if not self.path or self.path_index >= len(self.path):
            # Calcular nuevo path hacia el objetivo
            self.path = self.grid.get_path(self.info.position, self.info.target_position)
            self.path_index = 0
            logger.info(f"Taxi {self.taxi_id} calculated new path to ({self.info.target_position.x}, {self.info.target_position.y}), path length: {len(self.path)}")
            
        # Mover al siguiente punto en el path
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            new_pos = self.path[self.path_index]
            logger.debug(f"Taxi {self.taxi_id} moving from ({self.info.position.x}, {self.info.position.y}) to ({new_pos.x}, {new_pos.y})")
            self.info.position = new_pos
            
            # Verificar si llegamos al objetivo
            if self.info.position == self.info.target_position:
                logger.info(f"Taxi {self.taxi_id} arrived at target ({self.info.target_position.x}, {self.info.target_position.y})")
                return True
        else:
            # Ya estamos en el último punto del path
            logger.info(f"Taxi {self.taxi_id} reached end of path at ({self.info.position.x}, {self.info.position.y})")
            return True
                
        return False
    
    async def _handle_message(self, msg: Message):
        """Maneja mensajes recibidos"""
        if not msg or not msg.body:
            logger.warning(f"Taxi {self.taxi_id} received empty message")
            return
            
        try:
            msg_type = msg.get_metadata("type")
            logger.info(f"Taxi {self.taxi_id} received message type: {msg_type}")
            
            if msg_type == "assignment":
                # Asignación de pasajero
                data = json.loads(msg.body)
                passenger_id = data["passenger_id"]
                pickup_pos = GridPosition(data["pickup_x"], data["pickup_y"])
                dropoff_pos = GridPosition(data["dropoff_x"], data["dropoff_y"])
                
                # Actualizar estado del taxi
                self.info.assigned_passenger_id = passenger_id
                self.info.target_position = pickup_pos
                self.info.state = TaxiState.PICKUP
                
                # Guardar posición de destino para después del pickup
                self.dropoff_position = dropoff_pos
                
                # Resetear path para forzar recálculo
                self.path = []
                self.path_index = 0
                
                logger.info(f"Taxi {self.taxi_id} assigned to passenger {passenger_id} at ({pickup_pos.x}, {pickup_pos.y}) -> ({dropoff_pos.x}, {dropoff_pos.y})")
                
        except Exception as e:
            logger.error(f"Error handling message in taxi {self.taxi_id}: {e}")
            logger.error(f"Message body: {msg.body}")
            logger.error(f"Message metadata: {msg.metadata}")

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
        assignment_behaviour = self.AssignmentBehaviour(period=config.assignment_interval)
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
                await self._send_assignment_message(taxi_id, passenger_id)
        
        async def _send_assignment_message(self, taxi_id: str, passenger_id: str):
            """Envía mensaje de asignación a un taxi (desde el comportamiento)"""
            coordinator = self.agent
            
            if passenger_id not in coordinator.passengers:
                logger.warning(f"Passenger {passenger_id} not found for assignment")
                return
                
            passenger = coordinator.passengers[passenger_id]
            
            # Construir JID del taxi correctamente
            taxi_jid = f"{taxi_id}@{config.openfire_domain}"
            
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
            
            # Marcar asignación pendiente
            passenger.assigned_taxi_id = taxi_id
            
            logger.info(f"Sent assignment: {taxi_id} -> {passenger_id} at ({passenger.pickup_position.x}, {passenger.pickup_position.y}) -> ({passenger.dropoff_position.x}, {passenger.dropoff_position.y})")
    
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
    
    def _create_new_passenger(self, is_disabled=False, is_elderly=False, is_child=False, is_pregnant=False, price=10.0):
        """Crea un nuevo pasajero con opciones de discapacidad y precio"""
        passenger_id = f"P{self.passenger_counter}"
        self.passenger_counter += 1
        
        # Generar posiciones aleatorias con distancia mínima
        pickup = self.grid.get_random_intersection()
        dropoff = self.grid.get_random_intersection()
        
        # Asegurar distancia mínima entre pickup y dropoff
        max_attempts = 10
        attempts = 0
        while pickup.manhattan_distance(dropoff) < 5 and attempts < max_attempts:
            dropoff = self.grid.get_random_intersection()
            attempts += 1
        
        # Determinar prioridades y precio aleatorio
        if not any([is_disabled, is_elderly, is_child, is_pregnant]):
            # Asignar aleatoriamente algunas prioridades
            import random
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
            price=price
        )
        
        self.passengers[passenger_id] = passenger
        
        # Log detallado
        priorities = []
        if is_disabled: priorities.append("DISABLED")
        if is_elderly: priorities.append("ELDERLY")
        if is_child: priorities.append("CHILD")
        if is_pregnant: priorities.append("PREGNANT")
        
        priority_str = f" [{', '.join(priorities)}]" if priorities else ""
        logger.info(f"Created passenger {passenger_id}{priority_str} at ({pickup.x}, {pickup.y}) -> ({dropoff.x}, {dropoff.y}), price: S/{price:.2f}")
        
        return passenger
    
    async def _handle_message(self, msg: Message):
        """Maneja mensajes de taxis"""
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
                    position = GridPosition(position_data.get("x", 0), position_data.get("y", 0))
                else:
                    position = GridPosition(0, 0)
                
                target_position = None
                target_data = data.get("target_position")
                if target_data and isinstance(target_data, dict):
                    target_position = GridPosition(target_data.get("x", 0), target_data.get("y", 0))
                
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
                    speed=data.get("speed", 1.0)
                )
                
                self.taxis[taxi_info.taxi_id] = taxi_info
                
            elif msg_type == "passenger_picked_up":
                # Taxi notifica que recogió pasajero
                data = json.loads(msg.body)
                taxi_id = data.get("taxi_id")
                if taxi_id:
                    # Buscar pasajero asignado a este taxi
                    for p in self.passengers.values():
                        if p.assigned_taxi_id == taxi_id and p.state == PassengerState.WAITING:
                            p.state = PassengerState.PICKED_UP
                            logger.info(f"Passenger {p.passenger_id} picked up by taxi {taxi_id}")
                            break
                            
            elif msg_type == "passenger_delivered":
                # Pasajero entregado, crear nuevo pasajero
                data = json.loads(msg.body)
                passenger_id = data.get("passenger_id")
                if passenger_id and passenger_id in self.passengers:
                    self.passengers[passenger_id].state = PassengerState.DELIVERED
                    del self.passengers[passenger_id]
                    logger.info(f"Passenger {passenger_id} delivered successfully")
                # Crear nuevo pasajero
                self._create_new_passenger()
                
        except Exception as e:
            logger.error(f"Error handling message in coordinator: {e}")
            logger.error(f"Message body: {msg.body}")
            logger.error(f"Message metadata: {msg.metadata}")
    
    def update_passenger_wait_times(self, dt: float):
        """Actualiza tiempos de espera de pasajeros"""
        for passenger in self.passengers.values():
            if passenger.state == PassengerState.WAITING:
                passenger.wait_time += dt

# El resto del código continuará en la siguiente parte...
