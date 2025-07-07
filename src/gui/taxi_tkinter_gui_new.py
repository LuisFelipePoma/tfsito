"""
Tkinter GUI for taxi dispatch visualization - CYCLIC MOVEMENT SYSTEM
This version implements cyclic patrolling with constraint programming for pickup decisions.
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import math
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Colors for tkinter
COLORS = {
    'background': '#323232',
    'taxi_available': '#FFFF00',      # Yellow
    'taxi_busy': '#FFA500',           # Orange
    'taxi_moving': '#FF6464',         # Red
    'client_regular': '#00FF00',      # Green
    'client_disabled': '#0000FF',     # Blue
    'text': '#FFFFFF',                # White
    'grid': '#646464',                # Gray
    'route': '#C8C8C8',               # Light gray
    'canvas_bg': '#323232'
}

# Global GUI reference
_gui_instance = None

def get_gui():
    """Get global GUI instance"""
    return _gui_instance

def set_gui(gui):
    """Set global GUI instance"""
    global _gui_instance
    _gui_instance = gui

class TaxiVisual:
    """Visual representation of a taxi for tkinter with CYCLIC MOVEMENT SYSTEM"""
    
    def __init__(self, taxi_id: str, position: Tuple[float, float], max_capacity: int = 4):
        self.taxi_id = taxi_id
        # Grid and map settings
        self.grid_size = 10.0
        self.map_min_x = -40.0
        self.map_max_x = 40.0
        self.map_min_y = -40.0
        self.map_max_y = 40.0
        
        # Snap position to grid
        grid_x = round(position[0] / self.grid_size) * self.grid_size
        grid_y = round(position[1] / self.grid_size) * self.grid_size
        self.position = (grid_x, grid_y)
        self.target_position = self.position
        self.last_agent_position = self.position
        
        # Movement and interpolation
        self.interpolation_start_time = time.time()
        self.interpolation_duration = 2.0
        self.max_capacity = max_capacity
        self.current_passengers = 0
        self.is_available = True
        self.is_moving = False
        self.fuel_level = 1.0
        self.pickup_target: Optional['ClientVisual'] = None
        
        # CYCLIC MOVEMENT SYSTEM - Main attributes
        self.cycle_waypoints = []
        self.current_waypoint_index = 0
        self.cycle_mode = True  # True = following cycle, False = on mission
        self.cycle_speed = 1.5  # Slow cyclic movement
        self.mission_speed = 0.8  # Faster speed when on mission
        
        # Constraint programming attributes
        self.last_cp_check = time.time()
        self.cp_check_interval = 3.0  # Check for pickups every 3 seconds
        
        # Initialize the cyclic route
        self._initialize_cycle_route()
        
        # Tkinter attributes
        self.canvas_items = {}
        
    def _initialize_cycle_route(self):
        """Initialize a cyclic route based on taxi ID"""
        import random
        
        # Different cycle patterns for different taxis
        taxi_num = int(self.taxi_id.split('_')[-1]) if '_' in self.taxi_id else 0
        cycle_type = taxi_num % 4
        
        if cycle_type == 0:
            # Rectangular perimeter (clockwise)
            self.cycle_waypoints = [
                (-30.0, -30.0), (30.0, -30.0),
                (30.0, 30.0), (-30.0, 30.0)
            ]
        elif cycle_type == 1:
            # Inner rectangle (counterclockwise)
            self.cycle_waypoints = [
                (-20.0, -20.0), (-20.0, 20.0),
                (20.0, 20.0), (20.0, -20.0)
            ]
        elif cycle_type == 2:
            # Cross pattern
            self.cycle_waypoints = [
                (0.0, -40.0), (0.0, 0.0), (0.0, 40.0),
                (0.0, 0.0), (-40.0, 0.0), (0.0, 0.0),
                (40.0, 0.0), (0.0, 0.0)
            ]
        else:  # cycle_type == 3
            # Figure-8 pattern
            self.cycle_waypoints = [
                (0.0, 0.0), (-20.0, -20.0), (0.0, 0.0),
                (20.0, -20.0), (0.0, 0.0), (20.0, 20.0),
                (0.0, 0.0), (-20.0, 20.0)
            ]
        
        # Snap all waypoints to grid
        self.cycle_waypoints = [self.snap_to_grid(wp) for wp in self.cycle_waypoints]
        
        # Find closest waypoint to start
        current_pos = self.position
        min_distance = float('inf')
        closest_index = 0
        
        for i, waypoint in enumerate(self.cycle_waypoints):
            distance = math.sqrt((waypoint[0] - current_pos[0])**2 + (waypoint[1] - current_pos[1])**2)
            if distance < min_distance:
                min_distance = distance
                closest_index = i
        
        self.current_waypoint_index = closest_index
        logger.info(f"🚕 Taxi {self.taxi_id} initialized cycle type {cycle_type}, starting at waypoint {closest_index}")
    
    def snap_to_grid(self, position: Tuple[float, float]) -> Tuple[float, float]:
        """Snap position to nearest grid point"""
        x, y = position
        grid_x = round(x / self.grid_size) * self.grid_size
        grid_y = round(y / self.grid_size) * self.grid_size
        return (grid_x, grid_y)
    
    def set_target(self, target: Tuple[float, float]):
        """Set target position for taxi movement"""
        self.target_position = self.snap_to_grid(target)
        self.is_moving = True
        
        # Use appropriate speed based on mode
        if self.pickup_target is not None or self.current_passengers > 0:
            self.interpolation_duration = self.mission_speed
        else:
            self.interpolation_duration = self.cycle_speed
        
        self.interpolation_start_time = time.time()
    
    def update_agent_position(self, new_position: Tuple[float, float]):
        """Update position from agent data"""
        self.last_agent_position = self.position
        self.target_position = self.snap_to_grid(new_position)
        self.interpolation_start_time = time.time()
        self.interpolation_duration = 1.5
        self.is_moving = True
    
    def update_position(self):
        """Update visual position with smooth interpolation"""
        if not self.is_moving:
            return
            
        current_time = time.time()
        elapsed_time = current_time - self.interpolation_start_time
        interpolation_progress = min(1.0, elapsed_time / self.interpolation_duration)
        
        if interpolation_progress >= 1.0:
            # Reached target
            self.position = self.target_position
            self.is_moving = False
            
            # Handle pickup
            if self.pickup_target:
                self._handle_pickup_arrival()
        else:
            # Smooth interpolation
            start_x, start_y = self.last_agent_position
            target_x, target_y = self.target_position
            
            eased_progress = self._ease_in_out_cubic(interpolation_progress)
            
            self.position = (
                start_x + (target_x - start_x) * eased_progress,
                start_y + (target_y - start_y) * eased_progress
            )
    
    def _handle_pickup_arrival(self):
        """Handle arrival at pickup location"""
        logger.info(f"Taxi {self.taxi_id} ARRIVED at pickup location {self.position}")
        
        def complete_pickup():
            gui = get_gui()
            if gui and self.pickup_target and self.pickup_target.client_id in gui.clients:
                client_id = self.pickup_target.client_id
                client_destination = self.pickup_target.destination
                n_passengers = self.pickup_target.n_passengers
                
                self.current_passengers += n_passengers
                self.is_available = False
                
                logger.info(f"Taxi {self.taxi_id} PICKING UP {n_passengers} passengers")
                
                # Remove client from GUI
                del gui.clients[client_id]
                gui.draw_clients()
                
                # Head to destination
                self.set_target(client_destination)
                self.pickup_target = None
                
                # Schedule drop-off check
                gui.root.after(500, lambda: self._check_destination_arrival(client_destination, gui))
        
        gui = get_gui()
        if gui:
            gui.root.after(200, complete_pickup)
    
    def _check_destination_arrival(self, destination_position: Tuple[float, float], gui):
        """Check if taxi reached destination for drop-off"""
        if self.is_moving:
            gui.root.after(500, lambda: self._check_destination_arrival(destination_position, gui))
        else:
            # Complete drop-off
            passengers_dropped = self.current_passengers
            logger.info(f"Taxi {self.taxi_id} ARRIVED at destination {destination_position}")
            logger.info(f"Taxi {self.taxi_id} DROPPING OFF {passengers_dropped} passengers")
            
            self.current_passengers = 0
            self.is_available = True
            self.pickup_target = None
            
            # RESUME CYCLIC PATROL
            logger.info(f"🚕 Taxi {self.taxi_id} RESUMING CYCLIC PATROL")
            self._resume_cycle_from_position()
            
            # Generate new client
            def generate_new_client():
                import random
                new_client_id = f"auto_client_{int(time.time() * 1000)}"
                new_position = gui.generate_random_grid_position()
                new_passengers = random.randint(1, 3)
                new_disabled = random.random() < 0.15
                
                gui.add_client(new_client_id, new_position, new_passengers, new_disabled)
                logger.info(f"Generated new client {new_client_id}")
            
            gui.root.after(2000, generate_new_client)
            gui.draw_taxis()
    
    def _ease_in_out_cubic(self, t: float) -> float:
        """Cubic easing function"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def get_color(self):
        """Get color based on taxi state"""
        if self.is_moving:
            return COLORS['taxi_moving']
        elif self.is_available:
            return COLORS['taxi_available']
        else:
            return COLORS['taxi_busy']
    
    def update_continuous_movement(self):
        """CYCLIC MOVEMENT SYSTEM with constraint programming"""
        current_time = time.time()
        
        # Don't interfere if on mission
        if self.pickup_target is not None or self.current_passengers > 0:
            return
        
        if not self.is_available:
            return
        
        # Check for pickup opportunities using constraint programming
        self._check_for_pickup_opportunities()
        
        # Continue cyclic movement if still in cycle mode
        if self.cycle_mode and not self.is_moving:
            next_target = self._get_next_cycle_target()
            self.set_target(next_target)
            logger.debug(f"🚕 Taxi {self.taxi_id} continuing cycle to {next_target}")
    
    def _get_next_cycle_target(self) -> Tuple[float, float]:
        """Get next waypoint in cycle"""
        if not self.cycle_waypoints:
            return self.position
        
        self.current_waypoint_index = (self.current_waypoint_index + 1) % len(self.cycle_waypoints)
        next_waypoint = self.cycle_waypoints[self.current_waypoint_index]
        
        logger.debug(f"🚕 Taxi {self.taxi_id} cycling to waypoint {self.current_waypoint_index}: {next_waypoint}")
        return next_waypoint
    
    def _resume_cycle_from_position(self):
        """Resume cyclic movement from current position"""
        if not self.cycle_waypoints:
            return
        
        current_pos = self.position
        min_distance = float('inf')
        closest_index = 0
        
        # Find closest waypoint
        for i, waypoint in enumerate(self.cycle_waypoints):
            distance = math.sqrt((waypoint[0] - current_pos[0])**2 + (waypoint[1] - current_pos[1])**2)
            if distance < min_distance:
                min_distance = distance
                closest_index = i
        
        self.current_waypoint_index = closest_index
        self.cycle_mode = True
        
        # Head to closest waypoint
        next_target = self.cycle_waypoints[self.current_waypoint_index]
        self.set_target(next_target)
        
        logger.info(f"🚕 Taxi {self.taxi_id} resuming cycle at waypoint {closest_index}: {next_target}")
    
    def _check_for_pickup_opportunities(self):
        """Use constraint programming to check for pickup opportunities"""
        current_time = time.time()
        
        # Check periodically
        if current_time - self.last_cp_check < self.cp_check_interval:
            return
        
        self.last_cp_check = current_time
        
        # Only in cycle mode and available
        if not self.is_available or not self.cycle_mode or self.pickup_target is not None:
            return
        
        gui = get_gui()
        if not gui or not gui.clients:
            return
        
        # Use constraint programming
        try:
            from ..agent.libs.taxi_constraints import find_best_taxi_for_client
            
            for client_id, client in gui.clients.items():
                client_info = {
                    'position': client.position,
                    'passengers': client.n_passengers,
                    'disabled': client.is_disabled,
                    'waiting_time': current_time - client.request_time,
                    'range_multiplier': 1.0 + (current_time - client.request_time) * 0.02
                }
                
                taxi_info = [{
                    'id': self.taxi_id,
                    'position': self.position,
                    'capacity': self.max_capacity,
                    'current_passengers': self.current_passengers,
                    'is_available': self.is_available
                }]
                
                best_taxi = find_best_taxi_for_client(client_info, taxi_info)
                
                if best_taxi == self.taxi_id:
                    # Deviate from cycle for pickup
                    logger.info(f"🚕 Taxi {self.taxi_id} DEVIATING from cycle for client {client_id}")
                    
                    self.cycle_mode = False
                    self.pickup_target = client
                    self.is_available = False
                    
                    self.set_target(client.position)
                    break
                    
        except ImportError as e:
            logger.warning(f"Could not import constraint programming module: {e}")
        except Exception as e:
            logger.error(f"Error in constraint programming check: {e}")


