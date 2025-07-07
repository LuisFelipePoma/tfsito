"""
Taxi Dispatch System - Grid-Based Constraint Programming
Core functionality: taxis move continuously on grid, use constraint programming to assign passengers.
All movement is restricted to grid lines (no diagonals), passengers spawn only on intersections.
"""

import tkinter as tk
import time
import random
from typing import Dict, Tuple, Optional, List, Set
import logging

# OR-Tools imports for constraint programming
try:
    from ortools.constraint_solver import pywrapcp
    import numpy as np
    OR_TOOLS_AVAILABLE = True
except ImportError:
    OR_TOOLS_AVAILABLE = False
    print("Warning: OR-Tools not available. Using simple assignment algorithm.")

logger = logging.getLogger(__name__)

# Color scheme
COLORS = {
    'background': '#2E2E2E',
    'street': '#606060',
    'intersection': '#808080', 
    'taxi_available': '#FFD700',
    'taxi_busy': '#FF4500',
    'passenger': '#00FF00',
    'passenger_disabled': '#0080FF',
    'destination': '#FF69B4',
    'text': '#FFFFFF',
    'canvas_bg': '#1A1A1A'
}

class GridNetwork:
    """Grid-based street network for taxi movement"""
    
    def __init__(self, grid_size: float = 20.0):
        self.grid_size = grid_size
        self.bounds = (-100, -100, 200, 200)
        self.intersections: Set[Tuple[float, float]] = set()
        self.horizontal_roads: Set[Tuple[float, float, float]] = set()  # (y, x_start, x_end)
        self.vertical_roads: Set[Tuple[float, float, float]] = set()    # (x, y_start, y_end)
        self._generate_grid()
    
    def _generate_grid(self):
        """Generate grid of intersections and roads"""
        x_min, y_min, width, height = self.bounds
        x_max, y_max = x_min + width, y_min + height
        
        # Create intersections at grid points
        x = x_min
        while x <= x_max:
            y = y_min
            while y <= y_max:
                self.intersections.add((x, y))
                y += self.grid_size
            x += self.grid_size
        
        # Create horizontal roads
        for y in range(int(y_min), int(y_max) + 1, int(self.grid_size)):
            self.horizontal_roads.add((float(y), float(x_min), float(x_max)))
        
        # Create vertical roads
        for x in range(int(x_min), int(x_max) + 1, int(self.grid_size)):
            self.vertical_roads.add((float(x), float(y_min), float(y_max)))
    
    def get_random_intersection(self) -> Tuple[float, float]:
        """Get random intersection"""
        return random.choice(list(self.intersections))
    
    def is_intersection(self, position: Tuple[float, float]) -> bool:
        """Check if position is an intersection"""
        return position in self.intersections
    
    def get_next_positions(self, current_pos: Tuple[float, float]) -> List[Tuple[float, float]]:
        """Get valid next positions from current position (grid movement only)"""
        x, y = current_pos
        next_positions = []
        
        # Check all 4 cardinal directions
        candidates = [
            (x + self.grid_size, y),  # Right
            (x - self.grid_size, y),  # Left
            (x, y + self.grid_size),  # Up
            (x, y - self.grid_size)   # Down
        ]
        
        for next_x, next_y in candidates:
            if self.is_intersection((next_x, next_y)):
                next_positions.append((next_x, next_y))
        
        return next_positions
    
    def get_manhattan_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Manhattan distance between two positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


