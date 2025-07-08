"""
Sistema Completo de Despacho de Taxis Distribuido
================================================

Sistema robusto y modular con:
- Constraint programming (OR-Tools con fallback greedy)
- SPADE/OpenFire para comunicación distribuida (opcional)
- GUI completa con Tkinter para visualización
- Mapa de grilla con movimiento Manhattan únicamente
- Logging y manejo de errores robusto
- 3 taxis y pasajeros dinámicos

Requisitos: Python 3.7+, tkinter (incluido), ortools (opcional), spade (opcional)
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
import math

# Optional imports
try:
    from ortools.constraint_solver import pywrapcp
    OR_TOOLS_AVAILABLE = True
    print("✅ OR-Tools disponible para constraint programming")
except ImportError:
    OR_TOOLS_AVAILABLE = False
    print("⚠️ OR-Tools no disponible, usando algoritmo greedy")

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

# Configuration
from config import config, taxi_config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('taxi_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== DATA STRUCTURES ====================

class TaxiState(Enum):
    """Estados del taxi"""
    IDLE = "idle"
    PICKUP = "pickup"
    DROPOFF = "dropoff"

class PassengerState(Enum):
    """Estados del pasajero"""
    WAITING = "waiting"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"

@dataclass
class GridPosition:
    """Posición en la grilla"""
    x: int
    y: int
    
    def manhattan_distance(self, other: 'GridPosition') -> int:
        """Distancia Manhattan"""
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def __eq__(self, other):
        return isinstance(other, GridPosition) and self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def to_dict(self):
        return {"x": self.x, "y": self.y}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data["x"], data["y"])

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
    last_update: float

@dataclass
class PassengerInfo:
    """Información completa del pasajero"""
    passenger_id: str
    pickup_position: GridPosition
    dropoff_position: GridPosition
    state: PassengerState
    wait_time: float
    assigned_taxi_id: Optional[str] = None
    created_at: float = 0.0

# ==================== GRID NETWORK ====================

class GridNetwork:
    """Red de grilla para navegación"""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.intersections = self._generate_intersections()
    
    def _generate_intersections(self) -> Set[GridPosition]:
        """Genera todas las intersecciones de la grilla"""
        intersections = set()
        for x in range(self.width):
            for y in range(self.height):
                intersections.add(GridPosition(x, y))
        return intersections
    
    def get_random_intersection(self) -> GridPosition:
        """Intersección aleatoria válida"""
        return random.choice(list(self.intersections))
    
    def get_adjacent_positions(self, pos: GridPosition) -> List[GridPosition]:
        """Posiciones adyacentes válidas (solo cardinales, no diagonales)"""
        adjacent = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # up, down, right, left
        
        for dx, dy in directions:
            new_pos = GridPosition(pos.x + dx, pos.y + dy)
            if self.is_valid_position(new_pos):
                adjacent.append(new_pos)
        
        return adjacent
    
    def is_valid_position(self, pos: GridPosition) -> bool:
        """Verifica si una posición es válida"""
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height
    
    def get_path(self, start: GridPosition, end: GridPosition) -> List[GridPosition]:
        """Pathfinding simple Manhattan (solo movimientos cardinales)"""
        if start == end:
            return [start]
        
        path = [start]
        current = GridPosition(start.x, start.y)
        
        # Moverse horizontalmente primero
        while current.x != end.x:
            step = 1 if current.x < end.x else -1
            current.x += step
            path.append(GridPosition(current.x, current.y))
        
        # Luego verticalmente
        while current.y != end.y:
            step = 1 if current.y < end.y else -1
            current.y += step
            path.append(GridPosition(current.x, current.y))
        
        return path

# ==================== CONSTRAINT SOLVER ====================

class ConstraintSolver:
    """Solver para asignación óptima de taxis"""
    
    def __init__(self):
        self.max_pickup_distance = taxi_config.max_pickup_distance
        self.wait_penalty_factor = taxi_config.wait_penalty_factor
    
    def solve_assignment(self, taxis: List[TaxiInfo], 
                        passengers: List[PassengerInfo]) -> Dict[str, str]:
        """
        Resuelve la asignación óptima taxi-pasajero
        Returns: {taxi_id: passenger_id}
        """
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in passengers if p.state == PassengerState.WAITING]
        
        if not available_taxis or not waiting_passengers:
            return {}
        
        logger.info(f"Resolviendo asignación: {len(available_taxis)} taxis, {len(waiting_passengers)} pasajeros")
        
        # Try OR-Tools first, fallback to greedy
        if OR_TOOLS_AVAILABLE:
            try:
                result = self._solve_with_ortools(available_taxis, waiting_passengers)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"OR-Tools falló: {e}")
        
        return self._greedy_assignment(available_taxis, waiting_passengers)
    
    def _solve_with_ortools(self, taxis: List[TaxiInfo], 
                           passengers: List[PassengerInfo]) -> Dict[str, str]:
        """Constraint programming con OR-Tools"""
        solver = pywrapcp.Solver("TaxiAssignment")
        
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        
        if n_taxis == 0 or n_passengers == 0:
            return {}
        
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
        
        # Restricciones de viabilidad
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                
                # Verificar capacidad
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                    continue
                
                # Verificar distancia máxima
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
                wait_penalty = int(passenger.wait_time * self.wait_penalty_factor)
                total_cost = distance + wait_penalty
                
                cost_terms.append(assignment[i][j] * total_cost)
        
        if cost_terms:
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
                            taxi_id = taxis[i].taxi_id
                            passenger_id = passengers[j].passenger_id
                            assignments[taxi_id] = passenger_id
                            distance = taxis[i].position.manhattan_distance(passengers[j].pickup_position)
                            logger.info(f"OR-Tools asignación: {taxi_id} -> {passenger_id} (distancia: {distance})")
            
            solver.EndSearch()
            return assignments
        
        return {}
    
    def _greedy_assignment(self, taxis: List[TaxiInfo], 
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
                
                # Score: distancia + penalización por tiempo de espera
                score = distance + passenger.wait_time * self.wait_penalty_factor
                
                if score < best_score:
                    best_score = score
                    best_taxi = taxi
            
            if best_taxi:
                assignments[best_taxi.taxi_id] = passenger.passenger_id
                assigned_taxis.add(best_taxi.taxi_id)
                distance = best_taxi.position.manhattan_distance(passenger.pickup_position)
                logger.info(f"Greedy asignación: {best_taxi.taxi_id} -> {passenger.passenger_id} (score: {best_score:.1f})")
        
        return assignments

# ==================== TAXI ENTITY ====================

class GridTaxi:
    """Entidad taxi con lógica de movimiento y estado"""
    
    def __init__(self, taxi_id: str, initial_position: GridPosition, grid: GridNetwork):
        self.info = TaxiInfo(
            taxi_id=taxi_id,
            position=initial_position,
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            last_update=time.time()
        )
        self.grid = grid
        self.path: List[GridPosition] = []
        self.path_index = 0
        self.dropoff_position: Optional[GridPosition] = None
        self.patrol_target: Optional[GridPosition] = None
    
    def update(self, dt: float) -> Optional[str]:
        """
        Actualiza el estado del taxi
        Returns: evento si ocurre ("passenger_picked_up" o "passenger_delivered")
        """
        self.info.last_update = time.time()
        
        if self.info.state == TaxiState.IDLE:
            self._patrol_movement()
        elif self.info.state in [TaxiState.PICKUP, TaxiState.DROPOFF]:
            return self._move_towards_target()
        
        return None
    
    def _patrol_movement(self):
        """Movimiento de patrullaje aleatorio"""
        # Si no tiene destino de patrullaje o llegó, elegir uno nuevo
        if (not self.patrol_target or 
            self.info.position == self.patrol_target or
            not self.path or self.path_index >= len(self.path)):
            
            self.patrol_target = self.grid.get_random_intersection()
            self.path = self.grid.get_path(self.info.position, self.patrol_target)
            self.path_index = 0
        
        # Mover al siguiente punto en el path
        self._move_along_path()
    
    def _move_towards_target(self) -> Optional[str]:
        """Movimiento hacia el objetivo asignado"""
        if not self.info.target_position:
            return None
        
        # Generar path si es necesario
        if not self.path or self.path_index >= len(self.path):
            self.path = self.grid.get_path(self.info.position, self.info.target_position)
            self.path_index = 0
        
        # Mover
        self._move_along_path()
        
        # Verificar llegada al objetivo
        if self.info.position == self.info.target_position:
            return self._handle_arrival()
        
        return None
    
    def _move_along_path(self):
        """Mueve el taxi al siguiente punto en el path"""
        if self.path and self.path_index < len(self.path) - 1:
            self.path_index += 1
            self.info.position = self.path[self.path_index]
    
    def _handle_arrival(self) -> Optional[str]:
        """Maneja la llegada al objetivo"""
        if self.info.state == TaxiState.PICKUP:
            # Recogió al pasajero, ahora ir al destino
            self.info.state = TaxiState.DROPOFF
            self.info.current_passengers += 1
            self.info.target_position = self.dropoff_position
            self.path = []
            self.path_index = 0
            logger.info(f"Taxi {self.info.taxi_id} recogió pasajero {self.info.assigned_passenger_id}")
            return "passenger_picked_up"
            
        elif self.info.state == TaxiState.DROPOFF:
            # Entregó al pasajero, volver a idle
            passenger_id = self.info.assigned_passenger_id
            self.info.state = TaxiState.IDLE
            self.info.current_passengers = 0
            self.info.target_position = None
            self.info.assigned_passenger_id = None
            self.dropoff_position = None
            self.path = []
            self.path_index = 0
            logger.info(f"Taxi {self.info.taxi_id} entregó pasajero {passenger_id}")
            return "passenger_delivered"
        
        return None
    
    def assign_passenger(self, passenger_id: str, pickup_pos: GridPosition, 
                        dropoff_pos: GridPosition):
        """Asigna un pasajero al taxi"""
        if self.info.state != TaxiState.IDLE:
            logger.warning(f"Intentando asignar pasajero a taxi {self.info.taxi_id} que no está idle")
            return False
        
        self.info.assigned_passenger_id = passenger_id
        self.info.target_position = pickup_pos
        self.info.state = TaxiState.PICKUP
        self.dropoff_position = dropoff_pos
        self.path = []
        self.path_index = 0
        
        logger.info(f"Taxi {self.info.taxi_id} asignado a pasajero {passenger_id}")
        return True

# ==================== PASSENGER ENTITY ====================

class GridPassenger:
    """Entidad pasajero"""
    
    def __init__(self, passenger_id: str, pickup_pos: GridPosition, dropoff_pos: GridPosition):
        self.info = PassengerInfo(
            passenger_id=passenger_id,
            pickup_position=pickup_pos,
            dropoff_position=dropoff_pos,
            state=PassengerState.WAITING,
            wait_time=0.0,
            created_at=time.time()
        )
    
    def update(self, dt: float):
        """Actualiza el tiempo de espera"""
        if self.info.state == PassengerState.WAITING:
            self.info.wait_time += dt
    
    def pick_up(self, taxi_id: str):
        """Marca el pasajero como recogido"""
        self.info.state = PassengerState.PICKED_UP
        self.info.assigned_taxi_id = taxi_id
    
    def deliver(self):
        """Marca el pasajero como entregado"""
        self.info.state = PassengerState.DELIVERED

# ==================== GUI ====================

class TaxiSystemGUI:
    """GUI principal del sistema de taxis"""
    
    def __init__(self, system):
        self.system = system
        self.root = tk.Tk()
        self.root.title("Sistema de Despacho de Taxis Distribuido")
        self.root.geometry(f"{taxi_config.taxi_gui_width}x{taxi_config.taxi_gui_height}")
        
        # Colors
        self.colors = {
            'taxi_idle': '#00FF00',
            'taxi_pickup': '#FFFF00', 
            'taxi_dropoff': '#FF8000',
            'passenger_waiting': '#FF0000',
            'passenger_picked': '#800080',
            'grid_line': '#CCCCCC',
            'background': '#FFFFFF'
        }
        
        self.setup_gui()
        self.running = False
    
    def setup_gui(self):
        """Configura la interfaz gráfica"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Controls
        control_frame = ttk.LabelFrame(main_frame, text="Controles", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        # Buttons
        ttk.Button(control_frame, text="Añadir Pasajero", 
                  command=self.add_random_passenger).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="Reiniciar Sistema", 
                  command=self.reset_system).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="Pausar/Reanudar", 
                  command=self.toggle_pause).pack(fill=tk.X, pady=2)
        
        # Status
        status_frame = ttk.LabelFrame(control_frame, text="Estado", padding=5)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_vars = {
            'taxis': tk.StringVar(value="Taxis: 0"),
            'passengers': tk.StringVar(value="Pasajeros: 0"),
            'assignments': tk.StringVar(value="Asignaciones: 0"),
            'delivered': tk.StringVar(value="Entregados: 0")
        }
        
        for var in self.status_vars.values():
            ttk.Label(status_frame, textvariable=var).pack(anchor=tk.W)
        
        # Legend
        legend_frame = ttk.LabelFrame(control_frame, text="Leyenda", padding=5)
        legend_frame.pack(fill=tk.X, pady=(10, 0))
        
        legend_items = [
            ("🟢 Taxi Libre", self.colors['taxi_idle']),
            ("🟡 Taxi Recogiendo", self.colors['taxi_pickup']),
            ("🟠 Taxi Entregando", self.colors['taxi_dropoff']),
            ("🔴 Pasajero Esperando", self.colors['passenger_waiting']),
            ("🟣 Pasajero en Taxi", self.colors['passenger_picked'])
        ]
        
        for text, color in legend_items:
            frame = ttk.Frame(legend_frame)
            frame.pack(fill=tk.X)
            ttk.Label(frame, text=text).pack(side=tk.LEFT)
        
        # Right panel - Canvas
        canvas_frame = ttk.LabelFrame(main_frame, text="Mapa de la Ciudad", padding=5)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Canvas with scrollbars
        canvas_container = ttk.Frame(canvas_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_container, bg=self.colors['background'])
        v_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Set canvas scroll region
        canvas_width = taxi_config.taxi_grid_width * taxi_config.taxi_cell_size
        canvas_height = taxi_config.taxi_grid_height * taxi_config.taxi_cell_size
        self.canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
        
        # Bind canvas click
        self.canvas.bind("<Button-1>", self.on_canvas_click)
    
    def add_random_passenger(self):
        """Añade un pasajero aleatorio"""
        self.system.add_random_passenger()
    
    def reset_system(self):
        """Reinicia el sistema"""
        if messagebox.askyesno("Confirmar", "¿Reiniciar el sistema?"):
            self.system.reset()
    
    def toggle_pause(self):
        """Pausa/reanuda el sistema"""
        self.system.toggle_pause()
    
    def on_canvas_click(self, event):
        """Maneja clicks en el canvas"""
        x = int(event.x // taxi_config.taxi_cell_size)
        y = int(event.y // taxi_config.taxi_cell_size)
        
        if (0 <= x < taxi_config.taxi_grid_width and 0 <= y < taxi_config.taxi_grid_height):
            # Añadir pasajero en esta posición
            pickup_pos = GridPosition(x, y)
            dropoff_pos = self.system.grid.get_random_intersection()
            self.system.add_passenger(pickup_pos, dropoff_pos)
    
    def update_display(self):
        """Actualiza la visualización"""
        if not self.running:
            return
        
        self.canvas.delete("all")
        
        # Draw grid
        self._draw_grid()
        
        # Draw entities
        self._draw_taxis()
        self._draw_passengers()
        
        # Update status
        self._update_status()
    
    def _draw_grid(self):
        """Dibuja la grilla"""
        cell_size = taxi_config.taxi_cell_size
        
        # Vertical lines
        for x in range(taxi_config.taxi_grid_width + 1):
            x_pos = x * cell_size
            self.canvas.create_line(x_pos, 0, x_pos, taxi_config.taxi_grid_height * cell_size,
                                  fill=self.colors['grid_line'], width=1)
        
        # Horizontal lines
        for y in range(taxi_config.taxi_grid_height + 1):
            y_pos = y * cell_size
            self.canvas.create_line(0, y_pos, taxi_config.taxi_grid_width * cell_size, y_pos,
                                  fill=self.colors['grid_line'], width=1)
    
    def _draw_taxis(self):
        """Dibuja los taxis"""
        cell_size = taxi_config.taxi_cell_size
        
        for taxi in self.system.taxis.values():
            x = taxi.info.position.x * cell_size + cell_size // 2
            y = taxi.info.position.y * cell_size + cell_size // 2
            
            # Color según estado
            if taxi.info.state == TaxiState.IDLE:
                color = self.colors['taxi_idle']
            elif taxi.info.state == TaxiState.PICKUP:
                color = self.colors['taxi_pickup']
            else:  # DROPOFF
                color = self.colors['taxi_dropoff']
            
            # Dibujar taxi
            radius = cell_size // 3
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                  fill=color, outline='black', width=2)
            
            # Etiqueta
            self.canvas.create_text(x, y, text=taxi.info.taxi_id[-1], 
                                  font=('Arial', 8, 'bold'))
            
            # Dibujar path si está asignado
            if taxi.info.state != TaxiState.IDLE and taxi.path:
                self._draw_path(taxi.path, 'blue')
    
    def _draw_passengers(self):
        """Dibuja los pasajeros"""
        cell_size = taxi_config.taxi_cell_size
        
        for passenger in self.system.passengers.values():
            if passenger.info.state == PassengerState.DELIVERED:
                continue
            
            pos = passenger.info.pickup_position
            if passenger.info.state == PassengerState.PICKED_UP:
                # Si está en un taxi, no dibujar en pickup
                continue
            
            x = pos.x * cell_size + cell_size // 2
            y = pos.y * cell_size + cell_size // 2
            
            # Color según estado
            color = self.colors['passenger_waiting']
            
            # Dibujar pasajero
            size = cell_size // 4
            self.canvas.create_rectangle(x - size, y - size, x + size, y + size,
                                       fill=color, outline='black', width=1)
            
            # Mostrar tiempo de espera
            wait_time = int(passenger.info.wait_time)
            if wait_time > 0:
                self.canvas.create_text(x, y - cell_size // 2, text=f"{wait_time}s",
                                      font=('Arial', 7), fill='red')
            
            # Dibujar línea al destino
            dest_x = passenger.info.dropoff_position.x * cell_size + cell_size // 2
            dest_y = passenger.info.dropoff_position.y * cell_size + cell_size // 2
            self.canvas.create_line(x, y, dest_x, dest_y, fill='red', width=1, dash=(2, 2))
            
            # Dibujar destino
            dest_size = cell_size // 6
            self.canvas.create_oval(dest_x - dest_size, dest_y - dest_size,
                                  dest_x + dest_size, dest_y + dest_size,
                                  fill='red', outline='darkred')
    
    def _draw_path(self, path: List[GridPosition], color: str):
        """Dibuja un path"""
        if len(path) < 2:
            return
        
        cell_size = taxi_config.taxi_cell_size
        
        for i in range(len(path) - 1):
            x1 = path[i].x * cell_size + cell_size // 2
            y1 = path[i].y * cell_size + cell_size // 2
            x2 = path[i + 1].x * cell_size + cell_size // 2
            y2 = path[i + 1].y * cell_size + cell_size // 2
            
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
    
    def _update_status(self):
        """Actualiza las etiquetas de estado"""
        taxis_count = len(self.system.taxis)
        passengers_waiting = len([p for p in self.system.passengers.values() 
                                if p.info.state == PassengerState.WAITING])
        passengers_total = len(self.system.passengers)
        assignments = len([t for t in self.system.taxis.values() 
                         if t.info.state != TaxiState.IDLE])
        delivered = len([p for p in self.system.passengers.values() 
                       if p.info.state == PassengerState.DELIVERED])
        
        self.status_vars['taxis'].set(f"Taxis: {taxis_count}")
        self.status_vars['passengers'].set(f"Pasajeros: {passengers_waiting}/{passengers_total}")
        self.status_vars['assignments'].set(f"Asignaciones: {assignments}")
        self.status_vars['delivered'].set(f"Entregados: {delivered}")
    
    def start(self):
        """Inicia la GUI"""
        self.running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Maneja el cierre de la ventana"""
        self.running = False
        self.system.stop()
        self.root.destroy()

# ==================== DISTRIBUTED COMMUNICATION ====================

class DistributedCommunication:
    """Maneja la comunicación distribuida del sistema"""
    
    def __init__(self, taxi_system):
        self.taxi_system = taxi_system
        self.agent = None
        self.known_agents: Set[str] = set()
        self._communication_thread = None
        self._loop = None
        self._running = False
    
    async def start_communication(self):
        """Inicia la comunicación distribuida"""
        if SPADE_AVAILABLE:
            try:
                jid = f"{taxi_config.taxi_agent_prefix}system@{config.openfire_domain}"
                self.agent = TaxiSystemAgent(jid, "password", self.taxi_system)
                await self.agent.start()
                self._running = True
                logger.info(f"Comunicación distribuida iniciada: {jid}")
                return True
            except Exception as e:
                logger.warning(f"No se pudo iniciar comunicación distribuida: {e}")
        else:
            logger.info("SPADE no disponible, ejecutando en modo local")
        return False
    
    async def stop_communication(self):
        """Detiene la comunicación distribuida"""
        self._running = False
        if self.agent:
            try:
                await self.agent.stop()
                logger.info("Comunicación distribuida detenida")
            except Exception as e:
                logger.error(f"Error deteniendo comunicación: {e}")
    
    def start_in_thread(self):
        """Inicia la comunicación en un hilo separado"""
        if not self._communication_thread or not self._communication_thread.is_alive():
            import threading
            self._communication_thread = threading.Thread(
                target=self._run_async_in_thread, 
                daemon=True
            )
            self._communication_thread.start()
            logger.info("Comunicación distribuida iniciada en hilo separado")
    
    def _run_async_in_thread(self):
        """Ejecuta la comunicación asíncrona en un hilo separado"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.start_communication())
            
            # Mantener el bucle ejecutándose
            while self._running:
                self._loop.run_until_complete(asyncio.sleep(0.1))
                
        except Exception as e:
            logger.error(f"Error en hilo de comunicación: {e}")
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
    
    def stop_thread(self):
        """Detiene el hilo de comunicación"""
        self._running = False
        if self._loop and not self._loop.is_closed():
            try:
                # Programar la detención en el bucle del hilo
                future = asyncio.run_coroutine_threadsafe(
                    self.stop_communication(), 
                    self._loop
                )
                future.result(timeout=5.0)  # Esperar máximo 5 segundos
            except Exception as e:
                logger.error(f"Error deteniendo comunicación en hilo: {e}")
        
        if self._communication_thread and self._communication_thread.is_alive():
            self._communication_thread.join(timeout=2.0)
    
    async def handle_message(self, data: dict, sender: str):
        """Maneja mensajes distribuidos"""
        self.known_agents.add(sender)
        logger.debug(f"Mensaje recibido de {sender}")
        # Aquí se puede implementar sincronización de estado

if SPADE_AVAILABLE:
    class TaxiSystemAgent(Agent):
        """Agente SPADE para comunicación distribuida del sistema de taxis"""
        
        def __init__(self, jid, password, taxi_system):
            super().__init__(jid, password)
            self.system = taxi_system
        
        async def setup(self):
            """Configuración del agente"""
            logger.info(f"Agente {self.jid} iniciado")
            
            # Comportamiento para recibir mensajes
            receive_behaviour = self.ReceiveMessageBehaviour()
            receive_behaviour.set_agent(self)  # Set agent reference
            self.add_behaviour(receive_behaviour)
        
        class ReceiveMessageBehaviour(CyclicBehaviour):
            """Comportamiento para recibir mensajes"""
            
            def set_agent(self, agent):
                """Set agent reference"""
                self._agent_ref = agent
            
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg and msg.body:
                    try:
                        data = json.loads(msg.body)
                        # Use the stored agent reference
                        if hasattr(self, '_agent_ref') and self._agent_ref.system:
                            await self._agent_ref.system.handle_distributed_message(data, str(msg.sender))
                    except Exception as e:
                        logger.error(f"Error procesando mensaje: {e}")

else:
    class TaxiSystemAgent:
        """Agente mock cuando SPADE no está disponible"""
        def __init__(self, jid, password, taxi_system):
            self.jid = jid
            self.system = taxi_system
        
        async def start(self):
            logger.info("Agente mock iniciado (SPADE no disponible)")
        
        async def stop(self):
            logger.info("Agente mock detenido")

# ==================== MAIN SYSTEM ====================

class DistributedTaxiSystem:
    """Sistema principal de despacho de taxis"""
    
    def __init__(self):
        self.grid = GridNetwork(taxi_config.taxi_grid_width, taxi_config.taxi_grid_height)
        self.solver = ConstraintSolver()
        
        # Entities
        self.taxis: Dict[str, GridTaxi] = {}
        self.passengers: Dict[str, GridPassenger] = {}
        
        # Control
        self.running = False
        self.paused = False
        self.last_assignment_time = 0
        self.passenger_counter = 0
        self.delivered_count = 0
        
        # Distributed communication
        self.communication = DistributedCommunication(self)
        
        # Initialize system
        self._initialize_taxis()
        self._add_initial_passengers()
        
        logger.info("Sistema de taxis inicializado")
    
    def _initialize_taxis(self):
        """Inicializa los taxis"""
        for i in range(taxi_config.num_taxis):
            taxi_id = f"taxi_{i+1}"
            position = self.grid.get_random_intersection()
            self.taxis[taxi_id] = GridTaxi(taxi_id, position, self.grid)
        
        logger.info(f"Inicializados {len(self.taxis)} taxis")
    
    def _add_initial_passengers(self):
        """Añade pasajeros iniciales"""
        for i in range(taxi_config.initial_passengers):
            self.add_random_passenger()
    
    def add_random_passenger(self):
        """Añade un pasajero aleatorio"""
        pickup = self.grid.get_random_intersection()
        dropoff = self.grid.get_random_intersection()
        
        # Asegurar que pickup y dropoff son diferentes
        while pickup == dropoff:
            dropoff = self.grid.get_random_intersection()
        
        self.add_passenger(pickup, dropoff)
    
    def add_passenger(self, pickup_pos: GridPosition, dropoff_pos: GridPosition):
        """Añade un pasajero específico"""
        self.passenger_counter += 1
        passenger_id = f"passenger_{self.passenger_counter}"
        
        passenger = GridPassenger(passenger_id, pickup_pos, dropoff_pos)
        self.passengers[passenger_id] = passenger
        
        logger.info(f"Nuevo pasajero {passenger_id} en ({pickup_pos.x}, {pickup_pos.y}) -> ({dropoff_pos.x}, {dropoff_pos.y})")
    
    def update(self, dt: float):
        """Actualización principal del sistema"""
        if self.paused:
            return
        
        current_time = time.time()
        
        # Update entities
        self._update_taxis(dt)
        self._update_passengers(dt)
        
        # Periodic assignment
        if current_time - self.last_assignment_time >= taxi_config.assignment_interval:
            self._solve_assignments()
            self.last_assignment_time = current_time
        
        # Random passenger spawn
        if random.random() < taxi_config.passenger_spawn_rate * dt:
            self.add_random_passenger()
    
    def _update_taxis(self, dt: float):
        """Actualiza todos los taxis"""
        for taxi in self.taxis.values():
            event = taxi.update(dt)
            if event:
                self._handle_taxi_event(taxi, event)
    
    def _update_passengers(self, dt: float):
        """Actualiza todos los pasajeros"""
        for passenger in self.passengers.values():
            passenger.update(dt)
    
    def _handle_taxi_event(self, taxi: GridTaxi, event: str):
        """Maneja eventos de los taxis"""
        if event == "passenger_picked_up":
            passenger_id = taxi.info.assigned_passenger_id
            if passenger_id in self.passengers:
                self.passengers[passenger_id].pick_up(taxi.info.taxi_id)
                # Actualizar destino del taxi
                taxi.info.target_position = taxi.dropoff_position
        
        elif event == "passenger_delivered":
            passenger_id = taxi.info.assigned_passenger_id
            if passenger_id in self.passengers:
                self.passengers[passenger_id].deliver()
                self.delivered_count += 1
                logger.info(f"Pasajero {passenger_id} entregado. Total entregados: {self.delivered_count}")
    
    def _solve_assignments(self):
        """Resuelve asignaciones óptimas"""
        taxi_infos = [taxi.info for taxi in self.taxis.values()]
        passenger_infos = [passenger.info for passenger in self.passengers.values()]
        
        assignments = self.solver.solve_assignment(taxi_infos, passenger_infos)
        
        # Aplicar asignaciones
        for taxi_id, passenger_id in assignments.items():
            if taxi_id in self.taxis and passenger_id in self.passengers:
                taxi = self.taxis[taxi_id]
                passenger = self.passengers[passenger_id]
                
                taxi.assign_passenger(
                    passenger_id,
                    passenger.info.pickup_position,
                    passenger.info.dropoff_position
                )
                
                passenger.info.assigned_taxi_id = taxi_id
    
    def reset(self):
        """Reinicia el sistema"""
        logger.info("Reiniciando sistema...")
        
        self.taxis.clear()
        self.passengers.clear()
        self.passenger_counter = 0
        self.delivered_count = 0
        self.last_assignment_time = 0
        
        self._initialize_taxis()
        self._add_initial_passengers()
    
    def toggle_pause(self):
        """Pausa/reanuda el sistema"""
        self.paused = not self.paused
        logger.info(f"Sistema {'pausado' if self.paused else 'reanudado'}")
    
    def start(self):
        """Inicia el sistema"""
        self.running = True
        logger.info("Sistema iniciado")
        
        # Start distributed communication if available
        if SPADE_AVAILABLE and self.communication:
            self._start_communication_safe()
    
    def stop(self):
        """Detiene el sistema"""
        self.running = False
        logger.info("Sistema detenido")
        
        if self.communication:
            self._stop_communication_safe()
    
    def _start_communication_safe(self):
        """Inicia la comunicación de forma segura, manejando bucles de eventos"""
        if not self.communication:
            return
            
        try:
            # Verificar si hay un bucle de eventos en ejecución
            loop = asyncio.get_running_loop()
            # Si hay un bucle ejecutándose, crear la tarea
            loop.create_task(self.communication.start_communication())
            logger.info("Comunicación distribuida iniciada en bucle existente")
        except RuntimeError:
            # No hay bucle de eventos, usar hilo separado
            self.communication.start_in_thread()
    
    def _stop_communication_safe(self):
        """Detiene la comunicación de forma segura"""
        if not self.communication:
            return
            
        try:
            # Verificar si hay un bucle de eventos en ejecución
            loop = asyncio.get_running_loop()
            # Si hay un bucle ejecutándose, crear la tarea
            loop.create_task(self.communication.stop_communication())
        except RuntimeError:
            # No hay bucle de eventos, detener hilo si existe
            self.communication.stop_thread()
        except Exception as e:
            logger.error(f"Error deteniendo comunicación distribuida: {e}")
    
    def get_system_state(self) -> dict:
        """Obtiene el estado del sistema para comunicación distribuida"""
        return {
            "timestamp": time.time(),
            "taxis": {tid: asdict(taxi.info) for tid, taxi in self.taxis.items()},
            "passengers": {pid: asdict(passenger.info) for pid, passenger in self.passengers.items()},
            "delivered_count": self.delivered_count
        }
    
    async def handle_distributed_message(self, data: dict, sender: str):
        """Maneja mensajes de otros nodos"""
        await self.communication.handle_message(data, sender)

# ==================== MAIN APPLICATION ====================

class TaxiDispatchApp:
    """Aplicación principal"""
    
    def __init__(self):
        self.system = DistributedTaxiSystem()
        self.gui = TaxiSystemGUI(self.system)
        self.update_thread = None
    
    def run(self):
        """Ejecuta la aplicación"""
        logger.info("Iniciando aplicación de despacho de taxis")
        
        # Start system
        self.system.start()
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Start GUI (blocking)
        self.gui.start()
    
    def _update_loop(self):
        """Loop de actualización del sistema"""
        last_time = time.time()
        
        while self.system.running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Update system
            self.system.update(dt)
            
            # Update GUI
            if self.gui.running:
                try:
                    self.gui.root.after(0, self.gui.update_display)
                except tk.TclError:
                    break
            
            # Sleep to maintain FPS
            time.sleep(1.0 / taxi_config.taxi_fps)

# ==================== ENTRY POINT ====================

def main():
    """Función principal"""
    print("🚕 Sistema de Despacho de Taxis Distribuido")
    print("=" * 50)
    
    try:
        app = TaxiDispatchApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Aplicación interrumpida por el usuario")
    except Exception as e:
        logger.error(f"Error en la aplicación: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("Aplicación terminada")

if __name__ == "__main__":
    main()
