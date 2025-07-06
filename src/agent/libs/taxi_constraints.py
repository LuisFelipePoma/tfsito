"""
OR-Tools CP-SAT solver for taxi dispatch decision making (SIMPLIFIED VERSION)

This module has been simplified to only consider 3 key constraints:
1. CAPACITY: Taxi must have space for the requested number of passengers
2. DISTANCE: Client must be within reasonable distance from taxi
3. DISABILITY PRIORITY: Disabled clients get preference and extended distance limits

The taxi behavior is simplified:
- Pick up client at their location
- Drop them off at destination (any corner of the map)
- Return to pick up new clients that are generated after drop-off

Removed constraints: fuel level, wait time, profit calculations
"""

from ortools.sat.python import cp_model
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
import math

logger = logging.getLogger(__name__)


@dataclass
class RideRequest:
    """Data structure for ride requests from clients (simplified)"""
    client_id: str
    n_pasajeros: int
    es_discapacitado: bool
    distancia_al_cliente: float  # kilómetros
    client_position: tuple  # (x, y) position on map
    destination: tuple  # (x, y) destination chosen by client
    tiempo_esperando: float = 0.0  # seconds waiting for pickup
    max_range_multiplier: float = 1.0  # multiplier for expanding search range
    

@dataclass
class TaxiState:
    """Current state of the taxi (simplified)"""
    taxi_id: str
    current_position: tuple  # (x, y) position on map
    max_capacity: int
    current_passengers: int
    is_available: bool
    target_position: Optional[tuple] = None  # Where taxi is heading (None = free roaming)
    movement_speed: float = 2.0  # units per second for free movement
    

@dataclass
class TaxiConstraints:
    """Configuration constraints for taxi operations (simplified)"""
    max_capacity: int = 4
    base_max_distance: float = 25.0  # Base distance in km for pickup
    max_range_expansion: float = 3.0  # Maximum multiplier for expanding range
    range_expansion_rate: float = 0.1  # How fast range expands per second waiting
    priority_disability_bonus: int = 100  # bonus points for disability priority
    free_roam_radius: float = 15.0  # Radius for free roaming movement


