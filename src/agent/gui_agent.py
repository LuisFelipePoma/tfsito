"""
GUI Agent - Manages web interface communication and state aggregation
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from spade.agent import Agent
from spade.message import Message
from spade.behaviour import PeriodicBehaviour
from spade.template import Template

from config import config
from agent.agent_registry import agent_registry

logger = logging.getLogger(__name__)

class GUIAgent(Agent):
    """SPADE agent responsible for collecting system state and communicating with web interface"""
    
    def __init__(self, jid: str, password: str):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0]
        
        # System state
        self.agents_state: Dict[str, Dict] = {}
        self.communities: Dict[str, Dict] = {}
        self.system_stats = {
            "total_agents": 0,
            "total_communities": 0,
            "ideology_distribution": {},
            "conflicts": 0,
            "ideology_changes": 0,
            "last_updated": time.time()
        }
        
        # Web interface state
        self.web_clients: List[str] = []
        
    async def setup(self):
        """Initialize GUI agent behaviors"""
        logger.info(f"Setting up GUI agent {self.agent_id}")
        
        # State collection behavior - check for updates every 0.5 seconds
        state_behavior = self.StateCollectionBehaviour(period=0.5)
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", "state_update")
        self.add_behaviour(state_behavior, template)
        
        # Message receiving behavior for agent updates
        receive_behavior = self.MessageReceiveBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(receive_behavior, template)
        
        # Web interface communication behavior
        web_behavior = self.WebInterfaceBehaviour(period=1.0)
        self.add_behaviour(web_behavior)
        
        logger.info(f"GUI agent {self.agent_id} setup complete")
    
    def update_agent_state(self, agent_id: str, state: Dict):
        """Update state for a specific agent"""
        self.agents_state[agent_id] = {
            **state,
            "last_updated": time.time()
        }
        self._update_system_stats()
    
    def remove_agent_state(self, agent_id: str):
        """Remove agent from state tracking"""
        if agent_id in self.agents_state:
            del self.agents_state[agent_id]
            self._update_system_stats()
    
    def _update_system_stats(self):
        """Update aggregated system statistics"""
        total_agents = len(self.agents_state)
        
        # Calculate ideology distribution
        ideology_distribution = {}
        communities = {}
        total_ideology_changes = 0
        
        for agent_state in self.agents_state.values():
            ideology = agent_state.get("ideology", "unknown")
            ideology_distribution[ideology] = ideology_distribution.get(ideology, 0) + 1
            
            # Track communities
            community_id = agent_state.get("community_id")
            if community_id:
                if community_id not in communities:
                    communities[community_id] = {
                        "id": community_id,
                        "ideology": ideology,
                        "members": [],
                        "size": 0
                    }
                communities[community_id]["members"].append(agent_state.get("agent_id"))
                communities[community_id]["size"] += 1
            
            # Count ideology changes
            total_ideology_changes += agent_state.get("ideology_changes", 0)
        
        self.communities = communities
        self.system_stats = {
            "total_agents": total_agents,
            "total_communities": len(communities),
            "ideology_distribution": ideology_distribution,
            "conflicts": 0,  # Could be calculated from agent interactions
            "ideology_changes": total_ideology_changes,
            "last_updated": time.time()
        }
    
    def get_system_state(self) -> Dict[str, Any]:
        """Get complete system state for web interface"""
        
        # Force update from registry before returning state
        self._force_update_from_registry()
        
        logger.info(f"GUI: get_system_state called - returning {len(self.agents_state)} agents")
        
        # Log positions for debugging
        for agent_id, state in self.agents_state.items():
            pos = state.get("position", {})
            logger.info(f"GUI: Agent {agent_id} position in state: x={pos.get('x', 'N/A')}, y={pos.get('y', 'N/A')}")
        
        return {
            "agents": list(self.agents_state.values()),
            "communities": list(self.communities.values()),
            "stats": self.system_stats,
            "grid_config": {
                "width": config.grid_width,
                "height": config.grid_height,
                "ideologies": config.ideologies or ['red', 'blue', 'green']
            }
        }
    
    def _force_update_from_registry(self):
        """Force an immediate update from the agent registry"""
        try:
            active_agents = agent_registry.get_all_agents()
            logger.info(f"GUI: Force update - found {len(active_agents)} agents in registry")
            
            current_time = time.time()
            updated_agents = {}
            
            for agent_info in active_agents:
                agent_id = agent_info.agent_id
                
                agent_state = {
                    "agent_id": agent_id,
                    "ideology": agent_info.ideology,
                    "position": {
                        "x": agent_info.position[0],
                        "y": agent_info.position[1]
                    },
                    "community_id": None,
                    "last_updated": current_time,
                    "neighbor_count": 0,
                    "ideology_changes": 0,
                    "messages_sent": 0,
                    "messages_received": 0,
                    "current_timestep": 0
                }
                
                updated_agents[agent_id] = agent_state
                logger.info(f"GUI: Force update - Agent {agent_id} at ({agent_info.position[0]:.1f}, {agent_info.position[1]:.1f})")
            
            self.agents_state = updated_agents
            self._update_system_stats()
            
        except Exception as e:
            logger.error(f"Error in force update from registry: {e}")
            import traceback
            traceback.print_exc()
    
    class StateCollectionBehaviour(PeriodicBehaviour):
        """Periodically collect state updates from agent registry"""
        
        async def run(self):
            try:
                # Get all active agents from the registry
                active_agents = agent_registry.get_all_agents()
                
                logger.debug(f"StateCollection: Found {len(active_agents)} agents in registry")
                
                # Update agent states with current registry data
                current_time = time.time()
                updated_agents = {}
                
                for agent_info in active_agents:
                    agent_id = agent_info.agent_id
                    
                    # Create updated state from registry info
                    agent_state = {
                        "agent_id": agent_id,
                        "ideology": agent_info.ideology,
                        "position": {
                            "x": agent_info.position[0],
                            "y": agent_info.position[1]
                        },
                        "community_id": None,  # This would need to be tracked separately
                        "last_updated": current_time,
                        "neighbor_count": 0,  # This would be calculated from proximity
                        "ideology_changes": 0,  # This would be tracked in the agent
                        "messages_sent": 0,
                        "messages_received": 0,
                        "current_timestep": 0
                    }
                    
                    updated_agents[agent_id] = agent_state
                    
                    logger.info(f"GUI: Agent {agent_id} at position ({agent_info.position[0]:.1f}, {agent_info.position[1]:.1f}) ideology={agent_info.ideology}")
                
                # Replace the agents_state with fresh data from registry
                self.agent.agents_state = updated_agents
                self.agent._update_system_stats()
                
                logger.info(f"GUI: State collection complete - {len(updated_agents)} agents updated")
                
            except Exception as e:
                logger.error(f"Error in state collection behavior: {e}")
                import traceback
                traceback.print_exc()
    
    class MessageReceiveBehaviour(PeriodicBehaviour):
        """Handle incoming messages from other agents"""
        
        def __init__(self, period=0.5):
            super().__init__(period=period)
        
        async def run(self):
            try:
                msg = await self.receive(timeout=0.1)
                if msg:
                    await self.handle_message(msg)
            except Exception as e:
                logger.error(f"Error receiving message in GUI agent: {e}")
        
        async def handle_message(self, msg: Message):
            """Process received message"""
            try:
                if not msg.body:
                    return
                    
                content = json.loads(msg.body)
                message_type = content.get("type")
                
                if message_type == "agent_state_update":
                    agent_id = content.get("agent_id")
                    if agent_id:
                        self.agent.update_agent_state(agent_id, content)
                elif message_type == "agent_shutdown":
                    agent_id = content.get("agent_id")
                    if agent_id:
                        self.agent.remove_agent_state(agent_id)
                
            except Exception as e:
                logger.error(f"Error handling message in GUI agent: {e}")
    
    class WebInterfaceBehaviour(PeriodicBehaviour):
        """Manage communication with web interface"""
        
        async def run(self):
            try:
                # In a real implementation, this would communicate with the web server
                # For now, we'll just prepare the data that would be sent
                system_state = self.agent.get_system_state()
                
                # Log system statistics periodically
                if hasattr(self, 'last_log_time'):
                    if time.time() - self.last_log_time > 10.0:  # Log every 10 seconds
                        self._log_system_stats()
                        self.last_log_time = time.time()
                else:
                    self.last_log_time = time.time()
                
            except Exception as e:
                logger.error(f"Error in web interface behavior: {e}")
        
        def _log_system_stats(self):
            """Log current system statistics"""
            stats = self.agent.system_stats
            logger.info(f"System Stats - Agents: {stats['total_agents']}, "
                       f"Communities: {stats['total_communities']}, "
                       f"Ideology Changes: {stats['ideology_changes']}, "
                       f"Distribution: {stats['ideology_distribution']}")

# Global GUI agent instance
gui_agent_instance: Optional[GUIAgent] = None

async def create_gui_agent() -> Optional[GUIAgent]:
    """Create and start the GUI agent"""
    global gui_agent_instance
    
    try:
        from services.openfire_api import openfire_api
        import uuid
        
        # Create GUI agent user in Openfire
        agent_id = "gui_agent"
        password = f"gui_pass_{uuid.uuid4().hex[:8]}"
        jid = f"{agent_id}@{config.openfire_domain}"
        
        if not openfire_api.create_user(agent_id, password):
            logger.error("Failed to create Openfire user for GUI agent")
            return None
        
        # Create and start the GUI agent
        gui_agent_instance = GUIAgent(jid, password)
        await gui_agent_instance.start(auto_register=True)
        
        # Wait for initialization
        await asyncio.sleep(1.0)
        
        if gui_agent_instance.is_alive():
            logger.info("GUI agent created and started successfully")
            return gui_agent_instance
        else:
            logger.error("GUI agent failed to start")
            return None
            
    except Exception as e:
        logger.error(f"Exception creating GUI agent: {e}")
        return None

async def cleanup_gui_agent():
    """Clean up the GUI agent"""
    global gui_agent_instance
    
    if gui_agent_instance:
        try:
            await gui_agent_instance.stop()
            
            # Remove from Openfire
            from services.openfire_api import openfire_api
            openfire_api.delete_user("gui_agent")
            
            logger.info("GUI agent cleaned up")
            gui_agent_instance = None
            
        except Exception as e:
            logger.error(f"Error cleaning up GUI agent: {e}")

def get_gui_agent() -> Optional[GUIAgent]:
    """Get the global GUI agent instance"""
    return gui_agent_instance