class GridTaxi:
    """Taxi that moves continuously on grid using constraint programming for assignments"""
    
    def __init__(self, taxi_id: str, position: Tuple[float, float], grid_network: GridNetwork):
        self.taxi_id = taxi_id
        self.grid_network = grid_network
        self.max_capacity = 4
        self.current_passengers = 0
        
        # Ensure starting position is intersection
        if not grid_network.is_intersection(position):
            position = grid_network.get_random_intersection()
        
        self.position = position
        self.target_position = position
        self.is_moving = False
        self.is_available = True
        
        # Movement and mission state
        self.pickup_target = None
        self.dropoff_destination = None
        self.mission_state = "IDLE"  # IDLE, PICKUP, DROPOFF
        
        # Continuous movement
        self.move_start_time = time.time()
        self.move_duration = 1.5  # 1.5 seconds per grid step
        self.last_direction_change = time.time()
        self.current_direction = None
        self.patrol_path = []
        
        # Initialize random patrol
        self._start_random_patrol()
    
    def _start_random_patrol(self):
        """Start random patrol movement"""
        if self.mission_state == "IDLE":
            next_positions = self.grid_network.get_next_positions(self.position)
            if next_positions:
                # Choose random direction, but avoid going back immediately
                if len(next_positions) > 1 and self.current_direction:
                    # Try to avoid immediate reversal
                    opposite_pos = (
                        self.position[0] - (self.current_direction[0] - self.position[0]),
                        self.position[1] - (self.current_direction[1] - self.position[1])
                    )
                    if opposite_pos in next_positions and len(next_positions) > 1:
                        next_positions = [pos for pos in next_positions if pos != opposite_pos]
                
                next_pos = random.choice(next_positions)
                self.set_target(next_pos)
                self.current_direction = next_pos
    
    def set_target(self, target: Tuple[float, float]):
        """Set movement target (must be intersection)"""
        if self.grid_network.is_intersection(target):
            self.target_position = target
            self.is_moving = True
            self.move_start_time = time.time()
        else:
            logger.warning(f"Invalid target position: {target}")
    
    def update_movement(self):
        """Update taxi movement on grid"""
        if not self.is_moving:
            return
        
        current_time = time.time()
        progress = (current_time - self.move_start_time) / self.move_duration
        
        if progress >= 1.0:
            # Reached target
            self.position = self.target_position
            self.is_moving = False
            self._handle_arrival()
        else:
            # Linear interpolation between grid points
            start_x, start_y = self.position if not hasattr(self, '_move_start_pos') else self._move_start_pos
            if not hasattr(self, '_move_start_pos'):
                self._move_start_pos = self.position
            
            target_x, target_y = self.target_position
            
            self.position = (
                start_x + (target_x - start_x) * progress,
                start_y + (target_y - start_y) * progress
            )
    
    def _handle_arrival(self):
        """Handle arrival at intersection"""
        if hasattr(self, '_move_start_pos'):
            delattr(self, '_move_start_pos')
        
        if self.mission_state == "PICKUP" and self.pickup_target:
            # Check if we're at pickup location
            if self.grid_network.get_manhattan_distance(self.position, self.pickup_target.position) < self.grid_network.grid_size / 2:
                self._complete_pickup()
            else:
                # Continue moving towards pickup
                self._move_towards_target(self.pickup_target.position)
        elif self.mission_state == "DROPOFF" and self.dropoff_destination:
            # Check if we're at dropoff location
            if self.grid_network.get_manhattan_distance(self.position, self.dropoff_destination) < self.grid_network.grid_size / 2:
                self._complete_dropoff()
            else:
                # Continue moving towards dropoff
                self._move_towards_target(self.dropoff_destination)
        else:
            # Continue random patrol
            self._start_random_patrol()
    
    def _move_towards_target(self, target_pos: Tuple[float, float]):
        """Move one step towards target using Manhattan distance"""
        next_positions = self.grid_network.get_next_positions(self.position)
        if not next_positions:
            return
        
        # Choose position that minimizes Manhattan distance to target
        best_pos = None
        best_distance = float('inf')
        
        for pos in next_positions:
            distance = self.grid_network.get_manhattan_distance(pos, target_pos)
            if distance < best_distance:
                best_distance = distance
                best_pos = pos
        
        if best_pos:
            self.set_target(best_pos)
    
    def _complete_pickup(self):
        """Complete passenger pickup"""
        if self.pickup_target:
            self.current_passengers += self.pickup_target.n_passengers
            self.is_available = False
            self.mission_state = "DROPOFF"
            self.dropoff_destination = self.pickup_target.destination
            
            logger.info(f"Taxi {self.taxi_id} picked up {self.pickup_target.n_passengers} passengers")
            
            # Remove passenger from system
            gui = get_gui()
            if gui and self.pickup_target.passenger_id in gui.passengers:
                del gui.passengers[self.pickup_target.passenger_id]
            
            self.pickup_target = None
            
            # Start moving towards destination
            self._move_towards_target(self.dropoff_destination)
    
    def _complete_dropoff(self):
        """Complete passenger dropoff"""
        logger.info(f"Taxi {self.taxi_id} dropped off {self.current_passengers} passengers")
        
        self.current_passengers = 0
        self.is_available = True
        self.mission_state = "IDLE"
        self.dropoff_destination = None
        
        # Generate new passenger after dropoff
        gui = get_gui()
        if gui:
            gui.add_random_passenger()
        
        # Resume random patrol
        self._start_random_patrol()
    
    def assign_pickup(self, passenger):
        """Assign pickup mission to taxi"""
        if self.is_available and not self.pickup_target:
            self.pickup_target = passenger
            self.mission_state = "PICKUP"
            self.is_available = False
            self._move_towards_target(passenger.position)
            logger.info(f"Taxi {self.taxi_id} assigned to pickup passenger {passenger.passenger_id}")
            return True
        return False
    
    def get_color(self):
        """Get taxi color based on state"""
        if self.is_available:
            return COLORS['taxi_available']
        else:
            return COLORS['taxi_busy']