class TaxiDecisionSolver:
    """OR-Tools CP-SAT solver for taxi dispatch decisions"""
    
    def __init__(self, constraints: TaxiConstraints):
        self.constraints = constraints
        
    def can_accept_ride(self, taxi_state: TaxiState, ride_request: RideRequest) -> tuple[bool, str, Dict[str, Any]]:
        """
        Use OR-Tools CP-SAT to determine if taxi should accept ride request
        
        Simplified constraints:
        1. Capacity check: taxi must have space for passengers
        2. Distance check: client must be within reasonable distance
        3. Disability priority: disabled clients get preference
        
        Returns:
            tuple: (accept_decision, reason, solution_details)
        """
        try:
            # Create the model
            model = cp_model.CpModel()
            
            # Decision variable: 1 if accept ride, 0 if reject
            accept_ride = model.NewBoolVar('accept_ride')
            
            # Constraint variables for evaluation
            capacity_satisfied = model.NewBoolVar('capacity_satisfied')
            distance_satisfied = model.NewBoolVar('distance_satisfied')
            
            # Input parameters as integer variables (scaled for CP-SAT)
            n_passengers = ride_request.n_pasajeros
            distance = int(ride_request.distancia_al_cliente * 100)  # scale to avoid floats
            is_disabled = 1 if ride_request.es_discapacitado else 0
            
            taxi_capacity = taxi_state.max_capacity
            current_passengers = taxi_state.current_passengers
            
            # Constraint 1: Passenger capacity
            # capacity_satisfied = 1 if (current_passengers + n_passengers <= max_capacity)
            model.Add(current_passengers + n_passengers <= taxi_capacity).OnlyEnforceIf(capacity_satisfied)
            model.Add(current_passengers + n_passengers > taxi_capacity).OnlyEnforceIf(capacity_satisfied.Not())
            
            # Constraint 2: Distance limit (with dynamic range expansion)
            # distance_satisfied = 1 if distance <= effective_max_distance
            effective_max_distance = self.constraints.base_max_distance * ride_request.max_range_multiplier
            max_distance_scaled = int(effective_max_distance * 100)
            model.Add(distance <= max_distance_scaled).OnlyEnforceIf(distance_satisfied)
            model.Add(distance > max_distance_scaled).OnlyEnforceIf(distance_satisfied.Not())
            
            # Decision logic with disability priority
            if is_disabled:
                # Priority rule for disabled passengers: accept if capacity is OK and distance is reasonable
                # Relax distance constraint for disabled passengers (double the max distance)
                extended_distance_satisfied = model.NewBoolVar('extended_distance_satisfied')
                extended_max_distance = max_distance_scaled * 2  # Double distance for disabled
                model.Add(distance <= extended_max_distance).OnlyEnforceIf(extended_distance_satisfied)
                model.Add(distance > extended_max_distance).OnlyEnforceIf(extended_distance_satisfied.Not())
                
                # Accept if capacity OK and within extended distance
                model.AddBoolAnd([capacity_satisfied, extended_distance_satisfied]).OnlyEnforceIf(accept_ride)
                model.AddBoolOr([capacity_satisfied.Not(), extended_distance_satisfied.Not()]).OnlyEnforceIf(accept_ride.Not())
            else:
                # Regular passengers: capacity and normal distance constraints
                model.AddBoolAnd([capacity_satisfied, distance_satisfied]).OnlyEnforceIf(accept_ride)
                model.AddBoolOr([capacity_satisfied.Not(), distance_satisfied.Not()]).OnlyEnforceIf(accept_ride.Not())
            
            # Objective: prioritize disabled passengers, then minimize distance
            objective_value = model.NewIntVar(-10000, 10000, 'objective')
            
            if is_disabled:
                # High bonus for accepting disabled passengers
                model.Add(objective_value == self.constraints.priority_disability_bonus - distance).OnlyEnforceIf(accept_ride)
            else:
                # For regular passengers, prefer closer clients
                model.Add(objective_value == 1000 - distance).OnlyEnforceIf(accept_ride)
            
            model.Add(objective_value == -10000).OnlyEnforceIf(accept_ride.Not())
            
            model.Maximize(objective_value)
            
            # Solve the model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 0.5  # Quick decision
            
            status = solver.Solve(model)
            
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                accept_decision = bool(solver.Value(accept_ride))
                
                solution_details = {
                    'capacity_satisfied': bool(solver.Value(capacity_satisfied)),
                    'distance_satisfied': bool(solver.Value(distance_satisfied)),
                    'is_disabled_priority': is_disabled,
                    'distance_km': ride_request.distancia_al_cliente,
                    'passengers_needed': n_passengers,
                    'taxi_available_capacity': taxi_capacity - current_passengers
                }
                
                if accept_decision:
                    if is_disabled:
                        reason = "Ride accepted - Disability priority"
                    else:
                        reason = "Ride accepted - Capacity and distance OK"
                else:
                    failed_constraints = []
                    if not solution_details['capacity_satisfied']:
                        failed_constraints.append(f"capacity exceeded (need {n_passengers}, available {taxi_capacity - current_passengers})")
                    if not solution_details['distance_satisfied']:
                        effective_max = self.constraints.base_max_distance * ride_request.max_range_multiplier
                        failed_constraints.append(f"distance too far ({ride_request.distancia_al_cliente:.1f}km > {effective_max:.1f}km)")
                    
                    reason = f"Ride rejected - {', '.join(failed_constraints)}"
                
                return accept_decision, reason, solution_details
            
            else:
                logger.warning(f"Solver failed with status: {status}")
                return False, "Solver failed", {}
                
        except Exception as e:
            logger.error(f"Error in constraint solver: {e}")
            return False, f"Error in decision making: {str(e)}", {}
    
    def calculate_estimated_distance(self, pos1: tuple, pos2: tuple) -> float:
        """Calculate Euclidean distance between two positions"""
        try:
            x1, y1 = pos1
            x2, y2 = pos2
            return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return float('inf')


def parse_ride_request_from_message(message_body: str, sender_id: str) -> Optional[RideRequest]:
    """Parse ride request from SPADE message"""
    try:
        data = json.loads(message_body)
        
        return RideRequest(
            client_id=sender_id,
            n_pasajeros=data.get('n_pasajeros', 1),
            es_discapacitado=data.get('es_discapacitado', False),
            distancia_al_cliente=data.get('distancia_al_cliente', 0.0),
            client_position=tuple(data.get('client_position', (0, 0))),
            destination=tuple(data.get('destination', (0, 0)))
        )
    except Exception as e:
        logger.error(f"Error parsing ride request: {e}")
        return None


