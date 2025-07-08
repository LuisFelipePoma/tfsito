"""
Sistema Completo de Despacho de Taxis con Constraint Programming
==============================================================

Sistema distribuido funcional con:
- Constraint programming (OR-Tools con fallback)
- OpenFire/SPADE para comunicación (opcional)
- Mapa de grilla con movimiento Manhattan
- GUI completa con Tkinter
- 3 taxis, 4 pasajeros iniciales

Requisitos: Python 3.7+, tkinter (incluido), ortools (opcional)
"""

import asyncio
import json
import logging
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
import datetime

# Constraint programming import (opcional)
try:
    from ortools.constraint_solver import pywrapcp
    OR_TOOLS_AVAILABLE = True
    print("✅ OR-Tools disponible para constraint programming")
except ImportError:
    OR_TOOLS_AVAILABLE = False
    print("⚠️ OR-Tools no disponible, usando algoritmo greedy")

# SPADE import (opcional)
try:
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
    from spade.message import Message
    from spade.template import Template
    SPADE_AVAILABLE = True
    print("✅ SPADE disponible para comunicación distribuida")
except ImportError:
    SPADE_AVAILABLE = False
    print("⚠️ SPADE no disponible, modo local")

# Configuración del sistema
@dataclass
class Config:
    """Configuración del sistema"""
    grid_width: int = 20
    grid_height: int = 20
    gui_width: int = 1200
    gui_height: int = 800
    grid_cell_size: int = 25
    fps: int = 20
    num_taxis: int = 3
    initial_passengers: int = 4
    assignment_interval: float = 2.0  # segundos
    max_pickup_distance: int = 15
    
config = Config()

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== ESTRUCTURAS DE DATOS ====================

class TaxiState(Enum):
    """Estados del taxi"""
    IDLE = "idle"           # Patrullando
    PICKUP = "pickup"       # Yendo por pasajero
    DROPOFF = "dropoff"     # Llevando pasajero

class PassengerState(Enum):
    """Estados del pasajero"""
    WAITING = "waiting"     # Esperando
    PICKED_UP = "picked_up" # En taxi
    DELIVERED = "delivered" # Entregado

@dataclass
class GridPosition:
    """Posición en grilla"""
    x: int
    y: int
    
    def manhattan_distance(self, other: 'GridPosition') -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def __eq__(self, other):
        return isinstance(other, GridPosition) and self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))

@dataclass
class TaxiInfo:
    """Información del taxi"""
    taxi_id: str
    position: GridPosition
    target_position: Optional[GridPosition]
    state: TaxiState
    capacity: int
    current_passengers: int
    assigned_passenger_id: Optional[str]

@dataclass
class PassengerInfo:
    """Información del pasajero"""
    passenger_id: str
    pickup_position: GridPosition
    dropoff_position: GridPosition
    state: PassengerState
    wait_time: float
    assigned_taxi_id: Optional[str] = None

# ==================== GRID NETWORK ====================

class GridNetwork:
    """Red de grilla para movimiento"""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.intersections = set()
        self._generate_grid()
    
    def _generate_grid(self):
        """Genera intersecciones"""
        for x in range(self.width):
            for y in range(self.height):
                self.intersections.add(GridPosition(x, y))
    
    def get_random_intersection(self) -> GridPosition:
        """Intersección aleatoria"""
        return random.choice(list(self.intersections))
    
    def get_adjacent_positions(self, pos: GridPosition) -> List[GridPosition]:
        """Posiciones adyacentes (solo cardinales)"""
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_pos = GridPosition(pos.x + dx, pos.y + dy)
            if 0 <= new_pos.x < self.width and 0 <= new_pos.y < self.height:
                adjacent.append(new_pos)
        return adjacent
    
    def get_path(self, start: GridPosition, end: GridPosition) -> List[GridPosition]:
        """Pathfinding Manhattan simple"""
        if start == end:
            return [start]
        
        path = [start]
        current = GridPosition(start.x, start.y)
        
        # Moverse horizontalmente primero, luego verticalmente
        while current.x != end.x:
            current.x += 1 if current.x < end.x else -1
            path.append(GridPosition(current.x, current.y))
        
        while current.y != end.y:
            current.y += 1 if current.y < end.y else -1
            path.append(GridPosition(current.x, current.y))
        
        return path

# ==================== CONSTRAINT SOLVER ====================

