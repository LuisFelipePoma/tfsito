import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SimulationConfig:
    # Openfire Configuration
    openfire_host: str = "localhost"
    openfire_port: int = 9090
    openfire_admin_user: str = "admin"
    openfire_admin_password: str = "123"  # Match docker-compose
    openfire_domain: str = "localhost"
    openfire_xmpp_port: int = 5222
    
    # Simulation Parameters
    grid_width: int = 100
    grid_height: int = 100
    max_resources_per_node: int = 100
    resource_spawn_rate: float = 0.1
    danger_zone_count: int = 10
    initial_agent_health: int = 100
    max_carry_capacity: int = 20
    trust_threshold: float = 0.6
    
    # Agent Behavior
    movement_cost: int = 1
    resource_collection_rate: int = 5
    health_decay_rate: int = 2
    alliance_duration: int = 100  # simulation steps
    
    # Ideological System Parameters
    ideologies: Optional[List[str]] = None  # Will be set in __post_init__
    influence_radius: float = 5.0  # Grid units
    ideology_change_threshold: float = 0.6  # 60% of neighbors must differ
    ideology_change_cooldown: int = 3  # Time steps before next change
    broadcast_interval: float = 2.0  # Seconds between broadcasts
    community_join_threshold: float = 0.7  # Similarity needed to join community
    max_community_size: int = 50
    min_community_size: int = 3
    
    # Visualization
    gui_width: int = 1200
    gui_height: int = 800
    grid_cell_size: int = 8  # Smaller for larger grid
    fps: int = 30
    
    # Distributed System
    max_agents_per_host: int = 100  # Increased for scalability
    heartbeat_interval: float = 5.0
    message_timeout: float = 10.0
    
    # Web Interface
    web_port: int = 5000
    web_host: str = "0.0.0.0"
    
    def __post_init__(self):
        if self.ideologies is None:
            self.ideologies = ['red', 'blue', 'green', 'yellow', 'purple']

# Global configuration instance
config = SimulationConfig()

def load_config_from_env():
    """Load configuration from environment variables"""
    config.openfire_host = os.getenv("OPENFIRE_HOST", config.openfire_host)
    config.openfire_port = int(os.getenv("OPENFIRE_PORT", str(config.openfire_port)))
    config.openfire_admin_user = os.getenv("OPENFIRE_ADMIN_USER", config.openfire_admin_user)
    config.openfire_admin_password = os.getenv("OPENFIRE_ADMIN_PASSWORD", config.openfire_admin_password)
    config.openfire_domain = os.getenv("OPENFIRE_DOMAIN", config.openfire_domain)
    
    config.grid_width = int(os.getenv("GRID_WIDTH", str(config.grid_width)))
    config.grid_height = int(os.getenv("GRID_HEIGHT", str(config.grid_height)))
    
    return config
