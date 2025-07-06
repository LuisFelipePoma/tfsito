import datetime
import json
import time
import random
import math
from spade.agent import Agent
import logging
from spade.message import Message
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.template import Template

from agent.libs.taxi_constraints import (
    TaxiDecisionSolver, TaxiState, TaxiConstraints, 
    RideRequest, parse_ride_request_from_message
)
from gui.taxi_tkinter_gui import get_gui

logger = logging.getLogger(__name__)


class TaxiAgent(Agent):
    """SPADE agent representing a taxi in the dispatch system"""

    def __init__(self, jid: str, password: str, host_id: str, max_capacity: int = 4):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0]
        self.host_id = host_id
        
        # Initialize taxi state
        self.taxi_state = TaxiState(
            taxi_id=self.agent_id,
            current_position=(random.uniform(-50, 50), random.uniform(-50, 50)),
            max_capacity=max_capacity,
            current_passengers=0,
            is_available=True
        )
        
        # Movement and pickup state
        self.target_position = None
        self.current_client = None
        self.is_moving_to_pickup = False
        self.is_moving_to_destination = False
        self.movement_speed = 2.0
        
        # Initialize constraints and decision solver
        self.constraints = TaxiConstraints()
        self.decision_solver = TaxiDecisionSolver(self.constraints)
            
        # Register with GUI
        gui = get_gui()
        if gui:
            gui.add_taxi(self.agent_id, self.taxi_state.current_position, max_capacity)

    class RideRequestHandler(CyclicBehaviour):
        """Behavior to handle incoming ride requests"""
        
        async def run(self):
            msg = await self.receive(timeout=10)
            
            if msg:
                logger.info(f"Taxi {self.agent.agent_id} received ride request from {msg.sender}")
                
                ride_request = parse_ride_request_from_message(str(msg.body), str(msg.sender))
                
                if ride_request:
                    distance = self._calculate_distance_to_client(ride_request.client_position)
                    ride_request.distancia_al_cliente = distance
                    
                    accept, reason, details = self._make_decision(ride_request)
                    
                    response = self._create_response_message(accept, reason, details)
                    reply = Message(to=str(msg.sender))
                    reply.body = response
                    reply.set_metadata("performative", "inform-result")
                    
                    await self.send(reply)
                    logger.info(f"Taxi {self.agent.agent_id}: {reason}")
                    
                    if accept:
                        await self._accept_ride(ride_request)
                else:
                    logger.warning(f"Failed to parse ride request from {msg.sender}")
        
        async def _accept_ride(self, ride_request: RideRequest):
            """Handle accepted ride"""
            self.agent.current_client = ride_request
            self.agent.is_moving_to_pickup = True
            self.agent.target_position = ride_request.client_position
            self.agent.taxi_state.is_available = False
            
            gui = get_gui()
            if gui:
                gui.assign_taxi_to_client(self.agent.agent_id, ride_request.client_id)
            
            logger.info(f"Taxi {self.agent.agent_id} moving to pickup client {ride_request.client_id}")
        
        def _calculate_distance_to_client(self, client_position: tuple) -> float:
            """Calculate distance from taxi to client"""
            taxi_pos = self.agent.taxi_state.current_position
            return self.agent.decision_solver.calculate_estimated_distance(taxi_pos, client_position)
        
        def _make_decision(self, ride_request: RideRequest) -> tuple[bool, str, dict]:
            """Make decision whether to accept ride"""
            return self.agent.decision_solver.can_accept_ride(self.agent.taxi_state, ride_request)
        
        def _create_response_message(self, accept: bool, reason: str, details: dict) -> str:
            """Create response message for client"""
            response_data = {
                'taxi_id': self.agent.agent_id,
                'accepted': accept,
                'reason': reason,
                'details': details,
                'timestamp': time.time()
            }
            
            if accept and self.agent.current_client:
                distance = self.agent.decision_solver.calculate_estimated_distance(
                    self.agent.taxi_state.current_position,
                    self.agent.current_client.client_position
                )
                estimated_time = max(1, int(distance / self.agent.movement_speed / 60))
                response_data['estimated_arrival'] = estimated_time
                response_data['taxi_position'] = self.agent.taxi_state.current_position
            
            return json.dumps(response_data)

    class MovementBehaviour(PeriodicBehaviour):
        """Behavior to handle taxi movement"""
        
        async def run(self):
            if self.agent.target_position:
                await self._move_towards_target()
            
            # Update GUI
            gui = get_gui()
            if gui:
                gui.update_taxi_state(self.agent.agent_id, {
                    'position': self.agent.taxi_state.current_position,
                    'current_passengers': self.agent.taxi_state.current_passengers,
                    'is_available': self.agent.taxi_state.is_available
                })
        
        async def _move_towards_target(self):
            """Move taxi towards target position"""
            current_pos = self.agent.taxi_state.current_position
            target_pos = self.agent.target_position
            
            dx = target_pos[0] - current_pos[0]
            dy = target_pos[1] - current_pos[1]
            distance = math.sqrt(dx*dx + dy*dy)
            
            move_step = self.agent.movement_speed * 0.1
            
            if distance < move_step:
                self.agent.taxi_state.current_position = target_pos
                await self._handle_arrival()
            else:
                new_x = current_pos[0] + (dx / distance) * move_step
                new_y = current_pos[1] + (dy / distance) * move_step
                self.agent.taxi_state.current_position = (new_x, new_y)
        
        async def _handle_arrival(self):
            """Handle arrival at target destination"""
            if self.agent.is_moving_to_pickup:
                await self._pickup_client()
            elif self.agent.is_moving_to_destination:
                await self._dropoff_client()
        
        async def _pickup_client(self):
            """Handle client pickup"""
            if self.agent.current_client:
                logger.info(f"Taxi {self.agent.agent_id} picked up client {self.agent.current_client.client_id}")
                
                self.agent.taxi_state.current_passengers += self.agent.current_client.n_pasajeros
                self.agent.target_position = self.agent.current_client.destination
                self.agent.is_moving_to_pickup = False
                self.agent.is_moving_to_destination = True
                
                logger.info(f"Taxi {self.agent.agent_id} heading to destination {self.agent.current_client.destination}")
        
        async def _dropoff_client(self):
            """Handle client dropoff"""
            if self.agent.current_client:
                logger.info(f"Taxi {self.agent.agent_id} dropped off client {self.agent.current_client.client_id}")
                
                self.agent.taxi_state.current_passengers = 0
                self.agent.taxi_state.is_available = True
                self.agent.current_client = None
                self.agent.target_position = None
                self.agent.is_moving_to_pickup = False
                self.agent.is_moving_to_destination = False
                
                gui = get_gui()
                if gui:
                    gui.complete_ride(self.agent.current_client.client_id if self.agent.current_client else "unknown")

    class StatusUpdateBehaviour(PeriodicBehaviour):
        """Periodic behavior to update taxi status"""
        
        async def run(self):
            # Random small movements while idle
            if not self.agent.target_position and random.random() < 0.1:
                x, y = self.agent.taxi_state.current_position
                x += random.uniform(-1, 1)
                y += random.uniform(-1, 1)
                self.agent.taxi_state.current_position = (x, y)
            
            # Log status periodically
            if random.random() < 0.1:
                status = {
                    'taxi_id': self.agent.agent_id,
                    'position': self.agent.taxi_state.current_position,
                    'passengers': self.agent.taxi_state.current_passengers,
                    'available': self.agent.taxi_state.is_available,
                    'moving': self.agent.target_position is not None
                }
                logger.debug(f"Taxi status: {status}")

    async def setup(self):
        """Initialize agent behaviors"""
        logger.info(f"Setting up taxi agent {self.agent_id}")
        
        # Add ride request handler
        request_template = Template()
        request_template.set_metadata("performative", "request")
        request_handler = self.RideRequestHandler()
        self.add_behaviour(request_handler, request_template)
        
        # Add movement behavior
        movement_behavior = self.MovementBehaviour(period=0.1)
        self.add_behaviour(movement_behavior)
        
        # Add status update behavior
        status_behavior = self.StatusUpdateBehaviour(period=10)
        self.add_behaviour(status_behavior)
        
        logger.info(f"Taxi {self.agent_id} setup complete at position {self.taxi_state.current_position}")

    async def cleanup(self):
        """Cleanup when agent is stopping"""
        logger.info(f"Taxi {self.agent_id} cleanup complete")


class SurvivorAgent(Agent):
    """Simple survivor agent for basic testing"""

    def __init__(self, jid: str, password: str, host_id: str):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0]
        self.host_id = host_id

    class InformBehaviour(PeriodicBehaviour):
        async def run(self):
            msg = Message(to=self.get("receiver_jid"))
            msg.body = "Hello World"
            await self.send(msg)
            
            if self.counter == 5:
                self.kill()
            self.counter += 1

        async def on_end(self):
            await self.agent.stop()

        async def on_start(self):
            self.counter = 0
        
    async def setup(self):
        """Initialize agent behaviors"""
        logger.info(f"Setting up agent {self.agent_id}")
        start_at = datetime.datetime.now() + datetime.timedelta(seconds=5)
        b = self.InformBehaviour(period=2, start_at=start_at)
        self.add_behaviour(b)
        logger.info(f"Agent {self.agent_id} setup complete")

    async def cleanup(self):
        """Cleanup when agent is stopping"""
        logger.info(f"Agent {self.agent_id} cleanup complete")