def create_ride_request_message(n_pasajeros: int, es_discapacitado: bool, 
                               distancia_al_cliente: float, client_position: tuple, 
                               destination: tuple) -> str:
    """Create JSON message for ride request (simplified)"""
    
    data = {
        'n_pasajeros': n_pasajeros,
        'es_discapacitado': es_discapacitado,
        'distancia_al_cliente': distancia_al_cliente,
        'client_position': client_position,
        'destination': destination
    }
    
    return json.dumps(data)

# ===== EJEMPLO DE USO =====
def find_best_taxi_for_client(client_info: Dict[str, Any], available_taxis: list) -> Optional[str]:
    """
    Encuentra el mejor taxi para un cliente usando constraints simplificadas con rango dinámico
    
    Args:
        client_info: {
            'position': (x,y), 
            'passengers': int, 
            'disabled': bool,
            'waiting_time': float,  # seconds waiting
            'range_multiplier': float  # current range expansion
        }
        available_taxis: Lista de taxis con {
            'id': str, 
            'position': (x,y), 
            'capacity': int, 
            'current_passengers': int,
            'is_available': bool
        }
    
    Returns:
        taxi_id del mejor taxi o None si ninguno es adecuado
    """
    if not available_taxis:
        return None
    
    best_taxi = None
    best_score = float('inf')
    
    # Límites de distancia con rango dinámico
    base_distance = 20.0  # kilómetros base (reducido para mejor control)
    range_multiplier = client_info.get('range_multiplier', 1.0)
    max_distance = base_distance * range_multiplier
    
    # Mayor rango para discapacitados
    if client_info['disabled']:
        max_distance *= 1.8
    
    logger.debug(f"Searching taxi for client with max_distance: {max_distance:.1f} (base: {base_distance}, multiplier: {range_multiplier:.1f})")
    
    suitable_taxis = []
    
    for taxi_data in available_taxis:
        # Filtros estrictos para disponibilidad
        if not taxi_data.get('is_available', False):
            logger.debug(f"Taxi {taxi_data['id']} not available")
            continue
            
        if taxi_data.get('current_passengers', 0) > 0:
            logger.debug(f"Taxi {taxi_data['id']} already has passengers")
            continue
        
        # Verificar capacidad
        available_capacity = taxi_data['capacity'] - taxi_data.get('current_passengers', 0)
        if available_capacity < client_info['passengers']:
            logger.debug(f"Taxi {taxi_data['id']} insufficient capacity: {available_capacity} < {client_info['passengers']}")
            continue
        
        # Calcular distancia
        taxi_pos = taxi_data['position']
        client_pos = client_info['position']
        distance = math.sqrt((taxi_pos[0] - client_pos[0])**2 + (taxi_pos[1] - client_pos[1])**2)
        
        # Verificar límites de distancia expandida
        if distance > max_distance:
            logger.debug(f"Taxi {taxi_data['id']} too far: {distance:.1f} > {max_distance:.1f}")
            continue
        
        # Calcular puntuación (menor es mejor)
        score = distance
        
        # Prioridad a clientes discapacitados
        if client_info['disabled']:
            score *= 0.3  # Gran bonificación para clientes discapacitados
        
        # Bonificar clientes que han esperado mucho
        waiting_time = client_info.get('waiting_time', 0.0)
        if waiting_time > 30.0:  # Más de 30 segundos esperando
            score *= max(0.1, 1.0 - (waiting_time / 180.0))  # Reduce score según tiempo esperando
        
        suitable_taxis.append((taxi_data['id'], score, distance))
        
        if score < best_score:
            best_score = score
            best_taxi = taxi_data['id']
    
    if suitable_taxis:
        suitable_taxis.sort(key=lambda x: x[1])  # Sort by score
        logger.info(f"Found {len(suitable_taxis)} suitable taxis for client, best: {suitable_taxis[0][0]} (score: {suitable_taxis[0][1]:.1f}, distance: {suitable_taxis[0][2]:.1f})")
    else:
        logger.info(f"No suitable taxi found for client (range: {max_distance:.1f}, disabled: {client_info['disabled']}, passengers: {client_info['passengers']})")
    
    return best_taxi


# Función helper para actualizar tiempo de espera de clientes
    
    return best_taxi