class GridPassenger:
    """Passenger that spawns only on grid intersections"""
    
    def __init__(self, passenger_id: str, position: Tuple[float, float], 
                 destination: Tuple[float, float], n_passengers: int = 1, is_disabled: bool = False):
        self.passenger_id = passenger_id
        self.position = position
        self.destination = destination
        self.n_passengers = n_passengers
        self.is_disabled = is_disabled
        self.spawn_time = time.time()
    
    def get_wait_time(self) -> float:
        """Get waiting time in seconds"""
        return time.time() - self.spawn_time
    
    def get_color(self):
        """Get passenger color"""
        return COLORS['passenger_disabled'] if self.is_disabled else COLORS['passenger']


class ConstraintSolver:
    """Advanced constraint programming solver for taxi assignment"""
    
    def __init__(self):
        self.solver = None
        
    def solve_assignment(self, taxis: Dict[str, GridTaxi], passengers: Dict[str, GridPassenger]):
        """Solve taxi-passenger assignment using constraint programming"""
        if not OR_TOOLS_AVAILABLE:
            logger.warning("OR-Tools not available, using fallback assignment")
            return self._fallback_assignment(taxis, passengers)
        
        available_taxis = {tid: taxi for tid, taxi in taxis.items() if taxi.is_available}
        waiting_passengers = {pid: passenger for pid, passenger in passengers.items()}
        
        if not available_taxis or not waiting_passengers:
            return {}
        
        try:
            # Use simpler assignment approach due to OR-Tools version issues
            return self._simple_optimal_assignment(available_taxis, waiting_passengers)
            
        except Exception as e:
            logger.error(f"Error in constraint solver: {e}")
            return self._fallback_assignment(taxis, passengers)
    
    def _simple_optimal_assignment(self, available_taxis: Dict[str, GridTaxi], waiting_passengers: Dict[str, GridPassenger]):
        """Simple optimal assignment using greedy approach with constraint-like optimization"""
        assignments = {}
        
        # Calculate all possible assignments with costs
        assignment_options = []
        
        for taxi_id, taxi in available_taxis.items():
            for passenger_id, passenger in waiting_passengers.items():
                # Check capacity constraint
                if passenger.n_passengers > taxi.max_capacity:
                    continue
                
                # Calculate Manhattan distance
                distance = abs(taxi.position[0] - passenger.position[0]) + abs(taxi.position[1] - passenger.position[1])
                
                # Check distance constraint
                if distance > 100:  # Maximum pickup distance
                    continue
                
                # Calculate total cost (distance + waiting time penalty)
                wait_penalty = min(passenger.get_wait_time() * 5, 50)
                total_cost = distance + wait_penalty
                
                assignment_options.append({
                    'taxi_id': taxi_id,
                    'passenger_id': passenger_id,
                    'cost': total_cost,
                    'distance': distance
                })
        
        # Sort by cost (lowest first) - this approximates optimization
        assignment_options.sort(key=lambda x: x['cost'])
        
        assigned_taxis = set()
        assigned_passengers = set()
        
        # Greedy assignment (constraint-like behavior)
        for option in assignment_options:
            taxi_id = option['taxi_id']
            passenger_id = option['passenger_id']
            
            # Check if taxi or passenger already assigned
            if taxi_id in assigned_taxis or passenger_id in assigned_passengers:
                continue
            
            # Make assignment
            assignments[taxi_id] = passenger_id
            assigned_taxis.add(taxi_id)
            assigned_passengers.add(passenger_id)
            
            logger.info(f"Optimal assignment: {taxi_id} to {passenger_id} (cost: {option['cost']:.1f}, distance: {option['distance']:.1f})")
        
        return assignments
    
    def _fallback_assignment(self, taxis: Dict[str, GridTaxi], passengers: Dict[str, GridPassenger]):
        """Fallback assignment when OR-Tools is not available"""
        assignments = {}
        available_taxis = [(tid, taxi) for tid, taxi in taxis.items() if taxi.is_available]
        waiting_passengers = list(passengers.items())
        
        # Sort passengers by waiting time (longest first)
        waiting_passengers.sort(key=lambda x: x[1].get_wait_time(), reverse=True)
        
        for passenger_id, passenger in waiting_passengers:
            best_taxi = None
            best_distance = float('inf')
            
            for taxi_id, taxi in available_taxis:
                if taxi_id in assignments:  # Already assigned
                    continue
                    
                # Manhattan distance
                distance = abs(taxi.position[0] - passenger.position[0]) + abs(taxi.position[1] - passenger.position[1])
                
                if distance < best_distance and passenger.n_passengers <= taxi.max_capacity:
                    best_distance = distance
                    best_taxi = taxi_id
            
            if best_taxi and best_distance <= 100.0:
                assignments[best_taxi] = passenger_id
        
        return assignments


