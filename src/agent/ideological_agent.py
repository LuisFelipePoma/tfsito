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
        self.last_movement_time = 0  # Track last movement time for precise timing
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
        
        # Movement behavior
        movement_behavior = self.MovementBehaviour(period=config.movement_interval)
        self.add_behaviour(movement_behavior)
        
        # GUI update behavior - send state updates to GUI agent  
        gui_update_behavior = self.GUIUpdateBehaviour(period=3.0)
        self.add_behaviour(gui_update_behavior)
        
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
        """Determine if ideology should change based on 60% neighbor pressure rule"""
        # Check cooldown constraint
        if self.current_timestep - self.last_ideology_change < config.ideology_change_cooldown:
            return None
            
        neighbors = self.get_neighbors_within_radius()
        if len(neighbors) == 0:
            return None
        
        # Count ideologies among neighbors
        ideology_count = {}
        for neighbor in neighbors:
            ideology_count[neighbor.ideology] = ideology_count.get(neighbor.ideology, 0) + 1
        
        total_neighbors = len(neighbors)
        
        # Find most common ideology among neighbors
        if ideology_count:
            dominant_ideology = max(ideology_count.keys(), key=lambda k: ideology_count[k])
            dominant_percentage = ideology_count[dominant_ideology] / total_neighbors
            
            # Apply 60% rule: change ideology only if more than 60% of neighbors have different ideology
            if (dominant_ideology != self.ideology and 
                dominant_percentage > config.ideology_pressure_threshold):
                return dominant_ideology
        
        return None
    
    def check_community_compatibility(self, other_ideology: str) -> bool:
        """Check if an ideology is compatible for community formation"""
        if self.ideology == other_ideology:
            return True
        
        # Add custom compatibility rules here
        # For now, only same ideology agents can form communities
        return False
    
    def detect_community_conflicts(self) -> List[Tuple[str, str]]:
        """Detect conflicts between different communities in vicinity"""
        conflicts = []
        neighbors = self.get_neighbors_within_radius()
        
        # Group neighbors by community
        community_groups = {}
        for neighbor in neighbors:
            if neighbor.community_id and neighbor.community_id != self.community_id:
                if neighbor.community_id not in community_groups:
                    community_groups[neighbor.community_id] = []
                community_groups[neighbor.community_id].append(neighbor)
        
        # Check for conflicts based on ideology differences and proximity
        for community_id, members in community_groups.items():
            if len(members) >= config.min_community_size:
                # Calculate ideology difference
                different_ideology_count = sum(1 for member in members 
                                             if member.ideology != self.ideology)
                conflict_ratio = different_ideology_count / len(members)
                
                if conflict_ratio > config.conflict_threshold:
                    conflicts.append((self.community_id or "individual", community_id))
        
        return conflicts
    
    def calculate_radicalization_pressure(self) -> float:
        """Calculate pressure towards radicalization based on community dynamics"""
        if not self.community_id:
            return 0.0
            
        neighbors = self.get_neighbors_within_radius()
        same_community_neighbors = [n for n in neighbors 
                                  if n.community_id == self.community_id]
        
        if len(same_community_neighbors) == 0:
            return 0.0
        
        # Calculate pressure based on community size and ideology uniformity
        community_size = len(same_community_neighbors) + 1  # +1 for self
        uniformity = len([n for n in same_community_neighbors 
                         if n.ideology == self.ideology]) / len(same_community_neighbors)
        
        # Larger, more uniform communities create more radicalization pressure
        radicalization_pressure = (community_size / config.max_community_size) * uniformity
        
        return min(radicalization_pressure, 1.0)
    
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
            """Try to form a new community or join an existing one with compatibility rules"""
            neighbors = self.agent.get_neighbors_within_radius()
            
            # Filter neighbors by ideology compatibility  
            compatible_neighbors = [n for n in neighbors 
                                  if self.agent.check_community_compatibility(n.ideology)]
            
            if len(compatible_neighbors) >= config.min_community_size - 1:  # -1 because we count ourselves
                # Check if any compatible neighbors are already in communities we can join
                existing_communities = {}
                for neighbor in compatible_neighbors:
                    if neighbor.community_id:
                        if neighbor.community_id not in existing_communities:
                            existing_communities[neighbor.community_id] = []
                        existing_communities[neighbor.community_id].append(neighbor)
                
                # Try to join the largest compatible community
                if existing_communities:
                    best_community = max(existing_communities.keys(), 
                                       key=lambda cid: len(existing_communities[cid]))
                    
                    # Check community size limit
                    if len(existing_communities[best_community]) < config.max_community_size:
                        self.agent.community_id = best_community
                        logger.info(f"Agent {self.agent.agent_id} joined existing community {best_community}")
                        return
                
                # Form a new community if we can't join an existing one
                if len(compatible_neighbors) >= config.min_community_size - 1:
                    community_id = f"community_{self.agent.ideology}_{self.agent.agent_id}_{self.agent.current_timestep}"
                    self.agent.community_id = community_id
                    logger.info(f"Agent {self.agent.agent_id} formed new community {community_id}")
        
        async def manage_existing_community(self):
            """Manage existing community membership with conflict detection"""
            neighbors = self.agent.get_neighbors_within_radius()
            same_community_neighbors = [n for n in neighbors 
                                      if n.community_id == self.agent.community_id]
            
            # Check for community conflicts
            conflicts = self.agent.detect_community_conflicts()
            if conflicts:
                logger.info(f"Agent {self.agent.agent_id} detected conflicts: {conflicts}")
            
            # Leave if too few community members nearby
            if len(same_community_neighbors) < config.min_community_size - 1:
                old_community = self.agent.community_id
                self.agent.community_id = None
                logger.info(f"Agent {self.agent.agent_id} left community {old_community} (too few members)")
                return
            
            # Check for community splitting due to overcrowding
            if len(same_community_neighbors) > config.max_community_size:
                # Calculate if we should split off
                radicalization = self.agent.calculate_radicalization_pressure()
                if radicalization > config.radicalization_threshold:
                    # Form a new splinter community
                    new_community_id = f"splinter_{self.agent.ideology}_{self.agent.agent_id}_{self.agent.current_timestep}"
                    old_community = self.agent.community_id
                    self.agent.community_id = new_community_id
                    logger.info(f"Agent {self.agent.agent_id} split from {old_community} to form {new_community_id}")
            
            # Update ideology in registry if changed
            agent_registry.update_agent_ideology(self.agent.agent_id, self.agent.ideology)
    
    class MovementBehaviour(PeriodicBehaviour):
        """Handle agent movement based on social dynamics every 1.5 seconds"""
        
        async def run(self):
            try:
                logger.debug(f"Agent {self.agent.agent_id} attempting movement at timestep {self.agent.current_timestep}")
                
                # Attempt movement
                moved = self.agent.attempt_movement()
                
                if moved:
                    logger.info(f"Agent {self.agent.agent_id} moved to position ({self.agent.position.x:.1f}, {self.agent.position.y:.1f})")
                    # Broadcast new position after movement
                    await self.broadcast_position_update()
                else:
                    logger.debug(f"Agent {self.agent.agent_id} did not move this cycle")
                    
            except Exception as e:
                logger.error(f"Error in movement behavior for {self.agent.agent_id}: {e}")
        
        async def broadcast_position_update(self):
            """Broadcast position update after movement"""
            message_content = {
                "type": "position_update",
                "agent_id": self.agent.agent_id,
                "position": asdict(self.agent.position),
                "ideology": self.agent.ideology,
                "timestep": self.agent.current_timestep
            }
            
            msg = Message()
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "position_update")
            msg.body = json.dumps(message_content)
            
            logger.debug(f"Agent {self.agent.agent_id} broadcasting position update")

    class GUIUpdateBehaviour(PeriodicBehaviour):
        """Send periodic state updates to GUI agent"""
        
        async def run(self):
            try:
                # Get current agent statistics  
                agent_stats = await self.agent.get_agent_stats()
                
                # Add current position from registry (to ensure it's up to date)
                agent_stats["position"] = {
                    "x": self.agent.position.x,
                    "y": self.agent.position.y
                }
                
                # Add message type for GUI agent
                agent_stats["type"] = "agent_state_update"
                agent_stats["last_updated"] = time.time()
                
                logger.debug(f"Agent {self.agent.agent_id} sending state update: "
                           f"pos=({self.agent.position.x:.1f},{self.agent.position.y:.1f}), "
                           f"ideology={self.agent.ideology}")
                
                # In a real implementation, this would send a message to the GUI agent
                # For now, we'll directly update the agent registry which GUI agent reads
                agent_registry.update_agent_position(self.agent.agent_id, 
                                                   (self.agent.position.x, self.agent.position.y))
                agent_registry.update_agent_ideology(self.agent.agent_id, self.agent.ideology)
                
            except Exception as e:
                logger.error(f"Error in GUI update behavior for {self.agent.agent_id}: {e}")

    def find_valid_move_positions(self, max_distance: Optional[float] = None) -> List[Position]:
        """Find valid positions within movement range"""
        if max_distance is None:
            max_distance = config.movement_range
            
        valid_positions = []
        
        # Generate potential positions in a circle around current position
        for angle in range(0, 360, 30):  # Check 12 directions
            for distance in [max_distance * 0.5, max_distance]:  # Two distance rings
                rad = math.radians(angle)
                new_x = self.position.x + distance * math.cos(rad)
                new_y = self.position.y + distance * math.sin(rad)
                
                # Check bounds
                if 0 <= new_x <= config.grid_width and 0 <= new_y <= config.grid_height:
                    new_pos = Position(new_x, new_y)
                    
                    # Check if position is free (no other agent too close)
                    if self.is_position_free(new_pos):
                        valid_positions.append(new_pos)
        
        return valid_positions
    
    def is_position_free(self, position: Position, min_distance: float = 1.0) -> bool:
        """Check if a position is free of other agents"""
        for neighbor_state in self.neighbors.values():
            if neighbor_state.position.distance_to(position) < min_distance:
                return False
        return True
    
    def calculate_movement_desire(self) -> Optional[Position]:
        """Calculate desired movement based on social dynamics - executed every 1.5 seconds"""
        # Increase movement probability for more consistent movement
        if random.random() > 0.7:  # 70% chance to attempt movement each cycle
            logger.debug(f"Agent {self.agent_id} skipping movement this cycle (30% random skip)")
            return None
            
        neighbors = self.get_neighbors_within_radius()
        if not neighbors:
            logger.debug(f"Agent {self.agent_id} has no neighbors, performing random exploration")
            return self.get_random_move()  # Random exploration if no neighbors
        
        # Calculate forces from neighbors
        attraction_force = Position(0, 0)
        repulsion_force = Position(0, 0)
        
        similar_count = 0
        different_count = 0
        
        for neighbor in neighbors:
            direction_x = neighbor.position.x - self.position.x
            direction_y = neighbor.position.y - self.position.y
            distance = self.position.distance_to(neighbor.position)
            
            if distance == 0:
                continue
                
            # Normalize direction
            direction_x /= distance
            direction_y /= distance
            
            # Apply forces based on ideology similarity
            if neighbor.ideology == self.ideology:
                similar_count += 1
                # Attract to similar agents (higher probability for consistent movement)
                if random.random() < 0.8:  # Increased from config value for more movement
                    strength = 1.0 / (distance + 0.1)  # Closer = stronger attraction
                    attraction_force.x += direction_x * strength
                    attraction_force.y += direction_y * strength
            else:
                different_count += 1
                # Repel from different agents
                if random.random() < 0.6:  # Increased from config value
                    strength = 1.0 / (distance + 0.1)  # Closer = stronger repulsion
                    repulsion_force.x -= direction_x * strength
                    repulsion_force.y -= direction_y * strength
        
        logger.debug(f"Agent {self.agent_id} neighbors: {similar_count} similar, {different_count} different")
        
        # Combine forces
        total_force_x = attraction_force.x + repulsion_force.x
        total_force_y = attraction_force.y + repulsion_force.y
        
        # If forces are too weak, do random movement
        force_magnitude = math.sqrt(total_force_x**2 + total_force_y**2)
        if force_magnitude < 0.05:  # Reduced threshold for more sensitive movement
            logger.debug(f"Agent {self.agent_id} forces too weak ({force_magnitude:.3f}), random movement")
            return self.get_random_move()
        
        # Normalize and apply movement range
        total_force_x /= force_magnitude
        total_force_y /= force_magnitude
        
        new_x = self.position.x + total_force_x * config.movement_range
        new_y = self.position.y + total_force_y * config.movement_range
        
        # Clamp to grid bounds
        new_x = max(0, min(config.grid_width, new_x))
        new_y = max(0, min(config.grid_height, new_y))
        
        target_position = Position(new_x, new_y)
        logger.debug(f"Agent {self.agent_id} calculated movement target: ({new_x:.1f}, {new_y:.1f})")
        
        return target_position
    
    def get_random_move(self) -> Position:
        """Get a random movement within range"""
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(0.5, config.movement_range)
        
        new_x = self.position.x + distance * math.cos(angle)
        new_y = self.position.y + distance * math.sin(angle)
        
        # Clamp to grid bounds
        new_x = max(0, min(config.grid_width, new_x))
        new_y = max(0, min(config.grid_height, new_y))
        
        return Position(new_x, new_y)
    
    def attempt_movement(self) -> bool:
        """Attempt to move to a new position every 1.5 seconds"""
        # Always calculate movement desire - remove randomness for consistent movement
        desired_position = self.calculate_movement_desire()
        
        if desired_position is None:
            logger.debug(f"Agent {self.agent_id} has no movement desire this cycle")
            return False
            
        # Find the closest valid position to our desired position
        valid_positions = self.find_valid_move_positions()
        
        if not valid_positions:
            logger.debug(f"Agent {self.agent_id} has no valid move positions available")
            return False  # No valid moves available
        
        # Choose the valid position closest to our desired position
        best_position = min(valid_positions, 
                           key=lambda pos: desired_position.distance_to(pos))
        
        # Only move if the new position is significantly different (avoid micro-movements)
        movement_distance = self.position.distance_to(best_position)
        if movement_distance < 0.5:  # Minimum meaningful movement
            logger.debug(f"Agent {self.agent_id} movement distance too small ({movement_distance:.2f})")
            return False
        
        # Move to the best position
        old_position = self.position
        self.position = best_position
        
        logger.info(f"Agent {self.agent_id} moved from ({old_position.x:.1f}, {old_position.y:.1f}) "
                   f"to ({self.position.x:.1f}, {self.position.y:.1f}) - distance: {movement_distance:.2f}")
        
        # Update registry with new position
        agent_registry.update_agent_position(self.agent_id, (self.position.x, self.position.y))
        
        return True

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
