"""
Ideological Agent - A SPADE agent with ideological beliefs and community behavior
"""

import asyncio
import datetime
import json
import logging
import random
import time
import math
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from spade.agent import Agent
from spade.message import Message
from spade.behaviour import PeriodicBehaviour, OneShotBehaviour
from spade.template import Template

from agent.libs.ideology_constraints import IdeologyConstraintSolver
from agent.agent_registry import agent_registry
from config import config

logger = logging.getLogger(__name__)

@dataclass
class Position:
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

@dataclass 
class AgentState:
    agent_id: str
    position: Position
    ideology: str
    last_ideology_change: int
    community_id: Optional[str]
    neighbors: Set[str]
    ideology_history: List[Tuple[int, str]]  # (timestep, ideology)

@dataclass
class CommunityInfo:
    community_id: str
    ideology: str
    members: Set[str]
    center_position: Position
    created_at: int

class IdeologicalAgent(Agent):
    """SPADE agent with ideological beliefs and community participation"""
    
    def __init__(self, jid: str, password: str, host_id: str, ideology: Optional[str] = None, position: Optional[Position] = None):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0] 
        self.host_id = host_id
        
        # Agent state
        self.ideology = ideology or random.choice(config.ideologies or ['red', 'blue', 'green'])
        self.position = position or Position(
            random.uniform(0, config.grid_width),
            random.uniform(0, config.grid_height)
        )
        
        # Tracking variables
        self.neighbors: Dict[str, AgentState] = {}
        self.last_ideology_change = 0
        self.current_timestep = 0
        self.community_id: Optional[str] = None
        self.ideology_history: List[Tuple[int, str]] = [(0, self.ideology)]
        
        # Constraint solver for decision making
        self.constraint_solver = IdeologyConstraintSolver()
        
        # Performance metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.ideology_changes = 0
        
    async def setup(self):
        """Initialize agent behaviors"""
        logger.info(f"Setting up ideological agent {self.agent_id} with ideology '{self.ideology}' at position ({self.position.x:.1f}, {self.position.y:.1f})")
        
        # Register with the global agent registry
        agent_registry.register_agent(
            agent_id=self.agent_id,
            jid=str(self.jid),
            host_id=self.host_id,
            ideology=self.ideology,
            position=(self.position.x, self.position.y)
        )
        
        # Broadcast behavior - periodically announce ideology to neighbors
        broadcast_behavior = self.IdeologyBroadcastBehaviour(period=config.broadcast_interval)
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", "ideology_broadcast")
        self.add_behaviour(broadcast_behavior, template)
        
        # Message receiving behavior
        receive_behavior = self.MessageReceiveBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(receive_behavior, template)
        
        # Decision making behavior - evaluate ideology changes and community actions
        decision_behavior = self.DecisionMakingBehaviour(period=config.broadcast_interval * 2)
        self.add_behaviour(decision_behavior)
        
        # Community management behavior
        community_behavior = self.CommunityManagementBehaviour(period=config.broadcast_interval * 3)
        self.add_behaviour(community_behavior)
        
        logger.info(f"Agent {self.agent_id} setup complete")
    
    def get_neighbors_within_radius(self) -> List[AgentState]:
        """Get neighbors within influence radius"""
        neighbors = []
        for neighbor_id, neighbor_state in self.neighbors.items():
            if self.position.distance_to(neighbor_state.position) <= config.influence_radius:
                neighbors.append(neighbor_state)
        return neighbors
    
    def calculate_ideology_influence(self) -> Dict[str, int]:
        """Calculate ideology distribution among neighbors"""
        neighbors = self.get_neighbors_within_radius()
        ideology_count = {ideology: 0 for ideology in (config.ideologies or ['red', 'blue', 'green'])}
        
        for neighbor in neighbors:
            ideology_count[neighbor.ideology] += 1
            
        return ideology_count
    
    def should_change_ideology(self) -> Optional[str]:
        """Use constraint programming to determine if ideology should change"""
        # Check cooldown constraint
        if self.current_timestep - self.last_ideology_change < config.ideology_change_cooldown:
            return None
            
        neighbors = self.get_neighbors_within_radius()
        if len(neighbors) == 0:
            return None
            
        # Use constraint solver to determine if change is valid
        return self.constraint_solver.should_change_ideology(
            current_ideology=self.ideology,
            neighbors=[n.ideology for n in neighbors],
            change_threshold=config.ideology_change_threshold,
            last_change_time=self.last_ideology_change,
            current_time=self.current_timestep,
            cooldown=config.ideology_change_cooldown
        )
    
    class IdeologyBroadcastBehaviour(PeriodicBehaviour):
        """Periodically broadcast ideology to all agents"""
        
        async def run(self):
            try:
                # Create broadcast message
                message_content = {
                    "type": "ideology_broadcast",
                    "agent_id": self.agent.agent_id,
                    "ideology": self.agent.ideology,
                    "position": asdict(self.agent.position),
                    "timestep": self.agent.current_timestep,
                    "community_id": self.agent.community_id
                }
                
                # Broadcast to all agents (using XMPP multicast room would be better for scalability)
                msg = Message()
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "ideology_broadcast")
                msg.body = json.dumps(message_content)
                
                # For now, we'll use a simple approach - in production, use XMPP rooms
                # Here we would get list of all agents and send to each
                # For demo, we'll just log the broadcast
                logger.debug(f"Agent {self.agent.agent_id} broadcasting ideology '{self.agent.ideology}'")
                
                self.agent.messages_sent += 1
                self.agent.current_timestep += 1
                
            except Exception as e:
                logger.error(f"Error in broadcast behavior for {self.agent.agent_id}: {e}")
    
    class MessageReceiveBehaviour(PeriodicBehaviour):
        """Handle incoming messages from other agents"""
        
        def __init__(self, period=1.0):
            super().__init__(period=period)
        
        async def run(self):
            try:
                msg = await self.receive(timeout=0.1)
                if msg:
                    await self.handle_message(msg)
            except Exception as e:
                logger.error(f"Error receiving message for {self.agent.agent_id}: {e}")
        
        async def handle_message(self, msg: Message):
            """Process received message"""
            try:
                content = json.loads(msg.body)
                message_type = content.get("type")
                
                if message_type == "ideology_broadcast":
                    await self.handle_ideology_broadcast(content)
                elif message_type == "community_invite":
                    await self.handle_community_invite(content)
                elif message_type == "community_update":
                    await self.handle_community_update(content)
                
                self.agent.messages_received += 1
                
            except Exception as e:
                logger.error(f"Error handling message for {self.agent.agent_id}: {e}")
        
        async def handle_ideology_broadcast(self, content: Dict):
            """Handle ideology broadcast from another agent"""
            sender_id = content["agent_id"]
            if sender_id == self.agent.agent_id:
                return  # Ignore own messages
                
            # Update neighbor information
            neighbor_state = AgentState(
                agent_id=sender_id,
                position=Position(**content["position"]),
                ideology=content["ideology"],
                last_ideology_change=0,  # We don't track this for neighbors
                community_id=content.get("community_id"),
                neighbors=set(),
                ideology_history=[]
            )
            
            self.agent.neighbors[sender_id] = neighbor_state
            logger.debug(f"Agent {self.agent.agent_id} received broadcast from {sender_id} with ideology '{neighbor_state.ideology}'")
        
        async def handle_community_invite(self, content: Dict):
            """Handle invitation to join a community"""
            community_id = content["community_id"]
            community_ideology = content["ideology"]
            
            # Decide whether to join based on ideology similarity
            if (community_ideology == self.agent.ideology and 
                self.agent.community_id is None):
                self.agent.community_id = community_id
                logger.info(f"Agent {self.agent.agent_id} joined community {community_id}")
        
        async def handle_community_update(self, content: Dict):
            """Handle community status updates"""
            pass
    
    class DecisionMakingBehaviour(PeriodicBehaviour):
        """Evaluate whether to change ideology based on neighbor influence"""
        
        async def run(self):
            try:
                # Check if we should change ideology
                new_ideology = self.agent.should_change_ideology()
                
                if new_ideology and new_ideology != self.agent.ideology:
                    old_ideology = self.agent.ideology
                    self.agent.ideology = new_ideology
                    self.agent.last_ideology_change = self.agent.current_timestep
                    self.agent.ideology_changes += 1
                    self.agent.ideology_history.append((self.agent.current_timestep, new_ideology))
                    
                    # Leave current community if ideology changed
                    if self.agent.community_id:
                        self.agent.community_id = None
                    
                    logger.info(f"Agent {self.agent.agent_id} changed ideology from '{old_ideology}' to '{new_ideology}'")
                    
            except Exception as e:
                logger.error(f"Error in decision making for {self.agent.agent_id}: {e}")
    
    class CommunityManagementBehaviour(PeriodicBehaviour):
        """Manage community membership and formation"""
        
        async def run(self):
            try:
                # If not in a community, try to form or join one
                if self.agent.community_id is None:
                    await self.try_form_or_join_community()
                else:
                    await self.manage_existing_community()
                    
            except Exception as e:
                logger.error(f"Error in community management for {self.agent.agent_id}: {e}")
        
        async def try_form_or_join_community(self):
            """Try to form a new community or join an existing one"""
            neighbors = self.agent.get_neighbors_within_radius()
            same_ideology_neighbors = [n for n in neighbors if n.ideology == self.agent.ideology]
            
            if len(same_ideology_neighbors) >= config.min_community_size - 1:  # -1 because we count ourselves
                # Check if any neighbors are already in communities we can join
                existing_communities = set()
                for neighbor in same_ideology_neighbors:
                    if neighbor.community_id:
                        existing_communities.add(neighbor.community_id)
                
                if existing_communities:
                    # Try to join an existing community
                    community_id = random.choice(list(existing_communities))
                    self.agent.community_id = community_id
                    logger.info(f"Agent {self.agent.agent_id} joined existing community {community_id}")
                else:
                    # Form a new community
                    community_id = f"community_{self.agent.ideology}_{self.agent.agent_id}_{self.agent.current_timestep}"
                    self.agent.community_id = community_id
                    logger.info(f"Agent {self.agent.agent_id} formed new community {community_id}")
        
        async def manage_existing_community(self):
            """Manage existing community membership"""
            # Check if we should leave the community due to ideology change
            neighbors = self.agent.get_neighbors_within_radius()
            same_community_neighbors = [n for n in neighbors 
                                      if n.community_id == self.agent.community_id]
            
            # Leave if too few community members nearby
            if len(same_community_neighbors) < config.min_community_size - 1:
                old_community = self.agent.community_id
                self.agent.community_id = None
                logger.info(f"Agent {self.agent.agent_id} left community {old_community} (too few members)")
    
    async def get_agent_stats(self) -> Dict:
        """Get current agent statistics"""
        neighbors = self.get_neighbors_within_radius()
        ideology_distribution = self.calculate_ideology_influence()
        
        return {
            "agent_id": self.agent_id,
            "ideology": self.ideology,
            "position": asdict(self.position),
            "community_id": self.community_id,
            "neighbor_count": len(neighbors),
            "ideology_distribution": ideology_distribution,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "ideology_changes": self.ideology_changes,
            "current_timestep": self.current_timestep
        }
    
    async def cleanup(self):
        """Cleanup when agent is stopping"""
        logger.info(f"Agent {self.agent_id} cleanup complete")