class ClientVisual:
    """Visual representation of a client for tkinter"""
    
    def __init__(self, client_id: str, position: Tuple[float, float], 
                 n_passengers: int = 1, is_disabled: bool = False):
        self.client_id = client_id
        
        # Snap to grid
        self.grid_size = 10.0
        grid_x = round(position[0] / self.grid_size) * self.grid_size
        grid_y = round(position[1] / self.grid_size) * self.grid_size
        self.position = (grid_x, grid_y)
        
        self.n_passengers = n_passengers
        self.is_disabled = is_disabled
        self.is_waiting = True
        self.wait_start_time = time.time()
        self.request_time = time.time()  # For constraint programming
        self.assigned_taxi: Optional[str] = None
        
        # Dynamic range and destination
        self.waiting_time = 0.0
        self.range_multiplier = 1.0
        self.destination = self._generate_destination()
        
        # Tkinter attributes
        self.canvas_items = {}
    
    def snap_to_grid(self, position: Tuple[float, float]) -> Tuple[float, float]:
        """Snap position to grid"""
        x, y = position
        grid_x = round(x / self.grid_size) * self.grid_size
        grid_y = round(y / self.grid_size) * self.grid_size
        return (grid_x, grid_y)
    
    def _generate_destination(self) -> Tuple[float, float]:
        """Generate grid-aligned destination"""
        import random
        while True:
            grid_steps_x = random.randint(-4, 4)
            grid_steps_y = random.randint(-4, 4)
            dest_x = grid_steps_x * self.grid_size
            dest_y = grid_steps_y * self.grid_size
            
            # Ensure minimum distance
            distance = math.sqrt((dest_x - self.position[0])**2 + (dest_y - self.position[1])**2)
            if distance >= 2 * self.grid_size:
                return (dest_x, dest_y)
    
    def update_waiting_time(self, delta_time: float):
        """Update waiting time and expand search range"""
        if self.is_waiting and not self.assigned_taxi:
            self.waiting_time += delta_time
            time_factor = self.waiting_time * 0.1
            self.range_multiplier = min(1.0 + time_factor, 3.0)
    
    def get_color(self):
        """Get color based on client type"""
        if self.is_disabled:
            return COLORS['client_disabled']
        else:
            return COLORS['client_regular']
    
    def get_wait_time(self):
        """Get current wait time in minutes"""
        return (time.time() - self.wait_start_time) / 60.0


