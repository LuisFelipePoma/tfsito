"""
Tkinter GUI for taxi dispatch visualization - High performance version
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

class TaxiVisual:
    """Visual representation of a taxi for tkinter"""
    
    def __init__(self, taxi_id: str, position: Tuple[float, float], max_capacity: int = 4):
        self.taxi_id = taxi_id
        self.position = position
        self.target_position = position
        self.last_agent_position = position
        self.interpolation_start_time = time.time()
        self.interpolation_duration = 2.0  # Slower, more realistic movement (2 seconds per movement)
        self.max_capacity = max_capacity
        self.current_passengers = 0
        self.is_available = True
        self.is_moving = False
        self.fuel_level = 1.0
        self.pickup_target: Optional['ClientVisual'] = None
        
        # Free roaming attributes
        self.free_roam_target: Optional[Tuple[float, float]] = None
        self.last_roam_update = time.time()
        self.roam_interval = 8.0  # Change direction every 8 seconds (slower)
        self.roam_speed = 0.8  # Much slower speed for free roaming
        
        # Tkinter specific attributes
        self.canvas_items = {}  # Store canvas item IDs
        
    def set_target(self, target: Tuple[float, float]):
        """Set target position for taxi movement"""
        self.target_position = target
        self.is_moving = True
        
    def update_agent_position(self, new_position: Tuple[float, float]):
        """Update position from agent data with smooth interpolation"""
        self.last_agent_position = self.position
        self.target_position = new_position
        self.interpolation_start_time = time.time()
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
            
            # Check if picking up passenger
            if self.pickup_target:
                logger.info(f"Taxi {self.taxi_id} ARRIVED at pickup location {self.position} for client {self.pickup_target.client_id}")
                
                # Schedule pickup completion using tkinter's after() method - slower pickup
                def complete_pickup():
                    gui = get_gui()
                    if gui and self.pickup_target and self.pickup_target.client_id in gui.clients:
                        # Pick up passengers
                        client_id = self.pickup_target.client_id
                        client_destination = self.pickup_target.destination
                        n_passengers = self.pickup_target.n_passengers
                        
                        self.current_passengers += n_passengers
                        self.is_available = False
                        
                        logger.info(f"Taxi {self.taxi_id} PICKING UP {n_passengers} passengers from client {client_id}")
                        
                        # Remove the client from GUI
                        del gui.clients[client_id]
                        logger.info(f"Taxi {self.taxi_id} COMPLETED pickup of client {client_id}, NOW HEADING to destination {client_destination}")
                        
                        # Force a redraw to remove client visually
                        gui.draw_clients()
                        
                        # Set destination as client's chosen destination with slower movement
                        self.set_target(client_destination)
                        self.pickup_target = None
                        self.interpolation_duration = 3.0  # Even slower when carrying passengers
                        
                        # Schedule drop-off check with longer intervals
                        gui.root.after(500, lambda: self._check_destination_arrival(client_destination, gui))
                    else:
                        logger.warning(f"Taxi {self.taxi_id} arrived for pickup but client {self.pickup_target.client_id if self.pickup_target else 'None'} not found!")
                
                # Use tkinter's after() to avoid threading issues - wait longer for pickup
                gui = get_gui()
                if gui:
                    gui.root.after(200, complete_pickup)  # Longer pickup time
        else:
            # Smoothly interpolate between last position and target
            start_x, start_y = self.last_agent_position
            target_x, target_y = self.target_position
            
            # Use easing for smoother animation
            eased_progress = self._ease_in_out_cubic(interpolation_progress)
            
            self.position = (
                start_x + (target_x - start_x) * eased_progress,
                start_y + (target_y - start_y) * eased_progress
            )
    
    def _check_destination_arrival(self, destination_position: Tuple[float, float], gui):
        """Check if taxi has reached the destination for passenger drop-off"""
        if self.is_moving:
            # Still moving, check again later with longer interval
            gui.root.after(500, lambda: self._check_destination_arrival(destination_position, gui))
        else:
            # Arrived at destination, drop passengers
            passengers_dropped = self.current_passengers
            logger.info(f"Taxi {self.taxi_id} ARRIVED at destination {destination_position}")
            logger.info(f"Taxi {self.taxi_id} DROPPING OFF {passengers_dropped} passengers")
            
            self.current_passengers = 0
            self.is_available = True
            self.interpolation_duration = 2.0  # Reset to normal speed after drop-off
            
            logger.info(f"Taxi {self.taxi_id} COMPLETED FULL RIDE CYCLE - now available for new pickups")
            logger.info(f"Taxi {self.taxi_id} STATUS: available={self.is_available}, passengers={self.current_passengers}, pickup_target={self.pickup_target}")
            
            # Start free roaming immediately after drop-off
            self.free_roam_target = None  # Reset roaming target
            
            # Generate new client after drop-off with delay to make it more visible
            def generate_new_client():
                import random
                new_client_id = f"auto_client_{int(time.time() * 1000)}"
                new_position = (random.uniform(-40, 40), random.uniform(-40, 40))
                new_passengers = random.randint(1, 3)
                new_disabled = random.random() < 0.15
                
                gui.add_client(new_client_id, new_position, new_passengers, new_disabled)
                logger.info(f"Generated new client {new_client_id} at {new_position} ({new_passengers} passengers)")
            
            # Wait a bit before generating new client to make the process more visible
            gui.root.after(2000, generate_new_client)  # 2 second delay
            
            # Force redraw to show taxi status change
            gui.draw_taxis()
    
    def _ease_in_out_cubic(self, t: float) -> float:
        """Cubic easing function for smooth animation"""
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

    def update_free_roaming(self):
        """Update taxi position for free roaming when not on a mission"""
        current_time = time.time()
        
        # STRICT CHECK: Only free roam if completely available and not assigned
        if (not self.is_available or 
            self.pickup_target is not None or 
            self.current_passengers > 0 or
            self.is_moving):  # Don't start new roaming if already moving to pickup/destination
            return
        
        # Check if we need a new roaming target
        if (self.free_roam_target is None or 
            current_time - self.last_roam_update > self.roam_interval):
            
            # Generate new roaming target using constraints function
            try:
                from agent.libs.taxi_constraints import calculate_free_roam_target
                self.free_roam_target = calculate_free_roam_target(
                    self.position, 
                    roam_radius=12.0  # Smaller radius for more contained movement
                )
                self.set_target(self.free_roam_target)
                self.last_roam_update = current_time
                self.is_moving = True
                logger.debug(f"Taxi {self.taxi_id} starting free roam to {self.free_roam_target}")
                
            except ImportError:
                # Fallback if constraints not available
                import random
                x, y = self.position
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(5.0, 12.0)
                new_x = max(-50, min(50, x + distance * math.cos(angle)))
                new_y = max(-50, min(50, y + distance * math.sin(angle)))
                self.free_roam_target = (new_x, new_y)
                self.set_target(self.free_roam_target)
                self.last_roam_update = current_time
                self.is_moving = True

class ClientVisual:
    """Visual representation of a client for tkinter"""
    
    def __init__(self, client_id: str, position: Tuple[float, float], 
                 n_passengers: int = 1, is_disabled: bool = False):
        self.client_id = client_id
        self.position = position
        self.n_passengers = n_passengers
        self.is_disabled = is_disabled
        self.is_waiting = True
        self.wait_start_time = time.time()
        self.assigned_taxi: Optional[str] = None
        
        # Dynamic range and destination attributes
        self.waiting_time = 0.0  # Seconds waiting for pickup
        self.range_multiplier = 1.0  # Current search range multiplier
        self.destination = self._generate_destination()  # Client chooses destination
        
        # Tkinter specific attributes
        self.canvas_items = {}  # Store canvas item IDs
        
    def _generate_destination(self) -> Tuple[float, float]:
        """Generate a destination chosen by the client"""
        try:
            from agent.libs.taxi_constraints import generate_client_destination
            return generate_client_destination(self.position)
        except ImportError:
            # Fallback destination generation
            import random
            while True:
                dest_x = random.uniform(-45, 45)
                dest_y = random.uniform(-45, 45)
                # Ensure minimum distance from current position
                import math
                distance = math.sqrt((dest_x - self.position[0])**2 + (dest_y - self.position[1])**2)
                if distance >= 10.0:
                    return (dest_x, dest_y)
    
    def update_waiting_time(self, delta_time: float):
        """Update waiting time and expand search range"""
        if self.is_waiting and not self.assigned_taxi:
            self.waiting_time += delta_time
            
            # Update range multiplier (expand range over time)
            time_factor = self.waiting_time * 0.1  # 10% expansion per second
            self.range_multiplier = min(1.0 + time_factor, 3.0)  # Max 3x expansion
        
        # Tkinter specific attributes
        self.canvas_items = {}  # Store canvas item IDs
        
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
        
        # Simulation data
        self.taxis: Dict[str, TaxiVisual] = {}
        self.clients: Dict[str, ClientVisual] = {}
        self.simulation_bounds = (-50, -50, 100, 100)  # x, y, width, height
        
        # Tkinter setup
        self.root = tk.Tk()
        self.root.title("Taxi Dispatch System - Tkinter")
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg=COLORS['background'])
        
        # Create main frame
        self.main_frame = tk.Frame(self.root, bg=COLORS['background'])
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas for visualization
        self.canvas_height = height - 100  # Leave space for UI
        self.canvas = tk.Canvas(
            self.main_frame, 
            width=width-20, 
            height=self.canvas_height,
            bg=COLORS['canvas_bg'],
            highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        # Create UI frame
        self.ui_frame = tk.Frame(self.main_frame, bg=COLORS['background'], height=80)
        self.ui_frame.pack(fill=tk.X, padx=10, pady=5)
        self.ui_frame.pack_propagate(False)
        
        # Stats labels
        self.stats_frame = tk.Frame(self.ui_frame, bg=COLORS['background'])
        self.stats_frame.pack(side=tk.LEFT)
        
        self.taxis_label = tk.Label(
            self.stats_frame, 
            text="Taxis: 0", 
            fg=COLORS['text'], 
            bg=COLORS['background'],
            font=('Arial', 10)
        )
        self.taxis_label.pack(side=tk.LEFT, padx=5)
        
        self.clients_label = tk.Label(
            self.stats_frame, 
            text="Clients: 0", 
            fg=COLORS['text'], 
            bg=COLORS['background'],
            font=('Arial', 10)
        )
        self.clients_label.pack(side=tk.LEFT, padx=5)
        
        self.fps_label = tk.Label(
            self.stats_frame, 
            text="FPS: --", 
            fg=COLORS['text'], 
            bg=COLORS['background'],
            font=('Arial', 10)
        )
        self.fps_label.pack(side=tk.LEFT, padx=5)
        
        # Control buttons
        self.controls_frame = tk.Frame(self.ui_frame, bg=COLORS['background'])
        self.controls_frame.pack(side=tk.RIGHT)
        
        self.pause_button = tk.Button(
            self.controls_frame,
            text="Pause",
            command=self.toggle_pause,
            bg='#555555',
            fg=COLORS['text'],
            font=('Arial', 9)
        )
        self.pause_button.pack(side=tk.RIGHT, padx=5)
        
        # Performance monitoring
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.paused = False
        
        # Draw initial grid
        self.draw_grid()
        
        # Bind events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Stats
        self.stats = {
            'completed_rides': 0
        }
        
    def world_to_screen(self, world_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        world_x, world_y = world_pos
        bounds_x, bounds_y, bounds_w, bounds_h = self.simulation_bounds
        
        # Map world coordinates to screen space (with margin)
        margin = 50
        screen_w = self.width - 2 * margin
        screen_h = self.canvas_height - 2 * margin
        
        screen_x = margin + ((world_x - bounds_x) / bounds_w) * screen_w
        screen_y = margin + ((world_y - bounds_y) / bounds_h) * screen_h
        
        return (int(screen_x), int(screen_y))
    
    def screen_to_world(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to world coordinates"""
        screen_x, screen_y = screen_pos
        bounds_x, bounds_y, bounds_w, bounds_h = self.simulation_bounds
        
        margin = 50
        screen_w = self.width - 2 * margin
        screen_h = self.canvas_height - 2 * margin
        
        world_x = bounds_x + ((screen_x - margin) / screen_w) * bounds_w
        world_y = bounds_y + ((screen_y - margin) / screen_h) * bounds_h
        
        return (world_x, world_y)
    
    def draw_grid(self):
        """Draw background grid on canvas"""
        # Clear any existing grid
        self.canvas.delete("grid")
        
        margin = 50
        grid_size = 100  # Grid spacing
        
        # Draw vertical lines
        for x in range(margin, self.width - margin, grid_size):
            self.canvas.create_line(
                x, margin, x, self.canvas_height - margin,
                fill=COLORS['grid'], width=1, tags="grid"
            )
        
        # Draw horizontal lines
        for y in range(margin, self.canvas_height - margin, grid_size):
            self.canvas.create_line(
                margin, y, self.width - margin, y,
                fill=COLORS['grid'], width=1, tags="grid"
            )
    
    def add_taxi(self, taxi_id: str, position: Tuple[float, float], max_capacity: int = 4):
        """Add a taxi to the visualization"""
        self.taxis[taxi_id] = TaxiVisual(taxi_id, position, max_capacity)
        logger.info(f"Added taxi {taxi_id} at position {position}")
        self.update_stats()
    
    def add_client(self, client_id: str, position: Tuple[float, float], 
                   n_passengers: int = 1, is_disabled: bool = False):
        """Add a client to the visualization"""
        self.clients[client_id] = ClientVisual(client_id, position, n_passengers, is_disabled)
        logger.info(f"Added client {client_id} at position {position}")
        self.update_stats()
    
    def update_taxi_state(self, taxi_id: str, state_data: dict):
        """Update taxi state from agent data"""
        if taxi_id in self.taxis:
            taxi = self.taxis[taxi_id]
            
            # Handle position update with smooth interpolation
            if 'position' in state_data:
                new_position = state_data['position']
                # Only update if position has actually changed
                if new_position != taxi.position:
                    taxi.update_agent_position(new_position)
                    
            if 'current_passengers' in state_data:
                taxi.current_passengers = state_data['current_passengers']
            if 'is_available' in state_data:
                taxi.is_available = state_data['is_available']
            if 'fuel_level' in state_data:
                taxi.fuel_level = state_data['fuel_level']
    
    def assign_taxi_to_client(self, taxi_id: str, client_id: str):
        """Assign a taxi to pick up a client"""
        if taxi_id in self.taxis and client_id in self.clients:
            taxi = self.taxis[taxi_id]
            client = self.clients[client_id]
            
            # COMPLETELY STOP free roaming and assign pickup target
            taxi.is_available = False  # Mark as unavailable for other assignments
            taxi.free_roam_target = None  # Stop free roaming
            taxi.pickup_target = client
            client.assigned_taxi = taxi_id
            
            # Reset interpolation for immediate pickup mission
            taxi.last_agent_position = taxi.position
            taxi.interpolation_start_time = time.time()
            
            # Set taxi target to client position with smooth movement
            taxi.set_target(client.position)
            taxi.is_moving = True
            
            logger.info(f"Taxi {taxi_id} assigned to client {client_id} - STOPPING all free roaming, going to pickup at {client.position}")
            logger.info(f"   Client destination: {client.destination}, passengers: {client.n_passengers}")
            
            # Force immediate redraw to show assignment
            self.draw_taxis()
    
    def maintain_client_population(self, min_clients: int = 5):
        """Maintain a minimum number of clients in the simulation"""
        if not self.running:
            return
            
        current_count = len(self.clients)
        
        if current_count < min_clients:
            # Add one client at a time to avoid overwhelming
            import random
            client_id = f"maintenance_client_{int(time.time() * 1000)}_{random.randint(0, 999)}"
            position = (random.uniform(-40, 40), random.uniform(-40, 40))
            passengers = random.randint(1, 3)
            disabled = random.random() < 0.12  # 12% chance
            
            self.add_client(client_id, position, passengers, disabled)
            logger.info(f"Added maintenance client {client_id} to maintain population")
        
        # Schedule next check using tkinter's after() method
        self.root.after(3000, lambda: self.maintain_client_population(min_clients))
    
    def start_client_population_manager(self, min_clients: int = 5, check_interval: int = 3):
        """Start client population management using tkinter scheduling"""
        logger.info(f"Started client population manager (min: {min_clients})")
        # Use tkinter's after() method instead of threading to avoid thread safety issues
        self.root.after(2000, lambda: self.maintain_client_population(min_clients))

    def complete_ride(self, client_id: str):
        """Complete a ride and remove client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.assigned_taxi and client.assigned_taxi in self.taxis:
                taxi = self.taxis[client.assigned_taxi]
                # Generate random destination and move taxi there
                import random
                destination = (random.uniform(-40, 40), random.uniform(-40, 40))
                taxi.set_target(destination)
                
                # Schedule passenger drop-off
                def drop_passengers():
                    taxi.current_passengers = 0
                    taxi.is_available = True
                
                # Drop passengers after reaching destination
                threading.Timer(5.0, drop_passengers).start()
            
            del self.clients[client_id]
            self.stats['completed_rides'] += 1
            self.update_stats()
            logger.info(f"Completed ride for client {client_id}")
    
    def handle_ride_request(self, client_id: str, taxi_responses: List[dict]):
        """Handle ride request responses from taxis"""
        # Find accepting taxi
        accepting_taxi = None
        for response in taxi_responses:
            if response.get('accepted', False):
                accepting_taxi = response.get('taxi_id')
                break
        
        if accepting_taxi:
            self.assign_taxi_to_client(accepting_taxi, client_id)
            
            # Schedule ride completion
            def complete_later():
                time.sleep(10)  # Simulate ride duration
                self.complete_ride(client_id)
            
            threading.Thread(target=complete_later, daemon=True).start()
    
    def draw_taxis(self):
        """Draw all taxis on canvas"""
        # Clear existing taxi items
        self.canvas.delete("taxi")
        
        for taxi in self.taxis.values():
            screen_pos = self.world_to_screen(taxi.position)
            color = taxi.get_color()
            
            # Draw taxi as rectangle
            taxi_size = 8
            x1, y1 = screen_pos[0] - taxi_size, screen_pos[1] - taxi_size
            x2, y2 = screen_pos[0] + taxi_size, screen_pos[1] + taxi_size
            
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color, outline=color,
                tags="taxi"
            )
            
            # Draw movement line
            if taxi.is_moving:
                target_screen = self.world_to_screen(taxi.target_position)
                self.canvas.create_line(
                    screen_pos[0], screen_pos[1],
                    target_screen[0], target_screen[1],
                    fill=COLORS['route'], width=1,
                    tags="taxi"
                )
            
            # Draw taxi ID (for small number of taxis)
            if len(self.taxis) < 8:
                self.canvas.create_text(
                    screen_pos[0], screen_pos[1] - 15,
                    text=taxi.taxi_id[-1],
                    fill=COLORS['text'],
                    font=('Arial', 8),
                    tags="taxi"
                )
            
            # Show passenger count
            if taxi.current_passengers > 0:
                self.canvas.create_oval(
                    screen_pos[0] + 6, screen_pos[1] - 10,
                    screen_pos[0] + 10, screen_pos[1] - 6,
                    fill=COLORS['text'], outline=COLORS['text'],
                    tags="taxi"
                )
    
    def draw_clients(self):
        """Draw all clients on canvas"""
        # Clear existing client items
        self.canvas.delete("client")
        
        for client in self.clients.values():
            screen_pos = self.world_to_screen(client.position)
            color = client.get_color()
            
            # Draw client as circle
            client_radius = 6
            x1, y1 = screen_pos[0] - client_radius, screen_pos[1] - client_radius
            x2, y2 = screen_pos[0] + client_radius, screen_pos[1] + client_radius
            
            self.canvas.create_oval(
                x1, y1, x2, y2,
                fill=color, outline=color,
                tags="client"
            )
            
            # Inner circle for person representation
            inner_radius = 3
            x1_inner, y1_inner = screen_pos[0] - inner_radius, screen_pos[1] - inner_radius
            x2_inner, y2_inner = screen_pos[0] + inner_radius, screen_pos[1] + inner_radius
            
            self.canvas.create_oval(
                x1_inner, y1_inner, x2_inner, y2_inner,
                fill=COLORS['text'], outline=COLORS['text'],
                tags="client"
            )
            
            # Draw destination indicator (small dot with line)
            if hasattr(client, 'destination') and client.destination:
                dest_screen = self.world_to_screen(client.destination)
                
                # Line to destination
                self.canvas.create_line(
                    screen_pos[0], screen_pos[1],
                    dest_screen[0], dest_screen[1],
                    fill=color, width=1, dash=(2, 2),
                    tags="client"
                )
                
                # Destination marker
                dest_size = 3
                dx1, dy1 = dest_screen[0] - dest_size, dest_screen[1] - dest_size
                dx2, dy2 = dest_screen[0] + dest_size, dest_screen[1] + dest_size
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2,
                    fill=color, outline=color,
                    tags="client"
                )
            
            # Show waiting time and range multiplier for long waits
            if hasattr(client, 'waiting_time') and client.waiting_time > 10.0:
                wait_text = f"{client.waiting_time:.0f}s ({client.range_multiplier:.1f}x)"
                self.canvas.create_text(
                    screen_pos[0], screen_pos[1] + 20,
                    text=wait_text,
                    fill=COLORS['text'],
                    font=('Arial', 7),
                    tags="client"
                )
    
    def update_stats(self):
        """Update UI statistics"""
        self.taxis_label.config(text=f"Taxis: {len(self.taxis)}")
        self.clients_label.config(text=f"Clients: {len(self.clients)}")
        self.fps_label.config(text=f"FPS: {self.fps:.1f}")
    
    def toggle_pause(self):
        """Toggle pause state"""
        self.paused = not self.paused
        self.pause_button.config(text="Resume" if self.paused else "Pause")
    
    def on_canvas_click(self, event):
        """Handle canvas click to add clients"""
        if not self.paused:
            world_pos = self.screen_to_world((event.x, event.y))
            import random
            client_id = f"manual_client_{int(time.time())}"
            is_disabled = random.random() < 0.2  # 20% chance
            n_passengers = random.randint(1, 3)
            self.add_client(client_id, world_pos, n_passengers, is_disabled)
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.root.quit()
        self.root.destroy()
    
    def update(self):
        """Update simulation state"""
        if not self.paused:
            current_time = time.time()
            delta_time = current_time - getattr(self, 'last_update_time', current_time)
            self.last_update_time = current_time
            
            # Update taxi positions and free roaming
            for taxi in self.taxis.values():
                taxi.update_position()
                # Only update free roaming if taxi is not assigned to pickup or carrying passengers
                if taxi.is_available and not taxi.pickup_target and taxi.current_passengers == 0:
                    taxi.update_free_roaming()  # Update free roaming behavior
            
            # Update client waiting times and search ranges
            for client in self.clients.values():
                client.update_waiting_time(delta_time)
            
            # Calculate FPS
            self.frame_count += 1
            
            if current_time - self.last_frame_time >= 1.0:
                self.fps = self.frame_count / (current_time - self.last_frame_time)
                self.frame_count = 0
                self.last_frame_time = current_time
                self.update_stats()
    
    def render(self):
        """Render the visualization"""
        if not self.paused:
            self.draw_taxis()
            self.draw_clients()
    
    def run(self):
        """Main GUI loop"""
        self.running = True
        logger.info("Starting taxi dispatch GUI in Tkinter...")
        
        # Start client population manager
        self.start_client_population_manager(min_clients=6, check_interval=2)
        
        def animation_loop():
            """Animation loop for smooth updates"""
            if self.running:
                self.update()
                self.render()
                # Schedule next frame (targeting ~60 FPS)
                self.root.after(16, animation_loop)
        
        # Start animation loop
        animation_loop()
        
        # Start tkinter main loop
        self.root.mainloop()
        
        logger.info("Taxi dispatch GUI stopped")
    
    def stop(self):
        """Stop the GUI"""
        self.running = False
        if self.root:
            self.root.quit()


# Global GUI instance for agent access
_gui_instance: Optional[TaxiTkinterGUI] = None

def get_gui() -> Optional[TaxiTkinterGUI]:
    """Get the global GUI instance"""
    return _gui_instance

def set_gui(gui: TaxiTkinterGUI):
    """Set the global GUI instance"""
    global _gui_instance
    _gui_instance = gui

def start_gui():
    """Start GUI in the main thread (tkinter requirement)"""
    gui = TaxiTkinterGUI()
    set_gui(gui)
    return gui

def start_gui_thread():
    """Legacy function - now just calls start_gui() since tkinter needs main thread"""
    return start_gui()
