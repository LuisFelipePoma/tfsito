"""
Taxi Dispatch System - Optimized Version
Core functionality: taxis pickup and dropoff passengers on street grid.
"""

import tkinter as tk
import time
import math
import random
from typing import Dict, Tuple, Optional, List
import logging

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

_gui_instance = None

def get_gui():
    return _gui_instance

def set_gui(gui):
    global _gui_instance
    _gui_instance = gui

class StreetNetwork:
    """Simple street grid for taxi movement"""
    
    def __init__(self, grid_size: float = 20.0):
        self.grid_size = grid_size
        self.bounds = (-100, -100, 200, 200)
        self.intersections = set()
        self.valid_positions = set()
        self._generate_grid()
    
    def _generate_grid(self):
        """Generate simple grid of streets and intersections"""
        x_min, y_min, width, height = self.bounds
        x_max, y_max = x_min + width, y_min + height
        
        # Create grid intersections
        x = x_min
        while x <= x_max:
            y = y_min
            while y <= y_max:
                self.intersections.add((x, y))
                self.valid_positions.add((x, y))
                y += self.grid_size
            x += self.grid_size
        
        # Add street segments between intersections
        for (x, y) in list(self.intersections):
            # Add horizontal segments
            if (x + self.grid_size, y) in self.intersections:
                mid_x = x + self.grid_size / 2
                self.valid_positions.add((mid_x, y))
            # Add vertical segments  
            if (x, y + self.grid_size) in self.intersections:
                mid_y = y + self.grid_size / 2
                self.valid_positions.add((x, mid_y))
    
    def get_random_position(self) -> Tuple[float, float]:
        """Get random valid position"""
        return random.choice(list(self.valid_positions))
    
    def get_random_intersection(self) -> Tuple[float, float]:
        """Get random intersection"""
        return random.choice(list(self.intersections))
    
    def is_valid_position(self, position: Tuple[float, float]) -> bool:
        """Check if position is valid"""
        return position in self.valid_positions
    
    def get_streets(self):
        """Get street coordinates for drawing"""
        streets = []
        x_min, y_min, width, height = self.bounds
        x_max, y_max = x_min + width, y_min + height
        
        # Horizontal streets
        for y in range(int(y_min), int(y_max) + 1, int(self.grid_size)):
            streets.append(('horizontal', y, x_min, x_max))
        
        # Vertical streets
        for x in range(int(x_min), int(x_max) + 1, int(self.grid_size)):
            streets.append(('vertical', x, y_min, y_max))
            
        return streets