class ConstraintSolver:
    """Solver para asignación óptima"""
    
    def __init__(self):
        self.max_pickup_distance = config.max_pickup_distance
        self.wait_penalty = 2.0
    
    def solve_assignment(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Resuelve asignación taxi-pasajero
        Returns: {taxi_id: passenger_id}
        """
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in passengers if p.state == PassengerState.WAITING]
        
        if not available_taxis or not waiting_passengers:
            return {}
        
        logger.info(f"Solving assignment: {len(available_taxis)} taxis, {len(waiting_passengers)} passengers")
        
        if OR_TOOLS_AVAILABLE:
            try:
                return self._solve_with_ortools(available_taxis, waiting_passengers)
            except Exception as e:
                logger.warning(f"OR-Tools failed: {e}, using greedy")
                return self._greedy_fallback(available_taxis, waiting_passengers)
        else:
            return self._greedy_fallback(available_taxis, waiting_passengers)
    
    def _solve_with_ortools(self, taxis: List[TaxiInfo], 
                           passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Constraint programming con OR-Tools"""
        solver = pywrapcp.Solver("TaxiAssignment")
        
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        
        # Variables de decisión
        assignment = {}
        for i in range(n_taxis):
            assignment[i] = {}
            for j in range(n_passengers):
                assignment[i][j] = solver.IntVar(0, 1, f"assign_{i}_{j}")
        
        # Restricciones
        # Cada taxi asignado a máximo un pasajero
        for i in range(n_taxis):
            solver.Add(solver.Sum([assignment[i][j] for j in range(n_passengers)]) <= 1)
        
        # Cada pasajero asignado a máximo un taxi
        for j in range(n_passengers):
            solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) <= 1)
        
        # Restricciones de capacidad y distancia
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                
                # Capacidad
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
                
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                wait_penalty = int(passenger.wait_time * self.wait_penalty)
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
                        logger.info(f"OR-Tools: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (dist: {distance})")
        
        solver.EndSearch()
        return assignments
    
    def _greedy_fallback(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Algoritmo greedy como fallback"""
        assignments = {}
        assigned_taxis = set()
        
        # Ordenar pasajeros por tiempo de espera (mayor primero)
        sorted_passengers = sorted(passengers, key=lambda p: p.wait_time, reverse=True)
        
        for passenger in sorted_passengers:
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
                
                score = distance + passenger.wait_time * self.wait_penalty
                
                if score < best_score:
                    best_score = score
                    best_taxi = taxi
            
            if best_taxi:
                assignments[best_taxi.taxi_id] = passenger.passenger_id
                assigned_taxis.add(best_taxi.taxi_id)
                logger.info(f"Greedy: {best_taxi.taxi_id} -> {passenger.passenger_id} (score: {best_score:.1f})")
        
        return assignments

# ==================== TAXI SYSTEM ====================

class GridTaxi:
    """Taxi en la grilla"""
    
    def __init__(self, taxi_id: str, initial_position: GridPosition, grid: GridNetwork):
        self.info = TaxiInfo(
            taxi_id=taxi_id,
            position=initial_position,
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None
        )
        self.grid = grid
        self.path: List[GridPosition] = []
        self.path_index = 0
        
    def update(self, dt: float):
        """Actualiza estado del taxi"""
        if self.info.state == TaxiState.IDLE:
            self._patrol_movement()
        elif self.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]:
            self._move_towards_target()
    
    def _patrol_movement(self):
        """Movimiento aleatorio de patrullaje"""
        if not self.path or self.path_index >= len(self.path):
            # Nuevo destino aleatorio
            target = self.grid.get_random_intersection()
            self.path = self.grid.get_path(self.info.position, target)
            self.path_index = 0
        
        # Mover al siguiente punto
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.info.position = self.path[self.path_index]
    
    def _move_towards_target(self):
        """Movimiento hacia objetivo"""
        if not self.info.target_position:
            return
        
        if not self.path or self.path_index >= len(self.path):
            self.path = self.grid.get_path(self.info.position, self.info.target_position)
            self.path_index = 0
        
        if self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.info.position = self.path[self.path_index]
            
            # Verificar llegada
            if self.info.position == self.info.target_position:
                self._handle_arrival()
    
    def _handle_arrival(self):
        """Maneja llegada al objetivo"""
        if self.info.state == TaxiState.PICKUP:
            # Recoger pasajero
            self.info.state = TaxiState.DROPOFF
            self.info.current_passengers += 1
            logger.info(f"Taxi {self.info.taxi_id} picked up passenger {self.info.assigned_passenger_id}")
            return "passenger_picked_up"
            
        elif self.info.state == TaxiState.DROPOFF:
            # Entregar pasajero
            passenger_id = self.info.assigned_passenger_id
            self.info.state = TaxiState.IDLE
            self.info.current_passengers = 0
            self.info.target_position = None
            self.info.assigned_passenger_id = None
            logger.info(f"Taxi {self.info.taxi_id} delivered passenger {passenger_id}")
            return "passenger_delivered"
        
        return None
    
    def assign_passenger(self, passenger_id: str, pickup_pos: GridPosition, dropoff_pos: GridPosition):
        """Asigna pasajero al taxi"""
        self.info.assigned_passenger_id = passenger_id
        self.info.target_position = pickup_pos
        self.info.state = TaxiState.PICKUP
        # Guardar destino para después del pickup
        self._dropoff_position = dropoff_pos

class GridPassenger:
    """Pasajero en la grilla"""
    
    def __init__(self, passenger_id: str, pickup_pos: GridPosition, dropoff_pos: GridPosition):
        self.info = PassengerInfo(
            passenger_id=passenger_id,
            pickup_position=pickup_pos,
            dropoff_position=dropoff_pos,
            state=PassengerState.WAITING,
            wait_time=0.0
        )
    
    def update(self, dt: float):
        """Actualiza tiempo de espera"""
        if self.info.state == PassengerState.WAITING:
            self.info.wait_time += dt

# El resto del código continúa en el siguiente archivo...