def ejemplo_uso_constraints():
    """
    Ejemplo de cómo usar las constraints simplificadas
    """
    # Crear constraints con valores por defecto
    constraints = TaxiConstraints(
        max_capacity=4,
        base_max_distance=30.0,  # 30km base para recoger cliente regular
        priority_disability_bonus=100
    )
    
    # Crear solver
    solver = TaxiDecisionSolver(constraints)
    
    # Estado del taxi
    taxi_state = TaxiState(
        taxi_id="taxi_01",
        current_position=(0, 0),
        max_capacity=4,
        current_passengers=1,  # Ya tiene 1 pasajero
        is_available=True
    )
    
    # Solicitud de viaje regular
    ride_request_regular = RideRequest(
        client_id="client_01",
        n_pasajeros=2,  # Necesita 2 espacios
        es_discapacitado=False,
        distancia_al_cliente=15.0,  # 15km de distancia
        client_position=(15, 10),
        destination=(25, 30)
    )
    
    # Solicitud de viaje discapacitado
    ride_request_disabled = RideRequest(
        client_id="client_02", 
        n_pasajeros=1,
        es_discapacitado=True,
        distancia_al_cliente=45.0,  # 45km - fuera del rango normal
        client_position=(-40, -35),
        destination=(40, 40)
    )
    
    # Evaluar solicitudes
    print("=== Evaluación de Solicitudes ===")
    
    # Solicitud regular
    accept, reason, details = solver.can_accept_ride(taxi_state, ride_request_regular)
    print(f"Solicitud regular: {accept} - {reason}")
    print(f"  Detalles: {details}")
    
    # Solicitud discapacitado
    accept, reason, details = solver.can_accept_ride(taxi_state, ride_request_disabled)
    print(f"Solicitud discapacitado: {accept} - {reason}")
    print(f"  Detalles: {details}")


def update_client_waiting_time(ride_request: RideRequest, delta_time: float) -> RideRequest:
    """
    Update client waiting time and expand search range accordingly
    
    Args:
        ride_request: Current ride request
        delta_time: Time elapsed since last update (seconds)
        
    Returns:
        Updated ride request with expanded range
    """
    # Update waiting time
    ride_request.tiempo_esperando += delta_time
    
    # Calculate new range multiplier (starts at 1.0, increases over time)
    time_factor = ride_request.tiempo_esperando * TaxiConstraints().range_expansion_rate
    new_multiplier = min(1.0 + time_factor, TaxiConstraints().max_range_expansion)
    
    ride_request.max_range_multiplier = new_multiplier
    
    return ride_request


def calculate_free_roam_target(current_pos: tuple, roam_radius: float, map_bounds: tuple = (-50, 50, -50, 50)) -> tuple:
    """
    Calculate a random target position for free roaming within bounds
    
    Args:
        current_pos: Current (x, y) position
        roam_radius: Maximum distance to roam from current position
        map_bounds: (min_x, max_x, min_y, max_y) boundaries
        
    Returns:
        Target (x, y) position for free roaming
    """
    import random
    
    x, y = current_pos
    min_x, max_x, min_y, max_y = map_bounds
    
    # Generate random angle and distance
    angle = random.uniform(0, 2 * math.pi)
    distance = random.uniform(roam_radius * 0.3, roam_radius)  # 30% to 100% of radius
    
    # Calculate new position
    new_x = x + distance * math.cos(angle)
    new_y = y + distance * math.sin(angle)
    
    # Clamp to map bounds
    new_x = max(min_x, min(max_x, new_x))
    new_y = max(min_y, min(max_y, new_y))
    
    return (new_x, new_y)


def generate_client_destination(client_pos: tuple, map_bounds: tuple = (-50, 50, -50, 50)) -> tuple:
    """
    Generate a random destination for a client anywhere on the map
    
    Args:
        client_pos: Client's current position (to avoid same position)
        map_bounds: (min_x, max_x, min_y, max_y) map boundaries
        
    Returns:
        Random destination (x, y) position
    """
    import random
    
    min_x, max_x, min_y, max_y = map_bounds
    min_distance = 10.0  # Minimum distance from current position
    
    # Generate random destination ensuring minimum distance
    while True:
        dest_x = random.uniform(min_x, max_x)
        dest_y = random.uniform(min_y, max_y)
        destination = (dest_x, dest_y)
        
        # Check if destination is far enough from client position
        distance = math.sqrt((dest_x - client_pos[0])**2 + (dest_y - client_pos[1])**2)
        if distance >= min_distance:
            return destination


if __name__ == "__main__":
    # Ejecutar ejemplo si se corre directamente
    ejemplo_uso_constraints()