class SimpleTaxi:
    """Simplified taxi focused on core pickup/dropoff functionality"""
    
    def __init__(self, taxi_id: str, position: Tuple[float, float], street_network: StreetNetwork):
        self.taxi_id = taxi_id
        self.street_network = street_network
        self.max_capacity = 4
        self.current_passengers = 0
        
        # Ensure starting position is valid
        if not street_network.is_valid_position(position):
            position = street_network.get_random_intersection()
        
        self.position = position
        self.target_position = position
        self.is_moving = False
        self.is_available = True
        
        # Mission state
        self.pickup_target = None
        self.mission_state = "IDLE"  # IDLE, PICKUP, DROPOFF
        
        # Movement timing
        self.move_start_time = time.time()
        self.move_duration = 0.8  # Faster movement: 0.8 seconds per grid move
    
    def set_target(self, target: Tuple[float, float]):
        """Set movement target (must be valid street position)"""
        if self.street_network.is_valid_position(target):
            self.target_position = target
            self.is_moving = True
            self.move_start_time = time.time()
        else:
            logger.warning(f"Invalid target position: {target}")
    
    def update_movement(self):
        """Update taxi movement along street grid"""
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
            # Interpolate position
            start_x, start_y = self.position
            target_x, target_y = self.target_position
            
            self.position = (
                start_x + (target_x - start_x) * progress,
                start_y + (target_y - start_y) * progress
            )
    
    def _handle_arrival(self):
        """Handle arrival at destination"""
        if self.mission_state == "PICKUP" and self.pickup_target:
            # Arrived at pickup location
            self._complete_pickup()
        elif self.mission_state == "DROPOFF":
            # Arrived at dropoff location
            self._complete_dropoff()
    
    def _complete_pickup(self):
        """Complete passenger pickup"""
        if self.pickup_target:
            self.current_passengers += self.pickup_target.n_passengers
            self.is_available = False
            self.mission_state = "DROPOFF"
            
            # Head to destination
            destination = self.pickup_target.destination
            self.set_target(destination)
            
            logger.info(f"Taxi {self.taxi_id} picked up {self.pickup_target.n_passengers} passengers")
            
            # Remove passenger from GUI
            gui = get_gui()
            if gui and self.pickup_target.passenger_id in gui.passengers:
                del gui.passengers[self.pickup_target.passenger_id]
            
            self.pickup_target = None
    
    def _complete_dropoff(self):
        """Complete passenger dropoff"""
        logger.info(f"Taxi {self.taxi_id} dropped off {self.current_passengers} passengers")
        
        self.current_passengers = 0
        self.is_available = True
        self.mission_state = "IDLE"
        
        # Generate new passenger after dropoff
        gui = get_gui()
        if gui:
            gui.add_random_passenger()
    
    def assign_pickup(self, passenger):
        """Assign pickup mission to taxi"""
        if self.is_available and not self.pickup_target:
            self.pickup_target = passenger
            self.mission_state = "PICKUP"
            self.is_available = False
            self.set_target(passenger.position)
            logger.info(f"Taxi {self.taxi_id} assigned to pickup passenger {passenger.passenger_id}")
            return True
        return False
    
    def get_color(self):
        """Get taxi color based on state"""
        if self.is_available:
            return COLORS['taxi_available']
        else:
            return COLORS['taxi_busy']


class SimplePassenger:
    """Simplified passenger focused on core functionality"""
    
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


