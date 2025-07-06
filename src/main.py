import asyncio
import logging
import argparse
import signal
import sys
import time
import threading
from typing import List
import uuid
import spade

from agent.ideological_agent import IdeologicalAgent
from agent.ideological_factory import create_agent_batch, cleanup_agent_batch
from agent.gui_agent import create_gui_agent, cleanup_gui_agent, get_gui_agent
from env_agent.web_interface import create_web_interface
from services.openfire_api import openfire_api
from config import config, load_config_from_env

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("simulation.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class IdeologicalSimulationManager:
    """Manages the distributed multi-agent ideological simulation"""

    def __init__(self, host_id: str, agent_count: int, enable_web: bool = False):
        self.host_id = host_id
        self.agent_count = agent_count
        self.enable_web = enable_web
        self.agents: List[IdeologicalAgent] = []
        self.gui_agent = None
        self.web_interface = None
        self.running = False

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def initialize(self) -> bool:
        """Initialize the simulation system"""
        logger.info(f"Initializing ideological simulation manager for host {self.host_id}")

        # Load configuration
        load_config_from_env()

        # Check Openfire connection
        if not openfire_api.health_check():
            logger.error("Cannot connect to Openfire server")
            return False

        logger.info("Openfire connection verified")

        # Create GUI agent
        self.gui_agent = await create_gui_agent()
        if not self.gui_agent:
            logger.error("Failed to create GUI agent")
            return False

        # Setup web interface if enabled
        if self.enable_web:
            self.web_interface = create_web_interface()
            
            # Start web server in background thread
            def run_web():
                try:
                    self.web_interface.run(debug=False)
                except Exception as e:
                    logger.error(f"Web interface error: {e}")
            
            web_thread = threading.Thread(target=run_web, daemon=True)
            web_thread.start()
            logger.info(f"Web interface started on http://{config.web_host}:{config.web_port}")

        return True

    async def spawn_agents(self) -> bool:
        """Spawn ideological agents for this host"""
        logger.info(f"Spawning {self.agent_count} ideological agents for host {self.host_id}")

        # Create agents with distributed ideologies
        ideology_distribution = {
            'red': self.agent_count // 3,
            'blue': self.agent_count // 3,
            'green': self.agent_count - (2 * (self.agent_count // 3))
        }

        self.agents = await create_agent_batch(
            host_id=self.host_id,
            count=self.agent_count,
            ideology_distribution=ideology_distribution
        )

        logger.info(f"Spawned {len(self.agents)} ideological agents successfully")
        return len(self.agents) > 0

    async def run_simulation(self):
        """Run the main simulation loop"""
        logger.info("Starting ideological simulation loop")
        self.running = True

        start_time = time.time()
        loop_count = 0

        while self.running:
            try:
                loop_count += 1
                
                # Check agent health
                dead_agents = []
                for agent in self.agents:
                    if not agent.is_alive():
                        dead_agents.append(agent)

                # Clean up dead agents
                for agent in dead_agents:
                    logger.info(f"Cleaning up dead agent {agent.agent_id}")
                    self.agents.remove(agent)

                # Update GUI agent with system state
                if self.gui_agent and loop_count % 5 == 0:  # Every 5 loops
                    await self.update_gui_agent_state()

                # Check if we should spawn replacement agents
                if len(self.agents) < self.agent_count // 2:
                    logger.warning("Low agent count, considering respawn...")
                    # Could implement respawn logic here

                # Periodic status log
                if loop_count % 20 == 0:  # Every 20 loops (100 seconds)
                    runtime = time.time() - start_time
                    logger.info(f"Simulation running for {runtime:.1f}s with {len(self.agents)} agents")

                await asyncio.sleep(5.0)  # Main loop interval

            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(1.0)

        logger.info("Simulation loop ended")

    async def update_gui_agent_state(self):
        """Update GUI agent with current system state"""
        try:
            for agent in self.agents:
                if agent.is_alive():
                    agent_stats = await agent.get_agent_stats()
                    self.gui_agent.update_agent_state(agent.agent_id, agent_stats)
        except Exception as e:
            logger.error(f"Error updating GUI agent state: {e}")

    async def shutdown(self):
        """Gracefully shutdown the simulation"""
        logger.info("Shutting down ideological simulation manager")

        # Stop agents
        if self.agents:
            await cleanup_agent_batch(self.agents)

        # Stop GUI agent
        if self.gui_agent:
            await cleanup_gui_agent()

        logger.info("Simulation shutdown complete")



async def run_agent_mode(host_id: str, agent_count: int, enable_web: bool = False):
    """Run in ideological agent mode"""
    logger.info(f"Starting ideological agent mode: host={host_id}, agents={agent_count}, web={enable_web}")

    manager = IdeologicalSimulationManager(host_id, agent_count, enable_web)

    try:
        # Initialize
        if not await manager.initialize():
            logger.error("Failed to initialize simulation")
            return 1

        # Spawn agents
        if not await manager.spawn_agents():
            logger.error("Failed to spawn any agents")
            return 1

        # Run simulation
        await manager.run_simulation()

    except Exception as e:
        logger.error(f"Simulation error: {e}")
        return 1
    finally:
        await manager.shutdown()

    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Ideological Multi-Agent System"
    )
    parser.add_argument("--host", type=str, required=True, help="Hostname identifier")
    parser.add_argument(
        "--agent-count",
        type=int,
        default=10,
        help="Number of agents to spawn on this host",
    )
    parser.add_argument("--openfire-host", type=str, help="Openfire server hostname")
    parser.add_argument("--openfire-port", type=int, help="Openfire server port")
    parser.add_argument("--web", action="store_true", help="Enable web interface")

    args = parser.parse_args()

    # Override config with command line args
    if args.openfire_host:
        config.openfire_host = args.openfire_host
    if args.openfire_port:
        config.openfire_port = args.openfire_port

    print(f"Openfire server: {config.openfire_host}:{config.openfire_port}")
    print(f"Grid size: {config.grid_width}x{config.grid_height}")
    print(f"Ideologies: {config.ideologies}")
    if args.web:
        print(f"Web interface will be available at: http://{config.web_host}:{config.web_port}")

    try:
        result = spade.run(run_agent_mode(args.host, args.agent_count, args.web))
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