class TaxiTkinterGUI:
    """Main GUI for taxi dispatch visualization using tkinter"""
    
    def __init__(self, width: int = 1200, height: int = 800):
        self.width = width
        self.height = height
        self.running = False
        
        # Grid settings
        self.grid_size = 10.0
        
        # Simulation data
        self.taxis: Dict[str, TaxiVisual] = {}
        self.clients: Dict[str, ClientVisual] = {}
        self.simulation_bounds = (-50, -50, 100, 100)
        
        # Tkinter setup
        self.root = None
        self.canvas = None
        self.info_frame = None
        self.update_thread = None
        
        # Animation settings
        self.animation_running = False
        self.last_update_time = time.time()
        
        # Performance settings
        self.target_fps = 30
        self.frame_time = 1.0 / self.target_fps
        
        # Set global reference
        set_gui(self)
    
    def setup_gui(self):
        """Initialize tkinter GUI"""
        self.root = tk.Tk()
        self.root.title("Taxi Dispatch System - Cyclic Movement with Constraint Programming")
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.configure(bg=COLORS['background'])
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas for visualization
        self.canvas = tk.Canvas(
            main_frame,
            width=self.width - 200,
            height=self.height - 100,
            bg=COLORS['canvas_bg'],
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create info panel
        self._setup_info_panel(main_frame)
        
        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        
        logger.info("GUI setup completed")
    
    def _setup_info_panel(self, parent):
        """Setup information panel"""
        self.info_frame = ttk.Frame(parent, width=180)
        self.info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.info_frame.pack_propagate(False)
        
        # Title
        title_label = ttk.Label(self.info_frame, text="Taxi System", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Info text area
        self.info_text = tk.Text(
            self.info_frame,
            wrap=tk.WORD,
            width=22,
            height=30,
            font=('Arial', 8),
            bg='#f0f0f0',
            fg='#333333'
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def update_info_panel(self):
        """Update information panel"""
        try:
            current_time = time.time()
            
            info_text = "=== CYCLIC MOVEMENT SYSTEM ===\\n\\n"
            
            # Taxi information
            info_text += f"Taxis: {len(self.taxis)}\\n"
            for taxi_id, taxi in self.taxis.items():
                mode = "CYCLE" if taxi.cycle_mode else "MISSION"
                status = "AVAILABLE" if taxi.is_available else "BUSY"
                waypoint = taxi.current_waypoint_index if taxi.cycle_waypoints else "N/A"
                
                info_text += f"  {taxi_id}: {mode} | {status}\\n"
                info_text += f"    Position: ({taxi.position[0]:.0f}, {taxi.position[1]:.0f})\\n"
                info_text += f"    Waypoint: {waypoint}\\n"
                info_text += f"    Passengers: {taxi.current_passengers}/{taxi.max_capacity}\\n"
                
                if taxi.pickup_target:
                    info_text += f"    Target: {taxi.pickup_target.client_id}\\n"
                
                info_text += "\\n"
            
            # Client information
            info_text += f"\\nClients: {len(self.clients)}\\n"
            for client_id, client in self.clients.items():
                wait_time = (current_time - client.request_time) / 60.0
                info_text += f"  {client_id}:\\n"
                info_text += f"    Position: ({client.position[0]:.0f}, {client.position[1]:.0f})\\n"
                info_text += f"    Passengers: {client.n_passengers}\\n"
                info_text += f"    Disabled: {client.is_disabled}\\n"
                info_text += f"    Wait time: {wait_time:.1f}m\\n"
                info_text += f"    Range: {client.range_multiplier:.1f}x\\n\\n"
            
            # System information
            info_text += "\\n=== SYSTEM INFO ===\\n"
            info_text += f"Grid size: {self.grid_size}\\n"
            info_text += f"Update rate: {self.target_fps} FPS\\n"
            info_text += f"Map bounds: {self.simulation_bounds}\\n"
            
            # Clear and update text
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info_text)
            
        except Exception as e:
            logger.error(f"Error updating info panel: {e}")
    
    def world_to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to canvas coordinates"""
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return (0, 0)
        
        # World bounds
        world_x, world_y, world_width, world_height = self.simulation_bounds
        
        # Scale to canvas
        scale_x = canvas_width / world_width
        scale_y = canvas_height / world_height
        
        canvas_x = int((x - world_x) * scale_x)
        canvas_y = int(canvas_height - (y - world_y) * scale_y)  # Flip Y axis
        
        return (canvas_x, canvas_y)
    
    def add_taxi(self, taxi_id: str, position: Tuple[float, float], max_capacity: int = 4):
        """Add a taxi to the simulation"""
        if taxi_id not in self.taxis:
            self.taxis[taxi_id] = TaxiVisual(taxi_id, position, max_capacity)
            logger.info(f"Added taxi {taxi_id} at {position} with cyclic movement")
        else:
            logger.warning(f"Taxi {taxi_id} already exists")
    
    def add_client(self, client_id: str, position: Tuple[float, float], 
                   n_passengers: int = 1, is_disabled: bool = False):
        """Add a client to the simulation"""
        if client_id not in self.clients:
            self.clients[client_id] = ClientVisual(client_id, position, n_passengers, is_disabled)
            logger.info(f"Added client {client_id} at {position} ({n_passengers} passengers, disabled: {is_disabled})")
        else:
            logger.warning(f"Client {client_id} already exists")
    
    def generate_random_grid_position(self) -> Tuple[float, float]:
        """Generate random position aligned to grid"""
        import random
        
        # Grid bounds
        min_grid_x = int(self.simulation_bounds[0] / self.grid_size)
        max_grid_x = int((self.simulation_bounds[0] + self.simulation_bounds[2]) / self.grid_size)
        min_grid_y = int(self.simulation_bounds[1] / self.grid_size)
        max_grid_y = int((self.simulation_bounds[1] + self.simulation_bounds[3]) / self.grid_size)
        
        grid_x = random.randint(min_grid_x, max_grid_x)
        grid_y = random.randint(min_grid_y, max_grid_y)
        
        return (grid_x * self.grid_size, grid_y * self.grid_size)
    
    def draw_grid(self):
        """Draw grid lines on canvas"""
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                return
            
            # Clear existing grid
            self.canvas.delete("grid")
            
            # World bounds
            world_x, world_y, world_width, world_height = self.simulation_bounds
            
            # Draw vertical lines
            x = world_x
            while x <= world_x + world_width:
                if x % self.grid_size == 0:  # Only draw on grid lines
                    canvas_x1, canvas_y1 = self.world_to_canvas(x, world_y)
                    canvas_x2, canvas_y2 = self.world_to_canvas(x, world_y + world_height)
                    
                    self.canvas.create_line(
                        canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                        fill=COLORS['grid'], width=1, tags="grid"
                    )
                x += self.grid_size
            
            # Draw horizontal lines
            y = world_y
            while y <= world_y + world_height:
                if y % self.grid_size == 0:  # Only draw on grid lines
                    canvas_x1, canvas_y1 = self.world_to_canvas(world_x, y)
                    canvas_x2, canvas_y2 = self.world_to_canvas(world_x + world_width, y)
                    
                    self.canvas.create_line(
                        canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                        fill=COLORS['grid'], width=1, tags="grid"
                    )
                y += self.grid_size
            
        except Exception as e:
            logger.error(f"Error drawing grid: {e}")
    
    def draw_taxis(self):
        """Draw all taxis on canvas"""
        try:
            # Clear existing taxis
            self.canvas.delete("taxi")
            
            for taxi_id, taxi in self.taxis.items():
                canvas_x, canvas_y = self.world_to_canvas(taxi.position[0], taxi.position[1])
                color = taxi.get_color()
                
                # Draw taxi as circle
                size = 8
                self.canvas.create_oval(
                    canvas_x - size, canvas_y - size,
                    canvas_x + size, canvas_y + size,
                    fill=color, outline='black', width=2, tags="taxi"
                )
                
                # Draw taxi ID
                self.canvas.create_text(
                    canvas_x, canvas_y - 15,
                    text=taxi_id, fill=COLORS['text'],
                    font=('Arial', 8), tags="taxi"
                )
                
                # Draw waypoint path for taxis in cycle mode
                if taxi.cycle_mode and taxi.cycle_waypoints:
                    for i, waypoint in enumerate(taxi.cycle_waypoints):
                        wp_x, wp_y = self.world_to_canvas(waypoint[0], waypoint[1])
                        
                        # Draw waypoint
                        wp_size = 3
                        wp_color = '#FFD700' if i == taxi.current_waypoint_index else '#808080'
                        self.canvas.create_oval(
                            wp_x - wp_size, wp_y - wp_size,
                            wp_x + wp_size, wp_y + wp_size,
                            fill=wp_color, outline='black', width=1, tags="taxi"
                        )
                        
                        # Draw path lines
                        if i < len(taxi.cycle_waypoints) - 1:
                            next_wp = taxi.cycle_waypoints[i + 1]
                            next_wp_x, next_wp_y = self.world_to_canvas(next_wp[0], next_wp[1])
                            self.canvas.create_line(
                                wp_x, wp_y, next_wp_x, next_wp_y,
                                fill='#404040', width=1, tags="taxi"
                            )
                        else:
                            # Connect last waypoint to first
                            first_wp = taxi.cycle_waypoints[0]
                            first_wp_x, first_wp_y = self.world_to_canvas(first_wp[0], first_wp[1])
                            self.canvas.create_line(
                                wp_x, wp_y, first_wp_x, first_wp_y,
                                fill='#404040', width=1, tags="taxi"
                            )
                
        except Exception as e:
            logger.error(f"Error drawing taxis: {e}")
    
    def draw_clients(self):
        """Draw all clients on canvas"""
        try:
            # Clear existing clients
            self.canvas.delete("client")
            
            for client_id, client in self.clients.items():
                canvas_x, canvas_y = self.world_to_canvas(client.position[0], client.position[1])
                color = client.get_color()
                
                # Draw client as square
                size = 6
                self.canvas.create_rectangle(
                    canvas_x - size, canvas_y - size,
                    canvas_x + size, canvas_y + size,
                    fill=color, outline='black', width=2, tags="client"
                )
                
                # Draw client ID
                self.canvas.create_text(
                    canvas_x, canvas_y + 15,
                    text=f"{client_id} ({client.n_passengers})",
                    fill=COLORS['text'], font=('Arial', 8), tags="client"
                )
                
                # Draw destination
                dest_x, dest_y = self.world_to_canvas(client.destination[0], client.destination[1])
                self.canvas.create_oval(
                    dest_x - 4, dest_y - 4,
                    dest_x + 4, dest_y + 4,
                    fill='white', outline=color, width=2, tags="client"
                )
                
                # Draw line to destination
                self.canvas.create_line(
                    canvas_x, canvas_y, dest_x, dest_y,
                    fill=color, width=2, dash=(3, 3), tags="client"
                )
                
        except Exception as e:
            logger.error(f"Error drawing clients: {e}")
    
    def update_visualization(self):
        """Update the visualization"""
        try:
            current_time = time.time()
            delta_time = current_time - self.last_update_time
            self.last_update_time = current_time
            
            # Update taxi positions and movements
            for taxi in self.taxis.values():
                taxi.update_position()
                taxi.update_continuous_movement()  # CYCLIC MOVEMENT SYSTEM
            
            # Update client waiting times
            for client in self.clients.values():
                client.update_waiting_time(delta_time)
            
            # Redraw everything
            self.draw_grid()
            self.draw_taxis()
            self.draw_clients()
            self.update_info_panel()
            
        except Exception as e:
            logger.error(f"Error in update_visualization: {e}")
    
    def animation_loop(self):
        """Main animation loop"""
        if not self.animation_running:
            return
        
        try:
            start_time = time.time()
            
            # Update visualization
            self.update_visualization()
            
            # Calculate frame timing
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.frame_time - elapsed_time)
            
            # Schedule next frame
            self.root.after(int(sleep_time * 1000), self.animation_loop)
            
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
            if self.animation_running:
                self.root.after(100, self.animation_loop)  # Retry after 100ms
    
    def start(self):
        """Start the GUI"""
        self.running = True
        self.animation_running = True
        
        # Setup GUI if not done
        if self.root is None:
            self.setup_gui()
        
        # Start animation loop
        self.root.after(100, self.animation_loop)
        
        logger.info("Starting GUI with cyclic movement system...")
        
        # Start tkinter main loop
        self.root.mainloop()
    
    def stop(self):
        """Stop the GUI"""
        self.running = False
        self.animation_running = False
        
        if self.root:
            self.root.quit()
            self.root.destroy()
        
        logger.info("GUI stopped")
    
    def update_taxi_position(self, taxi_id: str, new_position: Tuple[float, float]):
        """Update taxi position from external source"""
        if taxi_id in self.taxis:
            self.taxis[taxi_id].update_agent_position(new_position)
        else:
            logger.warning(f"Taxi {taxi_id} not found for position update")
    
    def remove_client(self, client_id: str):
        """Remove a client from the simulation"""
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"Removed client {client_id}")
        else:
            logger.warning(f"Client {client_id} not found for removal")


# Convenience functions for external use
def create_gui(width: int = 1200, height: int = 800) -> TaxiTkinterGUI:
    """Create and return a new GUI instance"""
    return TaxiTkinterGUI(width, height)

def main():
    """Main function for testing"""
    logging.basicConfig(level=logging.INFO)
    
    gui = create_gui()
    
    # Add some test taxis with different cycle patterns
    gui.add_taxi("taxi_0", (-10, -10))  # Rectangular perimeter
    gui.add_taxi("taxi_1", (10, 10))    # Inner rectangle
    gui.add_taxi("taxi_2", (0, 0))      # Cross pattern
    gui.add_taxi("taxi_3", (20, -20))   # Figure-8
    
    # Add some test clients
    gui.add_client("client_1", (-25, 15), 2, False)
    gui.add_client("client_2", (30, -25), 1, True)  # Disabled client
    gui.add_client("client_3", (15, 35), 3, False)
    
    # Start GUI
    gui.start()

if __name__ == "__main__":
    main()
