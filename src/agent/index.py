import asyncio
from src.services.openfire_api import openfire_api
from src.utils.logger import logger


async def cleanup_agent(agent) -> None:
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
        logger.error(
            f"Error cleaning up agent {getattr(agent, 'agent_id', 'unknown')}: {e}"
        )

async def cleanup_agent_batch(agents) -> None:
    """Clean up a batch of agents"""

    cleanup_tasks = []
    for agent in agents:
        cleanup_tasks.append(cleanup_agent(agent))

    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    logger.info(f"Cleaned up {len(agents)} agents")
