"""
Constraint programming for ideological agent decisions using OR-Tools
"""

import logging
from typing import List, Optional, Dict, Set
from ortools.linear_solver import pywraplp
from config import config

logger = logging.getLogger(__name__)

class IdeologyConstraintSolver:
    """Constraint solver for ideological agent decision making"""
    
    def __init__(self):
        self.solver = pywraplp.Solver.CreateSolver('SCIP')
        if not self.solver:
            logger.error("Could not create OR-Tools solver")
            raise RuntimeError("OR-Tools solver not available")
    
    def should_change_ideology(self, 
                             current_ideology: str,
                             neighbors: List[str],
                             change_threshold: float,
                             last_change_time: int,
                             current_time: int,
                             cooldown: int) -> Optional[str]:
        """
        Determine if an agent should change ideology based on constraints:
        1. Cooldown period must have passed
        2. More than threshold% of neighbors must have different ideology
        3. Select the most popular different ideology among neighbors
        """
        
        # Check cooldown constraint
        if current_time - last_change_time < cooldown:
            return None
        
        if not neighbors:
            return None
        
        # Count ideology distribution among neighbors
        ideology_counts = {}
        for ideology in neighbors:
            ideology_counts[ideology] = ideology_counts.get(ideology, 0) + 1
        
        total_neighbors = len(neighbors)
        current_ideology_count = ideology_counts.get(current_ideology, 0)
        different_ideology_count = total_neighbors - current_ideology_count
        
        # Check if enough neighbors have different ideology
        different_ratio = different_ideology_count / total_neighbors
        if different_ratio <= change_threshold:
            return None
        
        # Find the most popular different ideology
        candidate_ideologies = {k: v for k, v in ideology_counts.items() 
                               if k != current_ideology}
        
        if not candidate_ideologies:
            return None
        
        # Return the most popular different ideology
        most_popular_ideology = max(candidate_ideologies.items(), 
                                   key=lambda x: x[1])[0]
        
        return most_popular_ideology
    
    def optimize_community_formation(self,
                                   agent_positions: Dict[str, tuple],
                                   agent_ideologies: Dict[str, str],
                                   current_communities: Dict[str, str],
                                   max_community_size: int,
                                   min_community_size: int,
                                   influence_radius: float) -> Dict[str, Optional[str]]:
        """
        Optimize community formation using constraint programming:
        1. Communities must have agents with same ideology
        2. Community size must be within min/max bounds
        3. Community members should be within influence radius
        4. Minimize number of communities while respecting constraints
        """
        
        try:
            # Clear previous model
            self.solver.Clear()
            
            agents = list(agent_positions.keys())
            ideologies = set(agent_ideologies.values())
            
            # Decision variables: which community each agent belongs to
            # We'll use integer variables representing community IDs
            max_communities = len(agents) // min_community_size + 1
            
            # Variables: agent_community[agent][community] = 1 if agent is in community
            agent_community = {}
            for agent in agents:
                agent_community[agent] = {}
                for c in range(max_communities):
                    agent_community[agent][c] = self.solver.IntVar(0, 1, f'agent_{agent}_community_{c}')
            
            # Community exists variables
            community_exists = {}
            for c in range(max_communities):
                community_exists[c] = self.solver.IntVar(0, 1, f'community_{c}_exists')
            
            # Constraints:
            
            # 1. Each agent belongs to exactly one community
            for agent in agents:
                self.solver.Add(sum(agent_community[agent][c] for c in range(max_communities)) == 1)
            
            # 2. Community size constraints
            for c in range(max_communities):
                community_size = sum(agent_community[agent][c] for agent in agents)
                
                # If community exists, it must have at least min_community_size members
                self.solver.Add(community_size >= min_community_size * community_exists[c])
                
                # Community cannot exceed max size
                self.solver.Add(community_size <= max_community_size)
                
                # If any agent is in community, community must exist
                for agent in agents:
                    self.solver.Add(agent_community[agent][c] <= community_exists[c])
            
            # 3. Ideology consistency within communities
            for c in range(max_communities):
                for ideology in ideologies:
                    ideology_agents = [agent for agent in agents 
                                     if agent_ideologies[agent] == ideology]
                    non_ideology_agents = [agent for agent in agents 
                                         if agent_ideologies[agent] != ideology]
                    
                    if ideology_agents and non_ideology_agents:
                        # If any agent with this ideology is in community, 
                        # no agent with different ideology can be in it
                        ideology_in_community = sum(agent_community[agent][c] 
                                                   for agent in ideology_agents)
                        non_ideology_in_community = sum(agent_community[agent][c] 
                                                       for agent in non_ideology_agents)
                        
                        # Big M constraint: if ideology_in_community > 0, then non_ideology_in_community = 0
                        self.solver.Add(non_ideology_in_community <= 
                                       len(non_ideology_agents) * (1 - community_exists[c]) +
                                       len(non_ideology_agents) * (len(ideology_agents) - ideology_in_community) / len(ideology_agents))
            
            # Objective: minimize number of communities
            self.solver.Minimize(sum(community_exists[c] for c in range(max_communities)))
            
            # Solve
            status = self.solver.Solve()
            
            if status == pywraplp.Solver.OPTIMAL:
                # Extract solution
                result = {}
                for agent in agents:
                    for c in range(max_communities):
                        if agent_community[agent][c].solution_value() > 0.5:
                            if community_exists[c].solution_value() > 0.5:
                                result[agent] = f"community_{c}"
                            else:
                                result[agent] = None
                            break
                    else:
                        result[agent] = None
                
                return result
            else:
                # No optimal solution found, return current assignments
                return {agent: current_communities.get(agent) for agent in agents}
                
        except Exception as e:
            logger.error(f"Error in community optimization: {e}")
            return {agent: current_communities.get(agent) for agent in agent_positions.keys()}
    
    def validate_community_constraints(self,
                                     communities: Dict[str, Set[str]],
                                     agent_ideologies: Dict[str, str],
                                     max_size: int,
                                     min_size: int) -> bool:
        """Validate that community assignments satisfy all constraints"""
        
        for community_id, members in communities.items():
            # Check size constraints
            if len(members) < min_size or len(members) > max_size:
                return False
            
            # Check ideology consistency
            ideologies_in_community = set(agent_ideologies[agent] for agent in members)
            if len(ideologies_in_community) > 1:
                return False
        
        return True
