import pygame
import time
import threading
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import colorsys

from agent.libs.environment import environment, Position
from config import config

# Initialize Pygame
pygame.init()

# Colors
class Colors:
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 165, 0)
    PURPLE = (128, 0, 128)
    BROWN = (139, 69, 19)
    GRAY = (128, 128, 128)
    DARK_GRAY = (64, 64, 64)
    LIGHT_GRAY = (192, 192, 192)
    CYAN = (0, 255, 255)
    MAGENTA = (255, 0, 255)
    
    # Resource colors
    FOOD = (0, 128, 0)      # Dark green
    WATER = (0, 191, 255)   # Deep sky blue
    MATERIALS = (139, 69, 19)  # Brown
    MEDICINE = (255, 20, 147)  # Deep pink
    
    # UI colors
    UI_BACKGROUND = (40, 40, 40)
    UI_BORDER = (80, 80, 80)
    UI_TEXT = (220, 220, 220)
    UI_HIGHLIGHT = (100, 149, 237)

@dataclass
class UIElement:
    rect: pygame.Rect
    color: Tuple[int, int, int]
    text: str = ""
    font_size: int = 12

class SimulationGUI:
    """Real-time GUI for monitoring the multi-agent simulation"""
    
    def __init__(self):
        self.screen = pygame.display.set_mode((config.gui_width, config.gui_height))
        pygame.display.set_caption("Post-Apocalyptic Survival Simulation")
        
        # Fonts
        self.font_small = pygame.font.Font(None, 16)
        self.font_medium = pygame.font.Font(None, 20)
        self.font_large = pygame.font.Font(None, 28)
        
        # Layout
        self.grid_size = min(
            (config.gui_width - 400) // config.grid_width,
            (config.gui_height - 100) // config.grid_height
        )
        self.grid_offset_x = 10
        self.grid_offset_y = 50
        
        # UI panels
        self.info_panel_x = self.grid_offset_x + config.grid_width * self.grid_size + 20
        self.info_panel_width = config.gui_width - self.info_panel_x - 10
        
        # Simulation state
        self.world_state = {}
        self.selected_agent = None
        self.show_alliances = True
        self.show_danger_zones = True
        self.show_resources = True
        self.show_paths = False
        
        # Event timeline
        self.event_timeline: List[Dict[str, Any]] = []
        self.timeline_scroll = 0
        
        # Performance tracking
        self.last_update = time.time()
        self.fps_counter = 0
        self.fps = 0
        
        # Colors for different agents
        self.agent_colors = {}
        self.alliance_colors = {}
        
        # UI state
        self.running = True
        self.clock = pygame.time.Clock()
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_world_state, daemon=True)
        self.update_thread.start()
    
    def _update_world_state(self):
        """Background thread to update world state"""
        while self.running:
            try:
                self.world_state = environment.get_world_state()
                time.sleep(0.1)  # Update 10 times per second
            except Exception as e:
                print(f"Error updating world state: {e}")
                time.sleep(1.0)
    
    def _get_agent_color(self, agent_id: str) -> Tuple[int, int, int]:
        """Get consistent color for agent"""
        if agent_id not in self.agent_colors:
            # Generate color based on agent ID hash
            hash_val = hash(agent_id) % 360
            hue = hash_val / 360.0
            rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
            self.agent_colors[agent_id] = tuple(int(c * 255) for c in rgb)
        return self.agent_colors[agent_id]
    
    def _get_alliance_color(self, alliance_id: str) -> Tuple[int, int, int]:
        """Get consistent color for alliance"""
        if alliance_id not in self.alliance_colors:
            hash_val = hash(alliance_id) % 360
            hue = hash_val / 360.0
            rgb = colorsys.hsv_to_rgb(hue, 0.6, 0.7)
            self.alliance_colors[alliance_id] = tuple(int(c * 255) for c in rgb)
        return self.alliance_colors[alliance_id]
    
    def _world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        screen_x = self.grid_offset_x + world_pos.x * self.grid_size
        screen_y = self.grid_offset_y + world_pos.y * self.grid_size
        return screen_x, screen_y
    
    def _screen_to_world(self, screen_x: int, screen_y: int) -> Position:
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x - self.grid_offset_x) // self.grid_size
        world_y = (screen_y - self.grid_offset_y) // self.grid_size
        return Position(max(0, min(config.grid_width - 1, world_x)),
                       max(0, min(config.grid_height - 1, world_y)))
    
    def _draw_grid(self):
        """Draw the simulation grid"""
        # Draw grid background
        grid_rect = pygame.Rect(
            self.grid_offset_x, self.grid_offset_y,
            config.grid_width * self.grid_size,
            config.grid_height * self.grid_size
        )
        pygame.draw.rect(self.screen, Colors.DARK_GRAY, grid_rect)
        
        # Draw grid lines
        for x in range(config.grid_width + 1):
            start_x = self.grid_offset_x + x * self.grid_size
            pygame.draw.line(
                self.screen, Colors.GRAY,
                (start_x, self.grid_offset_y),
                (start_x, self.grid_offset_y + config.grid_height * self.grid_size)
            )
        
        for y in range(config.grid_height + 1):
            start_y = self.grid_offset_y + y * self.grid_size
            pygame.draw.line(
                self.screen, Colors.GRAY,
                (self.grid_offset_x, start_y),
                (self.grid_offset_x + config.grid_width * self.grid_size, start_y)
            )
    
    def _draw_danger_zones(self):
        """Draw danger zones"""
        if not self.show_danger_zones:
            return
        
        danger_zones = self.world_state.get("danger_zones", [])
        for zone in danger_zones:
            if zone["active"]:
                center_pos = Position(zone["position"]["x"], zone["position"]["y"])
                center_screen = self._world_to_screen(center_pos)
                
                radius_pixels = zone["radius"] * self.grid_size
                
                # Draw danger zone as red circle with transparency
                danger_surface = pygame.Surface((radius_pixels * 2, radius_pixels * 2), pygame.SRCALPHA)
                pygame.draw.circle(
                    danger_surface, 
                    (*Colors.RED, 80),  # Red with alpha
                    (radius_pixels, radius_pixels),
                    radius_pixels
                )
                
                self.screen.blit(
                    danger_surface,
                    (center_screen[0] - radius_pixels, center_screen[1] - radius_pixels)
                )
                
                # Draw border
                pygame.draw.circle(
                    self.screen, Colors.RED,
                    center_screen, radius_pixels, 2
                )
    
    def _draw_resources(self):
        """Draw resource nodes"""
        if not self.show_resources:
            return
        
        resources = self.world_state.get("resources", {})
        for resource_data in resources.values():
            pos = Position(resource_data["position"]["x"], resource_data["position"]["y"])
            screen_pos = self._world_to_screen(pos)
            
            # Resource type colors
            resource_colors = {
                "food": Colors.FOOD,
                "water": Colors.WATER,
                "materials": Colors.MATERIALS,
                "medicine": Colors.MEDICINE
            }
            
            color = resource_colors.get(resource_data["type"], Colors.YELLOW)
            
            # Draw resource as circle, size based on amount
            amount_ratio = resource_data["amount"] / max(resource_data["max_amount"], 1)
            radius = max(2, int(self.grid_size * 0.3 * amount_ratio))
            
            pygame.draw.circle(
                self.screen, color,
                (screen_pos[0] + self.grid_size // 2, screen_pos[1] + self.grid_size // 2),
                radius
            )
            
            # Draw amount text if grid is large enough
            if self.grid_size >= 20:
                amount_text = self.font_small.render(
                    str(resource_data["amount"]), True, Colors.WHITE
                )
                text_rect = amount_text.get_rect()
                text_rect.center = (
                    screen_pos[0] + self.grid_size // 2,
                    screen_pos[1] + self.grid_size // 2
                )
                self.screen.blit(amount_text, text_rect)
    
    def _draw_agents(self):
        """Draw all agents"""
        agents = self.world_state.get("agents", {})
        alliances = self.world_state.get("alliances", {})
        
        # Draw alliance connections first
        if self.show_alliances:
            for alliance_id, alliance_data in alliances.items():
                members = alliance_data["members"]
                if len(members) > 1:
                    alliance_color = self._get_alliance_color(alliance_id)
                    
                    # Draw connections between alliance members
                    member_positions = []
                    for member_id in members:
                        if member_id in agents:
                            pos = Position(
                                agents[member_id]["position"]["x"],
                                agents[member_id]["position"]["y"]
                            )
                            screen_pos = self._world_to_screen(pos)
                            member_positions.append((
                                screen_pos[0] + self.grid_size // 2,
                                screen_pos[1] + self.grid_size // 2
                            ))
                    
                    # Draw lines between all members
                    for i, pos1 in enumerate(member_positions):
                        for pos2 in member_positions[i+1:]:
                            pygame.draw.line(self.screen, alliance_color, pos1, pos2, 2)
        
        # Draw agents
        for agent_id, agent_data in agents.items():
            pos = Position(agent_data["position"]["x"], agent_data["position"]["y"])
            screen_pos = self._world_to_screen(pos)
            
            # Agent color based on state
            state = agent_data["state"].get("state", "exploring")
            if state == "dying" or agent_data["state"].get("health", 100) < 20:
                color = Colors.RED
            elif state == "in_alliance":
                # Use alliance color if in alliance
                alliance_id = agent_data["state"].get("alliance_id")
                if alliance_id and alliance_id in alliances:
                    color = self._get_alliance_color(alliance_id)
                else:
                    color = self._get_agent_color(agent_id)
            elif state == "in_conflict":
                color = Colors.ORANGE
            else:
                color = self._get_agent_color(agent_id)
            
            # Draw agent as circle
            center = (
                screen_pos[0] + self.grid_size // 2,
                screen_pos[1] + self.grid_size // 2
            )
            
            # Agent size based on health
            health = agent_data["state"].get("health", 100)
            base_radius = max(3, self.grid_size // 4)
            radius = max(2, int(base_radius * (health / 100)))
            
            pygame.draw.circle(self.screen, color, center, radius)
            
            # Draw health bar if selected or grid is large
            if agent_id == self.selected_agent or self.grid_size >= 25:
                self._draw_health_bar(center, health, radius + 2)
            
            # Draw agent ID if grid is large enough
            if self.grid_size >= 30:
                id_text = self.font_small.render(agent_id[:3], True, Colors.WHITE)
                text_rect = id_text.get_rect()
                text_rect.center = (center[0], center[1] + radius + 8)
                self.screen.blit(id_text, text_rect)
            
            # Highlight selected agent
            if agent_id == self.selected_agent:
                pygame.draw.circle(self.screen, Colors.WHITE, center, radius + 3, 2)
    
    def _draw_health_bar(self, center: Tuple[int, int], health: int, offset: int):
        """Draw health bar above agent"""
        bar_width = 20
        bar_height = 4
        
        # Background
        bar_rect = pygame.Rect(
            center[0] - bar_width // 2,
            center[1] - offset - bar_height,
            bar_width, bar_height
        )
        pygame.draw.rect(self.screen, Colors.DARK_GRAY, bar_rect)
        
        # Health
        health_width = int(bar_width * (health / 100))
        if health_width > 0:
            health_rect = pygame.Rect(
                center[0] - bar_width // 2,
                center[1] - offset - bar_height,
                health_width, bar_height
            )
            
            # Color based on health level
            if health > 70:
                health_color = Colors.GREEN
            elif health > 30:
                health_color = Colors.YELLOW
            else:
                health_color = Colors.RED
            
            pygame.draw.rect(self.screen, health_color, health_rect)
    
    def _draw_info_panel(self):
        """Draw information panel"""
        panel_rect = pygame.Rect(
            self.info_panel_x, 10,
            self.info_panel_width, config.gui_height - 20
        )
        pygame.draw.rect(self.screen, Colors.UI_BACKGROUND, panel_rect)
        pygame.draw.rect(self.screen, Colors.UI_BORDER, panel_rect, 2)
        
        y_offset = 20
        
        # Simulation info
        sim_time = self.world_state.get("simulation_time", 0)
        time_text = self.font_medium.render(f"Simulation Time: {sim_time:.1f}s", True, Colors.UI_TEXT)
        self.screen.blit(time_text, (self.info_panel_x + 10, y_offset))
        y_offset += 25
        
        # Agent count
        agents = self.world_state.get("agents", {})
        agent_count_text = self.font_medium.render(f"Agents: {len(agents)}", True, Colors.UI_TEXT)
        self.screen.blit(agent_count_text, (self.info_panel_x + 10, y_offset))
        y_offset += 25
        
        # Alliance count
        alliances = self.world_state.get("alliances", {})
        alliance_count_text = self.font_medium.render(f"Alliances: {len(alliances)}", True, Colors.UI_TEXT)
        self.screen.blit(alliance_count_text, (self.info_panel_x + 10, y_offset))
        y_offset += 35
        
        # Controls
        controls_title = self.font_medium.render("Controls:", True, Colors.UI_HIGHLIGHT)
        self.screen.blit(controls_title, (self.info_panel_x + 10, y_offset))
        y_offset += 25
        
        controls = [
            "Click agent to select",
            "D - Toggle danger zones",
            "R - Toggle resources", 
            "A - Toggle alliances",
            "P - Toggle paths",
            "ESC - Exit"
        ]
        
        for control in controls:
            control_text = self.font_small.render(control, True, Colors.UI_TEXT)
            self.screen.blit(control_text, (self.info_panel_x + 10, y_offset))
            y_offset += 18
        
        y_offset += 20
        
        # Selected agent info
        if self.selected_agent and self.selected_agent in agents:
            self._draw_agent_info(y_offset)
            y_offset += 200
        
        # Event timeline
        self._draw_event_timeline(y_offset)
    
    def _draw_agent_info(self, start_y: int):
        """Draw detailed info about selected agent"""
        agents = self.world_state.get("agents", {})
        agent_data = agents[self.selected_agent]
        
        title = self.font_medium.render(f"Agent: {self.selected_agent}", True, Colors.UI_HIGHLIGHT)
        self.screen.blit(title, (self.info_panel_x + 10, start_y))
        start_y += 25
        
        # Basic stats
        state = agent_data["state"]
        health = state.get("health", 100)
        agent_state = state.get("state", "unknown")
        
        stats = [
            f"Health: {health}",
            f"State: {agent_state}",
            f"Position: ({agent_data['position']['x']}, {agent_data['position']['y']})"
        ]
        
        for stat in stats:
            stat_text = self.font_small.render(stat, True, Colors.UI_TEXT)
            self.screen.blit(stat_text, (self.info_panel_x + 10, start_y))
            start_y += 18
        
        # Resources
        resources = state.get("resources", {})
        if resources:
            resources_title = self.font_small.render("Resources:", True, Colors.UI_TEXT)
            self.screen.blit(resources_title, (self.info_panel_x + 10, start_y))
            start_y += 18
            
            for resource_type, amount in resources.items():
                if amount > 0:
                    resource_text = self.font_small.render(f"  {resource_type}: {amount}", True, Colors.UI_TEXT)
                    self.screen.blit(resource_text, (self.info_panel_x + 10, start_y))
                    start_y += 15
        
        # Alliance info
        alliance_id = state.get("alliance_id")
        if alliance_id:
            alliances = self.world_state.get("alliances", {})
            if alliance_id in alliances:
                alliance = alliances[alliance_id]
                alliance_text = self.font_small.render(f"Alliance: {alliance_id}", True, Colors.UI_TEXT)
                self.screen.blit(alliance_text, (self.info_panel_x + 10, start_y))
                start_y += 18
                
                members_text = self.font_small.render(f"Members: {len(alliance['members'])}", True, Colors.UI_TEXT)
                self.screen.blit(members_text, (self.info_panel_x + 10, start_y))
                start_y += 18
    
    def _draw_event_timeline(self, start_y: int):
        """Draw recent events timeline"""
        events = self.world_state.get("events", [])
        
        title = self.font_medium.render("Recent Events:", True, Colors.UI_HIGHLIGHT)
        self.screen.blit(title, (self.info_panel_x + 10, start_y))
        start_y += 25
        
        # Show last 8 events
        visible_events = events[-8:]
        
        for event in reversed(visible_events):  # Most recent first
            event_type = event["type"]
            participants = event.get("participants", [])
            timestamp = event["timestamp"]
            
            # Format event text
            if event_type == "agent_spawned":
                text = f"Agent {participants[0]} spawned"
            elif event_type == "alliance_formed":
                text = f"Alliance formed: {len(participants)} members"
            elif event_type == "resource_harvested":
                details = event.get("details", {})
                text = f"Resource harvested: {details.get('resource_type', 'unknown')}"
            elif event_type == "agent_died":
                text = f"Agent {participants[0]} died"
            else:
                text = f"{event_type}: {', '.join(participants[:2])}"
            
            # Truncate long text
            if len(text) > 35:
                text = text[:32] + "..."
            
            # Color based on event type
            if event_type in ["agent_died", "alliance_dissolved"]:
                color = Colors.RED
            elif event_type in ["alliance_formed", "resource_spawned"]:
                color = Colors.GREEN
            else:
                color = Colors.UI_TEXT
            
            event_text = self.font_small.render(text, True, color)
            self.screen.blit(event_text, (self.info_panel_x + 10, start_y))
            start_y += 15
            
            # Stop if we run out of space
            if start_y > config.gui_height - 50:
                break
    
    def _draw_hud(self):
        """Draw heads-up display"""
        # FPS counter
        fps_text = self.font_small.render(f"FPS: {self.fps}", True, Colors.WHITE)
        self.screen.blit(fps_text, (10, 10))
        
        # Legend
        legend_x = 10
        legend_y = config.gui_height - 80
        
        legend_title = self.font_small.render("Legend:", True, Colors.WHITE)
        self.screen.blit(legend_title, (legend_x, legend_y))
        legend_y += 18
        
        legend_items = [
            ("Agents", Colors.CYAN),
            ("Resources", Colors.YELLOW),
            ("Danger", Colors.RED)
        ]
        
        for item_text, item_color in legend_items:
            pygame.draw.circle(self.screen, item_color, (legend_x + 8, legend_y + 6), 4)
            text = self.font_small.render(item_text, True, Colors.WHITE)
            self.screen.blit(text, (legend_x + 20, legend_y))
            legend_y += 15
    
    def _handle_click(self, pos: Tuple[int, int]):
        """Handle mouse click"""
        # Check if click is on grid
        if (self.grid_offset_x <= pos[0] <= self.grid_offset_x + config.grid_width * self.grid_size and
            self.grid_offset_y <= pos[1] <= self.grid_offset_y + config.grid_height * self.grid_size):
            
            world_pos = self._screen_to_world(pos[0], pos[1])
            
            # Find agent at this position
            agents = self.world_state.get("agents", {})
            for agent_id, agent_data in agents.items():
                agent_pos = Position(agent_data["position"]["x"], agent_data["position"]["y"])
                if agent_pos.x == world_pos.x and agent_pos.y == world_pos.y:
                    self.selected_agent = agent_id
                    return
            
            # No agent found, deselect
            self.selected_agent = None
    
    def _handle_key(self, key):
        """Handle keyboard input"""
        if key == pygame.K_d:
            self.show_danger_zones = not self.show_danger_zones
        elif key == pygame.K_r:
            self.show_resources = not self.show_resources
        elif key == pygame.K_a:
            self.show_alliances = not self.show_alliances
        elif key == pygame.K_p:
            self.show_paths = not self.show_paths
        elif key == pygame.K_ESCAPE:
            self.running = False
    
    def run(self):
        """Main GUI loop"""
        print("Starting simulation GUI...")
        print("Controls:")
        print("  Click on agents to select them")
        print("  D - Toggle danger zones")
        print("  R - Toggle resources")
        print("  A - Toggle alliances")
        print("  P - Toggle paths")
        print("  ESC - Exit")
        
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self._handle_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
            
            # Clear screen
            self.screen.fill(Colors.BLACK)
            
            # Draw everything
            self._draw_grid()
            self._draw_danger_zones()
            self._draw_resources()
            self._draw_agents()
            self._draw_info_panel()
            self._draw_hud()
            
            # Update display
            pygame.display.flip()
            
            # Calculate FPS
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.last_update >= 1.0:
                self.fps = self.fps_counter
                self.fps_counter = 0
                self.last_update = current_time
            
            # Control frame rate
            self.clock.tick(config.fps)
        
        pygame.quit()

def main():
    """Run the GUI"""
    gui = SimulationGUI()
    gui.run()

if __name__ == "__main__":
    main()