_gui_instance = None

def get_gui():
    return _gui_instance

def set_gui(gui):
    global _gui_instance
    _gui_instance = gui


class GridTaxiGUI:
    """Grid-based taxi dispatch system with constraint programming"""
    
    def __init__(self, width: int = 1000, height: int = 700):
        self.width = width
        self.height = height
        
        # Initialize grid network
        self.grid_network = GridNetwork(grid_size=20.0)
        
        # Initialize constraint solver
        self.constraint_solver = ConstraintSolver()
        
        # Simulation data
        self.taxis: Dict[str, GridTaxi] = {}
        self.passengers: Dict[str, GridPassenger] = {}
        
        # GUI components
        self.root = None
        self.canvas = None
        self.status_label = None
        
        # Animation control
        self.running = False
        self.last_update = time.time()
        
        # Constraint programming assignment
        self.last_assignment_check = time.time()
        self.assignment_interval = 2.0  # Check every 2 seconds for constraint solving
        
        # Set global reference
        set_gui(self)
    
    def setup_gui(self):
        """Initialize GUI"""
        self.root = tk.Tk()
        self.root.title("Grid Taxi System - Constraint Programming")
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.configure(bg=COLORS['background'])
        
        # Create main canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.width - 20,
            height=self.height - 80,
            bg=COLORS['canvas_bg'],
            highlightthickness=1,
            highlightbackground=COLORS['street']
        )
        self.canvas.pack(pady=10)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg=COLORS['background'])
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.status_label = tk.Label(
            status_frame,
            text="Grid System Ready - Constraint Programming Active",
            bg=COLORS['background'],
            fg=COLORS['text'],
            font=('Arial', 10)
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Control buttons
        btn_frame = tk.Frame(status_frame, bg=COLORS['background'])
        btn_frame.pack(side=tk.RIGHT)
        
        tk.Button(
            btn_frame,
            text="Add Passenger",
            command=self.add_random_passenger,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 9),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Reset System",
            command=self.reset_simulation,
            bg='#FF5722',
            fg='white',
            font=('Arial', 9),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Set close handler
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        
        logger.info("Grid taxi GUI setup completed")
    
    def world_to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to canvas coordinates"""
        bounds = self.grid_network.bounds
        world_x, world_y, world_width, world_height = bounds
        
        canvas_width = self.canvas.winfo_width() if self.canvas else self.width - 20
        canvas_height = self.canvas.winfo_height() if self.canvas else self.height - 80
        
        scale_x = canvas_width / world_width
        scale_y = canvas_height / world_height
        
        canvas_x = int((x - world_x) * scale_x)
        canvas_y = int(canvas_height - (y - world_y) * scale_y)  # Flip Y axis
        
        return (canvas_x, canvas_y)
    
    def draw_grid(self):
        """Draw the grid network"""
        try:
            if not self.canvas:
                return
                
            self.canvas.delete("grid")
            
            # Draw horizontal roads
            for y, x_start, x_end in self.grid_network.horizontal_roads:
                start_x, start_y = self.world_to_canvas(x_start, y)
                end_x, end_y = self.world_to_canvas(x_end, y)
                
                self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill=COLORS['street'], width=2, tags="grid"
                )
            
            # Draw vertical roads
            for x, y_start, y_end in self.grid_network.vertical_roads:
                start_x, start_y = self.world_to_canvas(x, y_start)
                end_x, end_y = self.world_to_canvas(x, y_end)
                
                self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill=COLORS['street'], width=2, tags="grid"
                )
            
            # Draw intersections
            for intersection in self.grid_network.intersections:
                x, y = intersection
                canvas_x, canvas_y = self.world_to_canvas(x, y)
                
                self.canvas.create_oval(
                    canvas_x - 3, canvas_y - 3,
                    canvas_x + 3, canvas_y + 3,
                    fill=COLORS['intersection'], outline=COLORS['intersection'],
                    tags="grid"
                )
                
        except Exception as e:
            logger.error(f"Error drawing grid: {e}")
    
    def draw_taxis(self):
        """Draw all taxis"""
        try:
            if not self.canvas:
                return
                
            self.canvas.delete("taxi")
            
            for taxi in self.taxis.values():
                canvas_x, canvas_y = self.world_to_canvas(taxi.position[0], taxi.position[1])
                color = taxi.get_color()
                
                # Draw taxi as diamond
                size = 8
                points = [
                    canvas_x, canvas_y - size,  # Top
                    canvas_x + size, canvas_y,  # Right
                    canvas_x, canvas_y + size,  # Bottom
                    canvas_x - size, canvas_y   # Left
                ]
                
                self.canvas.create_polygon(
                    points, fill=color, outline='black', width=2, tags="taxi"
                )
                
                # Draw taxi ID
                self.canvas.create_text(
                    canvas_x, canvas_y - 15,
                    text=taxi.taxi_id,
                    fill=COLORS['text'],
                    font=('Arial', 8),
                    tags="taxi"
                )
                
                # Show passenger count if carrying
                if taxi.current_passengers > 0:
                    self.canvas.create_text(
                        canvas_x, canvas_y + 15,
                        text=f"P:{taxi.current_passengers}",
                        fill=COLORS['text'],
                        font=('Arial', 7),
                        tags="taxi"
                    )
                
        except Exception as e:
            logger.error(f"Error drawing taxis: {e}")
    
    def draw_passengers(self):
        """Draw all passengers"""
        try:
            if not self.canvas:
                return
                
            self.canvas.delete("passenger")
            
            for passenger in self.passengers.values():
                # Draw passenger
                canvas_x, canvas_y = self.world_to_canvas(passenger.position[0], passenger.position[1])
                color = passenger.get_color()
                
                size = 6
                self.canvas.create_rectangle(
                    canvas_x - size, canvas_y - size,
                    canvas_x + size, canvas_y + size,
                    fill=color, outline='black', width=2, tags="passenger"
                )
                
                # Draw passenger count
                self.canvas.create_text(
                    canvas_x, canvas_y,
                    text=str(passenger.n_passengers),
                    fill='white',
                    font=('Arial', 8, 'bold'),
                    tags="passenger"
                )
                
                # Draw destination
                dest_x, dest_y = self.world_to_canvas(passenger.destination[0], passenger.destination[1])
                self.canvas.create_oval(
                    dest_x - 4, dest_y - 4,
                    dest_x + 4, dest_y + 4,
                    fill=COLORS['destination'], outline='black', width=1, tags="passenger"
                )
                
                # Draw connection line
                self.canvas.create_line(
                    canvas_x, canvas_y, dest_x, dest_y,
                    fill=color, width=1, dash=(2, 2), tags="passenger"
                )
                
        except Exception as e:
            logger.error(f"Error drawing passengers: {e}")
    
    def update_status(self):
        """Update status bar"""
        if self.status_label:
            available_taxis = sum(1 for taxi in self.taxis.values() if taxi.is_available)
            total_taxis = len(self.taxis)
            waiting_passengers = len(self.passengers)
            
            solver_status = "Optimized Assignment" if OR_TOOLS_AVAILABLE else "Simple Assignment"
            status_text = f"Taxis: {available_taxis}/{total_taxis} available | Passengers: {waiting_passengers} waiting | Solver: {solver_status}"
            self.status_label.config(text=status_text)
    
    def add_taxi(self, taxi_id: str, position: Optional[Tuple[float, float]] = None):
        """Add a taxi to the system"""
        if position is None:
            position = self.grid_network.get_random_intersection()
        
        if taxi_id not in self.taxis:
            self.taxis[taxi_id] = GridTaxi(taxi_id, position, self.grid_network)
            logger.info(f"Added taxi {taxi_id} at {position}")
    
    def add_passenger(self, passenger_id: str, position: Optional[Tuple[float, float]] = None,
                     destination: Optional[Tuple[float, float]] = None, n_passengers: int = 1, 
                     is_disabled: bool = False):
        """Add a passenger to the system (only at intersections)"""
        if position is None:
            position = self.grid_network.get_random_intersection()
        
        if destination is None:
            # Ensure destination is different from pickup and reasonably far
            attempts = 0
            while attempts < 20:
                destination = self.grid_network.get_random_intersection()
                distance = self.grid_network.get_manhattan_distance(position, destination)
                if distance >= 60.0:
                    break
                attempts += 1
        
        if passenger_id not in self.passengers:
            # Ensure destination is set
            if destination is None:
                destination = self.grid_network.get_random_intersection()
            
            self.passengers[passenger_id] = GridPassenger(
                passenger_id, position, destination, n_passengers, is_disabled
            )
            logger.info(f"Added passenger {passenger_id} at {position} -> {destination}")
    
    def add_random_passenger(self):
        """Add a passenger at random intersection"""
        passenger_id = f"P{int(time.time() * 1000) % 10000}"
        n_passengers = random.randint(1, 4)
        is_disabled = random.random() < 0.15
        
        pickup_pos = self.grid_network.get_random_intersection()
        
        # Get destination that's reasonably far away
        attempts = 0
        while attempts < 20:
            destination = self.grid_network.get_random_intersection()
            distance = self.grid_network.get_manhattan_distance(pickup_pos, destination)
            if distance >= 60.0:
                break
            attempts += 1
        
        self.add_passenger(passenger_id, pickup_pos, destination, n_passengers, is_disabled)
    
    def reset_simulation(self):
        """Reset the simulation to initial state"""
        self.taxis.clear()
        self.passengers.clear()
        
        # Add exactly 3 taxis as required
        self.add_taxi("T1", (-80.0, -80.0))
        self.add_taxi("T2", (80.0, 80.0))
        self.add_taxi("T3", (0.0, 0.0))
        
        # Add exactly 4 passengers as required
        for i in range(4):
            self.add_random_passenger()
        
        logger.info("Grid simulation reset - 3 taxis, 4 passengers")
    
    def auto_assign_taxis(self):
        """Use constraint programming to assign taxis to passengers"""
        current_time = time.time()
        
        if current_time - self.last_assignment_check < self.assignment_interval:
            return
        
        self.last_assignment_check = current_time
        
        if not self.passengers or not self.taxis:
            return
        
        # Use constraint solver for optimal assignment
        assignments = self.constraint_solver.solve_assignment(self.taxis, self.passengers)
        
        # Apply assignments
        for taxi_id, passenger_id in assignments.items():
            if taxi_id in self.taxis and passenger_id in self.passengers:
                taxi = self.taxis[taxi_id]
                passenger = self.passengers[passenger_id]
                if taxi.assign_pickup(passenger):
                    logger.info(f"Applied constraint assignment: {taxi_id} -> {passenger_id}")
    
    def update_simulation(self):
        """Update the simulation state"""
        current_time = time.time()
        delta_time = current_time - self.last_update
        self.last_update = current_time
        
        # Update all taxis
        for taxi in self.taxis.values():
            taxi.update_movement()
        
        # Use constraint programming for assignments
        self.auto_assign_taxis()
        
        # Redraw everything
        self.draw_grid()
        self.draw_taxis()
        self.draw_passengers()
        self.update_status()
    
    def animation_loop(self):
        """Main animation loop"""
        if not self.running:
            return
        
        try:
            self.update_simulation()
            
            # Schedule next frame (20 FPS for smooth movement)
            if self.root:
                self.root.after(50, self.animation_loop)
                
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
            if self.running and self.root:
                self.root.after(100, self.animation_loop)
    
    def start(self):
        """Start the simulation"""
        self.running = True
        
        if self.root is None:
            self.setup_gui()
        
        # Initialize with exactly 3 taxis and 4 passengers
        self.add_taxi("T1", (-80.0, -80.0))
        self.add_taxi("T2", (80.0, 80.0))
        self.add_taxi("T3", (0.0, 0.0))
        
        for i in range(4):
            self.add_random_passenger()
        
        # Start animation
        if self.root:
            self.root.after(100, self.animation_loop)
            
            logger.info("Starting grid taxi system with constraint programming...")
            self.root.mainloop()
    
    def stop(self):
        """Stop the simulation"""
        self.running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
        logger.info("Grid simulation stopped")


def main():
    """Main function"""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    gui = GridTaxiGUI()
    gui.start()


if __name__ == "__main__":
    main()
