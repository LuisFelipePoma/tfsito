"""
Agent registry for managing agent discovery and communication
"""

import logging
import threading
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

@dataclass
class AgentInfo:
    agent_id: str
    jid: str
    host_id: str
    ideology: str
    position: Tuple[float, float]
    last_seen: float
    active: bool = True

class AgentRegistry:
    """Global registry for agent discovery and communication"""
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 60.0  # seconds
        self._agent_timeout = 120.0  # seconds
        
    def register_agent(self, agent_id: str, jid: str, host_id: str, 
                      ideology: str, position: Tuple[float, float]) -> bool:
        """Register an agent in the registry"""
        with self._lock:
            agent_info = AgentInfo(
                agent_id=agent_id,
                jid=jid,
                host_id=host_id,
                ideology=ideology,
                position=position,
                last_seen=time.time(),
                active=True
            )
            
            self._agents[agent_id] = agent_info
            logger.debug(f"Registered agent {agent_id} with JID {jid}")
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from the registry"""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                logger.debug(f"Unregistered agent {agent_id}")
                return True
            return False
    
    def update_agent_heartbeat(self, agent_id: str, ideology: Optional[str] = None, 
                              position: Optional[Tuple[float, float]] = None) -> bool:
        """Update agent heartbeat and optionally ideology/position"""
        with self._lock:
            if agent_id in self._agents:
                agent_info = self._agents[agent_id]
                agent_info.last_seen = time.time()
                agent_info.active = True
                
                if ideology:
                    agent_info.ideology = ideology
                if position:
                    agent_info.position = position
                    
                return True
            return False
    
    def update_agent_position(self, agent_id: str, position: Tuple[float, float]) -> bool:
        """Update an agent's position in the registry"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].position = position
                self._agents[agent_id].last_seen = time.time()
                logger.debug(f"Updated position for agent {agent_id} to {position}")
                return True
            return False
    
    def update_agent_ideology(self, agent_id: str, ideology: str) -> bool:
        """Update an agent's ideology in the registry"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].ideology = ideology
                self._agents[agent_id].last_seen = time.time()
                logger.debug(f"Updated ideology for agent {agent_id} to {ideology}")
                return True
            return False

    def get_active_agents(self) -> List[AgentInfo]:
        """Get list of all active agents"""
        with self._lock:
            current_time = time.time()
            active_agents = []
            
            for agent_info in self._agents.values():
                if (current_time - agent_info.last_seen) < self._agent_timeout:
                    active_agents.append(agent_info)
                else:
                    agent_info.active = False
            
            return active_agents
    
    def get_agent_jids(self, exclude_agent_id: Optional[str] = None) -> List[str]:
        """Get JIDs of all active agents, optionally excluding one"""
        active_agents = self.get_active_agents()
        jids = []
        
        for agent_info in active_agents:
            if exclude_agent_id is None or agent_info.agent_id != exclude_agent_id:
                jids.append(agent_info.jid)
        
        return jids
    
    def get_nearby_agents(self, position: Tuple[float, float], radius: float, 
                         exclude_agent_id: Optional[str] = None) -> List[AgentInfo]:
        """Get agents within a certain radius of a position"""
        import math
        
        active_agents = self.get_active_agents()
        nearby_agents = []
        
        for agent_info in active_agents:
            if exclude_agent_id and agent_info.agent_id == exclude_agent_id:
                continue
                
            # Calculate distance
            dx = position[0] - agent_info.position[0]
            dy = position[1] - agent_info.position[1]
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance <= radius:
                nearby_agents.append(agent_info)
        
        return nearby_agents
    
    def cleanup_inactive_agents(self):
        """Remove agents that haven't been seen recently"""
        with self._lock:
            current_time = time.time()
            inactive_agents = []
            
            for agent_id, agent_info in self._agents.items():
                if (current_time - agent_info.last_seen) > self._agent_timeout:
                    inactive_agents.append(agent_id)
            
            for agent_id in inactive_agents:
                del self._agents[agent_id]
                logger.info(f"Removed inactive agent {agent_id}")
    
    def get_registry_stats(self) -> Dict:
        """Get registry statistics"""
        with self._lock:
            active_agents = self.get_active_agents()
            
            ideology_counts = {}
            host_counts = {}
            
            for agent_info in active_agents:
                ideology_counts[agent_info.ideology] = ideology_counts.get(agent_info.ideology, 0) + 1
                host_counts[agent_info.host_id] = host_counts.get(agent_info.host_id, 0) + 1
            
            return {
                "total_agents": len(active_agents),
                "total_registered": len(self._agents),
                "ideology_distribution": ideology_counts,
                "host_distribution": host_counts
            }
        
    def get_all_agents(self) -> List[AgentInfo]:
        """Get list of all registered agents (active and inactive)"""
        with self._lock:
            return list(self._agents.values())

# Global agent registry instance
agent_registry = AgentRegistry()
