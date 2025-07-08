import os
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class SimulationConfig:
    # Openfire Configuration
    openfire_host: str = "localhost"
    openfire_port: int = 9090
    openfire_admin_user: str = "admin"
    openfire_admin_password: str = "123"
    openfire_domain: str = "localhost"
    openfire_xmpp_port: int = 5222
    openfire_secret_key: str = "jNw5zFIsgCfnk75M"  # Secret key para autenticación
    
    # Distributed Deployment Configuration
    coordinator_host: str = "localhost"  # Host principal donde ejecuta el coordinador
    remote_hosts: Optional[List[str]] = None  # Lista de hosts remotos
    
    # Simulation Parameters
    grid_width: int = 50
    grid_height: int = 50
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
    
    # Visualization
    gui_width: int = 1200
    gui_height: int = 800
    grid_cell_size: int = 12
    fps: int = 30
    
    # Distributed System
    max_agents_per_host: int = 50  # Incrementado para soportar más agentes
    heartbeat_interval: float = 5.0
    message_timeout: float = 10.0
    
    def __post_init__(self):
        """Initialize default remote hosts if not provided"""
        if self.remote_hosts is None:
            self.remote_hosts = [
                "192.168.1.100",  # Host coordinador (central)
                "192.168.1.101",  # Host remoto 1 - Taxis
                "192.168.1.102",  # Host remoto 2 - Pasajeros  
                "192.168.1.103",  # Host remoto 3 - Taxis adicional (opcional)
            ]

# Global configuration instance
config = SimulationConfig()

def load_config_from_env():
    """Load configuration from environment variables"""
    config.openfire_host = os.getenv("OPENFIRE_HOST", config.openfire_host)
    config.openfire_port = int(os.getenv("OPENFIRE_PORT", str(config.openfire_port)))
    config.openfire_admin_user = os.getenv("OPENFIRE_ADMIN_USER", config.openfire_admin_user)
    config.openfire_admin_password = os.getenv("OPENFIRE_ADMIN_PASSWORD", config.openfire_admin_password)
    config.openfire_domain = os.getenv("OPENFIRE_DOMAIN", config.openfire_domain)
    config.openfire_secret_key = os.getenv("OPENFIRE_SECRET_KEY", config.openfire_secret_key)
    config.coordinator_host = os.getenv("COORDINATOR_HOST", config.coordinator_host)
    
    # Parse remote hosts from environment (comma-separated)
    remote_hosts_env = os.getenv("REMOTE_HOSTS", "")
    if remote_hosts_env:
        config.remote_hosts = [host.strip() for host in remote_hosts_env.split(",")]
    
    config.grid_width = int(os.getenv("GRID_WIDTH", str(config.grid_width)))
    config.grid_height = int(os.getenv("GRID_HEIGHT", str(config.grid_height)))
    
    return config

@dataclass
class TaxiSystemConfig:
    """Configuración específica para el sistema de taxis"""
    # Grid Configuration
    taxi_grid_width: int = 20
    taxi_grid_height: int = 20
    
    # System Parameters
    num_taxis: int = 3
    initial_passengers: int = 4
    taxi_capacity: int = 4
    
    # Timing
    assignment_interval: float = 2.0  # seconds
    taxi_speed: float = 1.0  # cells per update
    passenger_spawn_rate: float = 0.1  # probability per update
    
    # Constraints
    max_pickup_distance: int = 15
    wait_penalty_factor: float = 2.0
    
    # GUI Configuration
    taxi_gui_width: int = 1000
    taxi_gui_height: int = 700
    taxi_cell_size: int = 25
    taxi_fps: int = 20
    
    # Distributed System (inherits from main config)
    use_distributed: bool = True
    taxi_agent_prefix: str = "taxi_"

# Global taxi configuration instance
taxi_config = TaxiSystemConfig()
