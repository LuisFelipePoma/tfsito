import logging
import random
from dataclasses import dataclass
from typing import List, Optional, Set
from enum import Enum

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
    
    def load_from_dict(self, data: dict):
        self.width = data.get("width", 20)
        self.height = data.get("height", 20)
        self.intersections = {GridPosition(**pos) for pos in data.get("intersections", [])}
        
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
    
    def to_dict(self) -> dict:
        """Convierte la red a diccionario para serialización"""
        return {
            "width": self.width,
            "height": self.height,
            "intersections": [{"x": pos.x, "y": pos.y} for pos in self.intersections]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GridNetwork':
        """Crea una red desde un diccionario"""
        grid = cls(data.get("width", 20), data.get("height", 20))
        intersections_data = data.get("intersections", [])
        grid.intersections = {GridPosition(pos["x"], pos["y"]) for pos in intersections_data}
        return grid