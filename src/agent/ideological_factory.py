"""
Agent factory and management for ideological agents
"""

import asyncio
import logging
import random
import uuid
from typing import Optional, List
from agent.ideological_agent import IdeologicalAgent, Position
from services.openfire_api import openfire_api
from config import config

logger = logging.getLogger(__name__)

async def create_ideological_agent(agent_id: str, host_id: str, ideology: Optional[str] = None, position: Optional[Position] = None) -> Optional[IdeologicalAgent]:
    """Create and initialize an ideological agent"""
    
    try:
        # Generate random ideology if not specified
        if ideology is None:
            ideology = random.choice(config.ideologies or ['red', 'blue', 'green'])
        
        # Generate random position if not specified
        if position is None:
            position = Position(
                random.uniform(0, config.grid_width),
                random.uniform(0, config.grid_height)
            )
        
        # Create user in Openfire
        password = f"agent_pass_{uuid.uuid4().hex[:8]}"
        jid = f"{agent_id}@{config.openfire_domain}"
        
        if not openfire_api.create_user(agent_id, password):
            logger.error(f"Failed to create Openfire user for agent {agent_id}")
            return None
        
        # Create and start the agent
        agent = IdeologicalAgent(jid, password, host_id, ideology, position)
        
        # Start the agent
        await agent.start(auto_register=True)
        
        # Wait a moment for the agent to fully initialize
        await asyncio.sleep(0.5)
        
        if agent.is_alive():
            logger.info(f"Successfully created ideological agent {agent_id} with ideology '{ideology}' at position ({position.x:.1f}, {position.y:.1f})")
            return agent
        else:
            logger.error(f"Agent {agent_id} failed to start properly")
            await cleanup_ideological_agent(agent)
            return None
            
    except Exception as e:
        logger.error(f"Exception creating agent {agent_id}: {e}")
        return None

async def cleanup_ideological_agent(agent: IdeologicalAgent) -> None:
    """Clean up an ideological agent"""
    
    try:
        agent_id = agent.agent_id
        
        # Stop the agent
        if agent.is_alive():
            await agent.cleanup()
            await agent.stop()
        
        # Remove from Openfire
        openfire_api.delete_user(agent_id)
        
        logger.info(f"Cleaned up agent {agent_id}")
        
    except Exception as e:
        logger.error(f"Error cleaning up agent {getattr(agent, 'agent_id', 'unknown')}: {e}")

async def create_agent_batch(host_id: str, count: int, ideology_distribution: Optional[dict] = None) -> List[IdeologicalAgent]:
    """Create a batch of agents with specified ideology distribution"""
    
    agents = []
    
    # Calculate ideology distribution
    if ideology_distribution is None:
        # Even distribution
        ideologies = config.ideologies or ['red', 'blue', 'green']
        ideology_distribution = {ideology: count // len(ideologies) for ideology in ideologies}
        # Handle remainder
        remaining = count % len(ideologies)
        for i, ideology in enumerate(ideologies):
            if i < remaining:
                ideology_distribution[ideology] += 1
    
    # Create agents
    agent_count = 0
    for ideology, agent_num in ideology_distribution.items():
        for i in range(agent_num):
            agent_id = f"{host_id}_agent_{ideology}_{i}_{uuid.uuid4().hex[:8]}"
            
            agent = await create_ideological_agent(agent_id, host_id, ideology)
            if agent:
                agents.append(agent)
                agent_count += 1
            
            # Small delay between creations
            await asyncio.sleep(0.2)
    
    logger.info(f"Created {agent_count} ideological agents for host {host_id}")
    return agents

async def cleanup_agent_batch(agents: List[IdeologicalAgent]) -> None:
    """Clean up a batch of agents"""
    
    cleanup_tasks = []
    for agent in agents:
        cleanup_tasks.append(cleanup_ideological_agent(agent))
    
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    
    logger.info(f"Cleaned up {len(agents)} agents")
