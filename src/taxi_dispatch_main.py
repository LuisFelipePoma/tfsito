"""
Main taxi dispatch simulation script
"""

import asyncio
import logging
import time
import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config, load_config_from_env
from agent.agent import TaxiAgent
from agent.client_agent import ClientAgent
from services.openfire_api import OpenFireAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('taxi_dispatch.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class TaxiDispatchSimulation:
    """Main simulation coordinator for taxi dispatch system"""
    
    def __init__(self):
        self.openfire_api = None
        self.taxi_agents = []
        self.client_agents = []
        self.running = False
        
    async def initialize_openfire(self):
        """Initialize and setup Openfire server"""
        try:
            self.openfire_api = OpenFireAPI(
                host=config.openfire_host,
                port=config.openfire_port,
                username=config.openfire_admin_user,
                password=config.openfire_admin_password
            )
            
            # Wait for Openfire to be ready
            await self._wait_for_openfire()
            
            logger.info("Openfire server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Openfire: {e}")
            raise
    
    async def _wait_for_openfire(self, max_attempts=30):
        """Wait for Openfire server to be ready"""
        for attempt in range(max_attempts):
            try:
                if self.openfire_api and await self.openfire_api.is_server_ready():
                    return True
                await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(2)
                
        raise RuntimeError("Openfire server not ready after maximum attempts")
    
    async def create_taxi_agents(self, count=3):
        """Create and start taxi agents"""
        try:
            domain = config.openfire_domain
            
            for i in range(1, count + 1):
                jid = f"taxi{i}@{domain}"
                password = "taxi123"
                
                # Create user in Openfire if needed
                if self.openfire_api:
                    await self.openfire_api.create_user(f"taxi{i}", password, f"Taxi Agent {i}")
                
                # Create and start taxi agent
                max_capacity = 4 if i <= 2 else 6  # Some taxis have different capacities
                taxi = TaxiAgent(jid, password, domain, max_capacity=max_capacity)
                
                await taxi.start()
                self.taxi_agents.append(taxi)
                
                logger.info(f"Created taxi agent: {jid} (capacity: {max_capacity})")
                
        except Exception as e:
            logger.error(f"Failed to create taxi agents: {e}")
            raise
    
    async def create_client_agents(self, count=5):
        """Create and start client agents"""
        try:
            domain = config.openfire_domain
            
            for i in range(1, count + 1):
                jid = f"client{i}@{domain}"
                password = "client123"
                
                # Create user in Openfire if needed
                if self.openfire_api:
                    await self.openfire_api.create_user(f"client{i}", password, f"Client {i}")
                
                # Some clients have disabilities (higher priority)
                is_disabled = (i % 4 == 0)  # Every 4th client is disabled
                
                # Create and start client agent
                client = ClientAgent(jid, password, domain, is_disabled=is_disabled)
                
                await client.start()
                self.client_agents.append(client)
                
                status = "disabled" if is_disabled else "regular"
                logger.info(f"Created client agent: {jid} ({status})")
                
        except Exception as e:
            logger.error(f"Failed to create client agents: {e}")
            raise
    
    async def run_simulation(self, duration=300):
        """Run the taxi dispatch simulation"""
        logger.info(f"Starting taxi dispatch simulation for {duration} seconds")
        self.running = True
        
        try:
            # Initialize system
            await self.initialize_openfire()
            
            # Create agents
            await self.create_taxi_agents(count=3)
            await self.create_client_agents(count=5)
            
            # Run simulation
            start_time = time.time()
            
            while self.running and (time.time() - start_time) < duration:
                await asyncio.sleep(10)  # Status check every 10 seconds
                
                # Log system status
                active_taxis = len([t for t in self.taxi_agents if t.is_alive()])
                active_clients = len([c for c in self.client_agents if c.is_alive()])
                
                logger.info(f"System status: {active_taxis} taxis, {active_clients} clients active")
                
                # Check if any agents crashed
                if active_taxis == 0 or active_clients == 0:
                    logger.warning("Some agents stopped unexpectedly")
                    break
            
            logger.info("Simulation completed successfully")
            
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            raise
        
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup all agents and resources"""
        logger.info("Cleaning up simulation...")
        
        # Stop all agents
        cleanup_tasks = []
        
        for taxi in self.taxi_agents:
            if taxi.is_alive():
                cleanup_tasks.append(taxi.stop())
        
        for client in self.client_agents:
            if client.is_alive():
                cleanup_tasks.append(client.stop())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.taxi_agents.clear()
        self.client_agents.clear()
        self.running = False
        
        logger.info("Cleanup completed")
    
    def stop(self):
        """Stop the simulation"""
        self.running = False
        logger.info("Simulation stop requested")


async def main():
    """Main entry point"""
    # Load configuration from environment
    load_config_from_env()
    
    # Create and run simulation
    simulation = TaxiDispatchSimulation()
    
    try:
        await simulation.run_simulation(duration=300)  # 5 minutes
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
    finally:
        await simulation.cleanup()


if __name__ == "__main__":
    # Run the simulation
    asyncio.run(main())
