import asyncio
import logging
import argparse
import signal
import sys
import time
from typing import List
import uuid
import spade

from agent.agent import SurvivorAgent
from agent.index import create_agent, cleanup_agent
from services.openfire_api import openfire_api
from config import config, load_config_from_env

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("simulation.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class SimulationManager:
    """Manages the distributed multi-agent simulation"""

    def __init__(self, host_id: str, agent_count: int):
        self.host_id = host_id
        self.agent_count = agent_count
        self.agents: List[SurvivorAgent] = []
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
        logger.info(f"Initializing simulation manager for host {self.host_id}")

        # Load configuration
        load_config_from_env()

        # Check Openfire connection
        if not openfire_api.health_check():
            logger.error("Cannot connect to Openfire server")
            return False

        logger.info("Openfire connection verified")

        return True

    async def spawn_agents(self) -> bool:
        """Spawn agents for this host"""
        logger.info(f"Spawning {self.agent_count} agents for host {self.host_id}")

        for i in range(self.agent_count):
            agent_id = f"{self.host_id}_agent_{i}_{uuid.uuid4().hex[:8]}"

            try:
                agent = await create_agent(agent_id, self.host_id)
                if agent:
                    self.agents.append(agent)
                    logger.info(f"Successfully spawned agent {agent_id}")
                else:
                    logger.error(f"Failed to spawn agent {agent_id}")

                # Small delay between spawns
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error spawning agent {agent_id}: {e}")

        logger.info(f"Spawned {len(self.agents)} agents successfully")
        return len(self.agents) > 0

    async def run_simulation(self):
        """Run the main simulation loop"""
        logger.info("Starting simulation loop")
        self.running = True

        start_time = time.time()

        while self.running:
            try:
                # Check agent health
                dead_agents = []
                for agent in self.agents:
                    if not agent.is_alive():
                        dead_agents.append(agent)

                # Clean up dead agents
                for agent in dead_agents:
                    logger.info(f"Cleaning up dead agent {agent.agent_id}")
                    await cleanup_agent(agent)
                    self.agents.remove(agent)

                # Check if we should spawn replacement agents
                if len(self.agents) < self.agent_count // 2:
                    logger.warning("Low agent count, considering respawn...")
                    # Could implement respawn logic here

                await asyncio.sleep(5.0)  # Main loop interval

            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(1.0)

        logger.info("Simulation loop ended")

    async def shutdown(self):
        """Gracefully shutdown the simulation"""
        logger.info("Shutting down simulation manager")

        # Stop agents
        cleanup_tasks = []
        for agent in self.agents:
            cleanup_tasks.append(cleanup_agent(agent))

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)



async def run_agent_mode(host_id: str, agent_count: int):
    """Run in agent mode"""
    logger.info(f"Starting agent mode: host={host_id}, agents={agent_count}")

    manager = SimulationManager(host_id, agent_count)

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
        description="Multiagent"
    )
    parser.add_argument("--host", type=str, help="Hostname")
    parser.add_argument(
        "--agent-count",
        type=int,
        default=5,
        help="Number of agents to spawn on this host",
    )
    parser.add_argument("--openfire-host", type=str, help="Openfire server hostname")
    parser.add_argument("--openfire-port", type=int, help="Openfire server port")

    args = parser.parse_args()

    # Override config with command line args
    if args.openfire_host:
        config.openfire_host = args.openfire_host
    if args.openfire_port:
        config.openfire_port = args.openfire_port

    print(f"Openfire server: {config.openfire_host}:{config.openfire_port}")

    try:
        result = spade.run(run_agent_mode(args.host, args.agent_count))
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
