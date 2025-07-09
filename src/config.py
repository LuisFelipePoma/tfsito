import os
from dataclasses import dataclass

@dataclass 
class TaxiSystemConfig:
    """Configuración del Sistema de Taxis con Constraint Programming"""
    
    #APP
    host_name: str = "host"
    
    # OpenFire/XMPP Configuration
    openfire_host: str = "localhost"
    openfire_port: int = 9090
    openfire_admin_user: str = "admin"
    openfire_admin_password: str = "123"
    openfire_domain: str = "192.168.18.19"
    openfire_xmpp_port: int = 5222
    
    # Grid Configuration
    grid_width: int = 20
    grid_height: int = 20
    
    # System Parameters
    num_taxis: int = 3
    initial_passengers: int = 4
    taxi_capacity: int = 4
    
    # Timing
    assignment_interval: float = 2.0  # seconds
    taxi_speed: float = 1.0  # cells per update
    passenger_spawn_rate: float = 0.1  # probability per update
    status_report_interval: float = 1.0  # seconds
    movement_update_interval: float = 0.5  # seconds
    
    # Constraints
    max_pickup_distance: int = 15
    wait_penalty_factor: float = 2.0
    
    # GUI Configuration
    gui_width: int = 1000
    gui_height: int = 700
    grid_cell_size: int = 25
    fps: int = 20

def load_config_from_env():
    """Load configuration from environment variables"""
    config.openfire_host = os.getenv("OPENFIRE_HOST", config.openfire_host)
    config.openfire_port = int(os.getenv("OPENFIRE_PORT", str(config.openfire_port)))
    config.openfire_admin_user = os.getenv("OPENFIRE_ADMIN_USER", config.openfire_admin_user)
    config.openfire_admin_password = os.getenv("OPENFIRE_ADMIN_PASSWORD", config.openfire_admin_password)
    config.openfire_domain = os.getenv("OPENFIRE_DOMAIN", config.openfire_domain)
    
    config.host_name = os.getenv("HOST_NAME", config.openfire_domain)
    config.grid_width = int(os.getenv("GRID_WIDTH", str(config.grid_width)))
    config.grid_height = int(os.getenv("GRID_HEIGHT", str(config.grid_height)))
    config.num_taxis = int(os.getenv("NUM_TAXIS", str(config.num_taxis)))
    
    return config

# Global configuration instance
config = TaxiSystemConfig()
