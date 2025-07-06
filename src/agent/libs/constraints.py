from ortools.linear_solver import pywraplp
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass
from agent.libs.environment import Position, DangerZone
from config import config

logger = logging.getLogger(__name__)

@dataclass
class MovementConstraints:
    agent_id: str
    current_position: Position
    carry_capacity: int
    current_resources: int
    health: int
    forbidden_zones: List[Position]
    target_resources: List[Position]
    other_agents: List[Position]

@dataclass
class MovementSolution:
    next_position: Position
    estimated_cost: float
    resource_targets: List[Position]
    safe_path: List[Position]

class ConstraintSolver:
    """OR-Tools based constraint programming for agent decisions"""
    
    def __init__(self):
        self.solver = pywraplp.Solver.CreateSolver('SCIP')
        if not self.solver:
            logger.error("Could not create OR-Tools solver")
            raise RuntimeError("OR-Tools solver not available")
    
    def solve_movement_constraints(self, constraints: MovementConstraints) -> Optional[MovementSolution]:
        """
        Solve movement optimization with constraints:
        1. Cannot enter danger zones
        2. Must respect carry capacity
        3. Minimize distance to resources
        4. Avoid conflicts with other agents
        """
        try:
            # Clear previous model
            self.solver.Clear()
            
            current_pos = constraints.current_position
            
            # Generate possible moves (8 directions + stay)
            possible_moves = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    new_x = current_pos.x + dx
                    new_y = current_pos.y + dy
                    
                    # Check bounds
                    if 0 <= new_x < config.grid_width and 0 <= new_y < config.grid_height:
                        new_pos = Position(new_x, new_y)
                        
                        # Check if position is forbidden (danger zone)
                        if new_pos not in constraints.forbidden_zones:
                            possible_moves.append(new_pos)
            
            if not possible_moves:
                return None
            
            # Decision variables: which move to take
            move_vars = {}
            for i, pos in enumerate(possible_moves):
                move_vars[i] = self.solver.IntVar(0, 1, f'move_{i}')
            
            # Constraint: exactly one move
            self.solver.Add(sum(move_vars.values()) == 1)
            
            # Objective: minimize distance to nearest resource
            if constraints.target_resources:
                objective_terms = []
                for i, pos in enumerate(possible_moves):
                    min_distance = min(pos.distance_to(resource_pos) 
                                     for resource_pos in constraints.target_resources)
                    objective_terms.append(move_vars[i] * min_distance)
                
                self.solver.Minimize(sum(objective_terms))
            else:
                # No resources, just stay put
                stay_index = next((i for i, pos in enumerate(possible_moves) 
                                 if pos.x == current_pos.x and pos.y == current_pos.y), 0)
                self.solver.Maximize(move_vars[stay_index])
            
            # Solve
            status = self.solver.Solve()
            
            if status == pywraplp.Solver.OPTIMAL:
                # Find selected move
                selected_move = None
                for i, var in move_vars.items():
                    if var.solution_value() > 0.5:
                        selected_move = possible_moves[i]
                        break
                
                if selected_move:
                    return MovementSolution(
                        next_position=selected_move,
                        estimated_cost=self.solver.Objective().Value(),
                        resource_targets=constraints.target_resources[:3],  # Top 3 targets
                        safe_path=[selected_move]
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error solving movement constraints: {e}")
            return None
    
    def solve_resource_allocation(self, agent_id: str, available_resources: Dict[str, int], 
                                 carry_capacity: int, resource_priorities: Dict[str, float]) -> Dict[str, int]:
        """
        Solve optimal resource allocation considering:
        1. Carry capacity constraint
        2. Resource priorities
        3. Available quantities
        """
        try:
            self.solver.Clear()
            
            # Decision variables: how much of each resource to take
            resource_vars = {}
            for resource_type in available_resources:
                max_amount = min(available_resources[resource_type], carry_capacity)
                resource_vars[resource_type] = self.solver.IntVar(0, max_amount, f'res_{resource_type}')
            
            # Constraint: total weight <= carry capacity
            total_weight = sum(resource_vars.values())
            self.solver.Add(total_weight <= carry_capacity)
            
            # Objective: maximize utility based on priorities
            utility_terms = []
            for resource_type, var in resource_vars.items():
                priority = resource_priorities.get(resource_type, 1.0)
                utility_terms.append(var * priority)
            
            self.solver.Maximize(sum(utility_terms))
            
            # Solve
            status = self.solver.Solve()
            
            if status == pywraplp.Solver.OPTIMAL:
                allocation = {}
                for resource_type, var in resource_vars.items():
                    amount = int(var.solution_value())
                    if amount > 0:
                        allocation[resource_type] = amount
                return allocation
            
            return {}
            
        except Exception as e:
            logger.error(f"Error solving resource allocation: {e}")
            return {}
    
    def solve_alliance_formation(self, agent_id: str, potential_allies: List[str], 
                               trust_levels: Dict[str, float], 
                               resource_needs: Dict[str, int]) -> List[str]:
        """
        Solve alliance formation constraints:
        1. Trust level must exceed threshold
        2. Complementary resource needs
        3. Maximum alliance size
        """
        try:
            self.solver.Clear()
            
            # Filter by trust threshold
            valid_allies = [ally for ally in potential_allies 
                          if trust_levels.get(ally, 0.0) >= config.trust_threshold]
            
            if not valid_allies:
                return []
            
            # Decision variables: include ally in alliance
            ally_vars = {}
            for ally in valid_allies:
                ally_vars[ally] = self.solver.BoolVar(f'ally_{ally}')
            
            # Constraint: maximum alliance size (including self)
            max_alliance_size = min(5, len(valid_allies) + 1)  # Max 5 members
            self.solver.Add(sum(ally_vars.values()) <= max_alliance_size - 1)
            
            # Objective: maximize total trust + resource complementarity
            objective_terms = []
            for ally, var in ally_vars.items():
                trust_score = trust_levels.get(ally, 0.0)
                # Resource complementarity could be calculated here
                objective_terms.append(var * trust_score)
            
            self.solver.Maximize(sum(objective_terms))
            
            # Solve
            status = self.solver.Solve()
            
            if status == pywraplp.Solver.OPTIMAL:
                selected_allies = []
                for ally, var in ally_vars.items():
                    if var.solution_value() > 0.5:
                        selected_allies.append(ally)
                return selected_allies
            
            return []
            
        except Exception as e:
            logger.error(f"Error solving alliance formation: {e}")
            return []
    
    def solve_conflict_resolution(self, agent_id: str, conflicting_agent: str, 
                                disputed_resource: Position, 
                                agent_strength: int, opponent_strength: int) -> str:
        """
        Determine conflict outcome based on:
        1. Relative strength
        2. Resource value
        3. Risk assessment
        """
        try:
            # Simple decision: fight if significantly stronger, otherwise retreat
            strength_ratio = agent_strength / max(opponent_strength, 1)
            
            if strength_ratio > 1.5:
                return "fight"
            elif strength_ratio > 0.8:
                return "negotiate"
            else:
                return "retreat"
                
        except Exception as e:
            logger.error(f"Error solving conflict resolution: {e}")
            return "retreat"
    
    def calculate_path_safety(self, start: Position, end: Position, 
                            danger_zones: List[DangerZone]) -> Tuple[List[Position], float]:
        """
        Calculate safest path between two points avoiding danger zones
        """
        try:
            # Simple A* pathfinding with danger zone avoidance
            from heapq import heappush, heappop
            
            # Grid bounds
            width, height = config.grid_width, config.grid_height
            
            # Create danger map
            danger_map = np.zeros((height, width))
            for zone in danger_zones:
                for y in range(max(0, zone.position.y - zone.radius), 
                             min(height, zone.position.y + zone.radius + 1)):
                    for x in range(max(0, zone.position.x - zone.radius), 
                                 min(width, zone.position.x + zone.radius + 1)):
                        if Position(x, y).distance_to(zone.position) <= zone.radius:
                            danger_map[y, x] = zone.damage
            
            # A* algorithm
            open_set = [(0, start)]
            came_from = {}
            g_score = {start: 0}
            f_score = {start: start.distance_to(end)}
            
            while open_set:
                current_f, current = heappop(open_set)
                
                if current.x == end.x and current.y == end.y:
                    # Reconstruct path
                    path = []
                    while current in came_from:
                        path.append(current)
                        current = came_from[current]
                    path.append(start)
                    path.reverse()
                    
                    # Calculate total danger
                    total_danger = sum(danger_map[pos.y, pos.x] for pos in path)
                    return path, total_danger
                
                # Check neighbors
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        
                        neighbor = Position(current.x + dx, current.y + dy)
                        
                        # Check bounds
                        if not (0 <= neighbor.x < width and 0 <= neighbor.y < height):
                            continue
                        
                        # Calculate movement cost (distance + danger)
                        move_cost = np.sqrt(dx*dx + dy*dy)
                        danger_cost = danger_map[neighbor.y, neighbor.x]
                        tentative_g = g_score[current] + move_cost + danger_cost * 10
                        
                        if neighbor not in g_score or tentative_g < g_score[neighbor]:
                            came_from[neighbor] = current
                            g_score[neighbor] = tentative_g
                            f_score[neighbor] = tentative_g + neighbor.distance_to(end)
                            heappush(open_set, (f_score[neighbor], neighbor))
            
            # No path found, return direct line
            return [start, end], float('inf')
            
        except Exception as e:
            logger.error(f"Error calculating path safety: {e}")
            return [start, end], float('inf')

# Global constraint solver instance
constraint_solver = ConstraintSolver()