class OptimizedTaxiGUI:
    """Optimized taxi dispatch system focused on core functionality"""
    
    def __init__(self, width: int = 1000, height: int = 700):
        self.width = width
        self.height = height
        
        # Initialize street network
        self.street_network = StreetNetwork(grid_size=20.0)
        
        # Simulation data
        self.taxis: Dict[str, SimpleTaxi] = {}
        self.passengers: Dict[str, SimplePassenger] = {}
        
        # Tkinter setup
        self.root = None
        self.canvas = None
        self.status_label = None
        
        # Animation control
        self.running = False
        self.last_update = time.time()
        
        # Auto-assignment system
        self.last_assignment_check = time.time()
        self.assignment_interval = 0.5  # Check every 0.5 seconds for faster response
        
        # Set global reference
        set_gui(self)
    
    def setup_gui(self):
        """Initialize optimized GUI"""
        self.root = tk.Tk()
        self.root.title("Optimized Taxi Dispatch - Street Grid System")
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
            text="System Ready",
            bg=COLORS['background'],
            fg=COLORS['text'],
            font=('Arial', 10)
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Control buttons
        btn_frame = tk.Frame(status_frame, bg=COLORS['background'])
        btn_frame.pack(side=tk.RIGHT)
        
        # Add control buttons for better user interaction
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
            text="Add Taxi",
            command=self.add_random_taxi,
            bg='#2196F3',
            fg='white',
            font=('Arial', 9),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Reset All",
            command=self.reset_simulation,
            bg='#FF5722',
            fg='white',
            font=('Arial', 9),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        
        logger.info("Optimized GUI setup completed")
    
    def world_to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to canvas coordinates"""
        # Street network bounds
        bounds = self.street_network.bounds
        world_x, world_y, world_width, world_height = bounds
        
        # Scale to canvas
        canvas_width = self.canvas.winfo_width() if self.canvas else self.width - 20
        canvas_height = self.canvas.winfo_height() if self.canvas else self.height - 80
        
        scale_x = canvas_width / world_width
        scale_y = canvas_height / world_height
        
        canvas_x = int((x - world_x) * scale_x)
        canvas_y = int(canvas_height - (y - world_y) * scale_y)  # Flip Y axis
        
        return (canvas_x, canvas_y)
    
    def draw_street_network(self):
        """Draw the street grid"""
        try:
            if not self.canvas:
                return
                
            self.canvas.delete("street")
            
            # Draw streets using simplified method
            for street_type, coord, start, end in self.street_network.get_streets():
                if street_type == 'horizontal':
                    start_x, start_y = self.world_to_canvas(start, coord)
                    end_x, end_y = self.world_to_canvas(end, coord)
                else:  # vertical
                    start_x, start_y = self.world_to_canvas(coord, start)
                    end_x, end_y = self.world_to_canvas(coord, end)
                
                self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill=COLORS['street'], width=2, tags="street"
                )
            
            # Draw intersections
            for intersection in self.street_network.intersections:
                x, y = intersection
                canvas_x, canvas_y = self.world_to_canvas(x, y)
                
                self.canvas.create_oval(
                    canvas_x - 3, canvas_y - 3,
                    canvas_x + 3, canvas_y + 3,
                    fill=COLORS['intersection'], outline=COLORS['intersection'],
                    tags="street"
                )
                
        except Exception as e:
            logger.error(f"Error drawing street network: {e}")
    
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
            
            status_text = f"Taxis: {available_taxis}/{total_taxis} available | Passengers: {waiting_passengers} waiting"
            self.status_label.config(text=status_text)
    
    def add_taxi(self, taxi_id: str, position: Optional[Tuple[float, float]] = None):
        """Add a taxi to the system"""
        if position is None:
            position = self.street_network.get_random_intersection()
        
        if taxi_id not in self.taxis:
            self.taxis[taxi_id] = SimpleTaxi(taxi_id, position, self.street_network)
            logger.info(f"Added taxi {taxi_id} at {position}")
    
    def add_passenger(self, passenger_id: str, position: Optional[Tuple[float, float]] = None,
                     destination: Optional[Tuple[float, float]] = None, n_passengers: int = 1, 
                     is_disabled: bool = False):
        """Add a passenger to the system"""
        if position is None:
            position = self.street_network.get_random_position()
        
        if destination is None:
            while True:
                destination = self.street_network.get_random_intersection()
                distance = math.sqrt((destination[0] - position[0])**2 + (destination[1] - position[1])**2)
                if distance >= 40.0:
                    break
        
        if passenger_id not in self.passengers:
            self.passengers[passenger_id] = SimplePassenger(
                passenger_id, position, destination, n_passengers, is_disabled
            )
            logger.info(f"Added passenger {passenger_id} at {position} -> {destination}")
    
    def add_random_taxi(self):
        """Add a taxi at random intersection"""
        taxi_id = f"T{len(self.taxis) + 1}"
        position = self.street_network.get_random_intersection()
        self.add_taxi(taxi_id, position)
    
    def add_random_passenger(self):
        """Add a passenger at random location with improved logic"""
        passenger_id = f"P{int(time.time() * 1000) % 10000}"
        n_passengers = random.randint(1, 4)  # 1-4 passengers
        is_disabled = random.random() < 0.15  # 15% chance for accessibility needs
        
        # Get random pickup position
        pickup_pos = self.street_network.get_random_valid_position()
        
        # Get destination that's reasonably far away
        attempts = 0
        while attempts < 20:  # Prevent infinite loop
            destination = self.street_network.get_random_intersection()
            distance = math.sqrt(
                (destination[0] - pickup_pos[0])**2 + 
                (destination[1] - pickup_pos[1])**2
            )
            if distance >= 60.0:  # Ensure minimum reasonable distance
                break
            attempts += 1
        
        self.add_passenger(passenger_id, pickup_pos, destination, n_passengers, is_disabled)
    
    def reset_simulation(self):
        """Reset the simulation to initial state"""
        self.taxis.clear()
        self.passengers.clear()
        
        # Re-add initial taxis
        self.add_taxi("T1", (-80.0, -80.0))
        self.add_taxi("T2", (80.0, 80.0))
        self.add_taxi("T3", (0.0, 0.0))
        
        # Add some passengers
        for i in range(2):
            self.add_random_passenger()
        
        logger.info("Simulation reset")
    
    def auto_assign_taxis(self):
        """Automatically assign available taxis to waiting passengers"""
        current_time = time.time()
        
        if current_time - self.last_assignment_check < self.assignment_interval:
            return
        
        self.last_assignment_check = current_time
        
        # Simple assignment: closest available taxi to longest waiting passenger
        if not self.passengers or not self.taxis:
            return
        
        # Find longest waiting passenger
        longest_wait_passenger = None
        longest_wait_time = 0
        
        for passenger in self.passengers.values():
            wait_time = passenger.get_wait_time()
            if wait_time > longest_wait_time:
                longest_wait_time = wait_time
                longest_wait_passenger = passenger
        
        if longest_wait_passenger is None:
            return
        
        # Find closest available taxi
        closest_taxi = None
        closest_distance = float('inf')
        
        for taxi in self.taxis.values():
            if taxi.is_available:
                distance = math.sqrt(
                    (taxi.position[0] - longest_wait_passenger.position[0])**2 +
                    (taxi.position[1] - longest_wait_passenger.position[1])**2
                )
                if distance < closest_distance:
                    closest_distance = distance
                    closest_taxi = taxi
        
        # Assign taxi to passenger
        if closest_taxi and closest_distance <= 100.0:  # Max pickup distance
            if closest_taxi.assign_pickup(longest_wait_passenger):
                logger.info(f"Assigned {closest_taxi.taxi_id} to {longest_wait_passenger.passenger_id}")
    
    def update_simulation(self):
        """Update the simulation state"""
        current_time = time.time()
        delta_time = current_time - self.last_update
        self.last_update = current_time
        
        # Update taxis
        for taxi in self.taxis.values():
            taxi.update_movement()
        
        # Auto-assign taxis to passengers
        self.auto_assign_taxis()
        
        # Remove completed passengers (handled by taxi dropoff)
        
        # Redraw everything
        self.draw_street_network()
        self.draw_taxis()
        self.draw_passengers()
        self.update_status()
    
    def animation_loop(self):
        """Main animation loop"""
        if not self.running:
            return
        
        try:
            self.update_simulation()
            
            # Schedule next frame (30 FPS)
            if self.root:
                self.root.after(33, self.animation_loop)
                
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
            if self.running and self.root:
                self.root.after(100, self.animation_loop)
    
    def start(self):
        """Start the simulation"""
        self.running = True
        
        if self.root is None:
            self.setup_gui()
        
        # Add initial taxis and passengers for demonstration
        self.add_taxi("T1", (-80.0, -80.0))
        self.add_taxi("T2", (80.0, 80.0))
        self.add_taxi("T3", (0.0, 0.0))
        self.add_taxi("T4", (-80.0, 80.0))
        self.add_taxi("T5", (80.0, -80.0))
        
        # Add initial passengers
        for i in range(3):
            self.add_random_passenger()
        
        # Start animation
        if self.root:
            self.root.after(100, self.animation_loop)
            
            logger.info("Starting optimized taxi dispatch system...")
            self.root.mainloop()
    
    def stop(self):
        """Stop the simulation"""
        self.running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
        logger.info("Simulation stopped")
    
    # Compatibility methods for testing
    def update(self):
        """Manual update for testing"""
        self.update_simulation()
    
    def add_client(self, client_id: str, position: Tuple[float, float], 
                   n_passengers: int = 1, is_disabled: bool = False):
        """Compatibility method"""
        self.add_passenger(client_id, position, None, n_passengers, is_disabled)


# Convenience functions
def create_gui(width: int = 1000, height: int = 700) -> OptimizedTaxiGUI:
    """Create and return a new optimized GUI instance"""
    return OptimizedTaxiGUI(width, height)


def main():
    """Main function for testing"""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    gui = create_gui()
    gui.start()


if __name__ == "__main__":
    main()
