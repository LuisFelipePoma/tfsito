import logging
from typing import Optional
from agent.agent import SurvivorAgent
from config import config
from services.openfire_api import openfire_api
logger = logging.getLogger(__name__)



async def create_agent(agent_id: str, host_id: str) -> Optional[SurvivorAgent]:
    """Create and setup a new survivor agent"""
    
    # Create user in Openfire if not exists
    password = f"agent_{agent_id}_pass"
    jid = f"{agent_id}@{config.openfire_domain}"
    
    if not openfire_api.create_user(agent_id, password, f"Agent {agent_id}"):
        logger.error(f"Failed to create user for agent {agent_id}")
        return None
    
    # Create agent
    agent = SurvivorAgent(jid, password, host_id)
    
    try:
        # Start agent (SPADE agents return a future from start())
        await agent.start()
        logger.info(f"Agent {agent_id} started successfully")
        return agent
    except Exception as e:
        logger.error(f"Failed to start agent {agent_id}: {e}")
        return None

async def cleanup_agent(agent: SurvivorAgent):
    """Cleanup and remove agent"""
    if agent:
        await agent.stop()
        # Remove from Openfire
        openfire_api.delete_user(agent.agent_id)
        logger.info(f"Agent {agent.agent_id} cleaned up")
