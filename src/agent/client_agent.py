"""
Client agent for taxi dispatch system
"""

import datetime
import json
import time
import random
from spade.agent import Agent
import logging
from spade.message import Message
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.template import Template

from agent.libs.taxi_constraints import create_ride_request_message
from gui.taxi_tkinter_gui import get_gui

logger = logging.getLogger(__name__)


class ClientAgent(Agent):
    """SPADE agent representing a client requesting taxi rides"""

    def __init__(self, jid: str, password: str, host_id: str, is_disabled: bool = False):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0]
        self.host_id = host_id
        self.is_disabled = is_disabled
        self.current_position = (random.uniform(-50, 50), random.uniform(-50, 50))
        self.waiting_for_ride = False
        self.wait_start_time = None
        self.ride_requests_sent = 0
        self.destination = None
        
        # Register with GUI
        gui = get_gui()
        if gui:
            n_passengers = random.randint(1, 4)
            gui.add_client(self.agent_id, self.current_position, n_passengers, is_disabled)

    class RideRequestBehaviour(PeriodicBehaviour):
        """Behavior to send ride requests to available taxis"""
        
        async def run(self):
            if not self.agent.waiting_for_ride and random.random() < 0.3:  # 30% chance to request ride
                await self._send_ride_request()
        
        async def _send_ride_request(self):
            """Send a ride request to all available taxis"""
            # Generate ride request parameters
            n_passengers = random.randint(1, 4)
            destination = (random.uniform(-50, 50), random.uniform(-50, 50))
            
            # Calculate wait time if already waiting
            wait_time = 0
            if self.agent.wait_start_time:
                wait_time = int((time.time() - self.agent.wait_start_time) / 60)  # minutes
            
            # Create ride request message
            message_body = create_ride_request_message(
                n_pasajeros=n_passengers,
                tiempo_espera_cliente=wait_time,
                es_discapacitado=self.agent.is_disabled,
                distancia_al_cliente=0.0,  # Will be calculated by taxi
                client_position=self.agent.current_position,
                destination=destination
            )
            
            # Send to multiple taxis (broadcast to taxi agents)
            taxi_jids = self._get_available_taxi_jids()
            
            for taxi_jid in taxi_jids:
                msg = Message(to=taxi_jid)
                msg.body = message_body
                msg.set_metadata("performative", "request")
                
                await self.send(msg)
                logger.info(f"Client {self.agent.agent_id} sent ride request to {taxi_jid}")
            
            self.agent.waiting_for_ride = True
            self.agent.wait_start_time = time.time()
            self.agent.ride_requests_sent += 1
            
            logger.info(f"Client {self.agent.agent_id} requesting ride: {n_passengers} passengers, "
                       f"disabled: {self.agent.is_disabled}, wait time: {wait_time} min")
        
        def _get_available_taxi_jids(self) -> list:
            """Get list of available taxi JIDs (in real implementation, this would query the system)"""
            # For simulation, generate some taxi JIDs
            domain = self.agent.host_id
            taxi_count = random.randint(2, 5)
            return [f"taxi{i}@{domain}" for i in range(1, taxi_count + 1)]

    class ResponseHandler(CyclicBehaviour):
        """Behavior to handle responses from taxis"""
        
        async def run(self):
            # Wait for response messages
            msg = await self.receive(timeout=10)
            
            if msg and self.agent.waiting_for_ride:
                try:
                    response_data = json.loads(str(msg.body))
                    taxi_id = response_data.get('taxi_id', str(msg.sender))
                    accepted = response_data.get('accepted', False)
                    reason = response_data.get('reason', 'No reason provided')
                    
                    logger.info(f"Client {self.agent.agent_id} received response from {taxi_id}: "
                               f"{'ACCEPTED' if accepted else 'REJECTED'} - {reason}")
                    
                    if accepted:
                        # Ride accepted, stop waiting
                        self.agent.waiting_for_ride = False
                        self.agent.wait_start_time = None
                        
                        # Log acceptance details
                        estimated_arrival = response_data.get('estimated_arrival', 'Unknown')
                        taxi_position = response_data.get('taxi_position', 'Unknown')
                        
                        logger.info(f"Client {self.agent.agent_id} ride confirmed! "
                                   f"Taxi ETA: {estimated_arrival} min, "
                                   f"Taxi position: {taxi_position}")
                        
                        # Simulate ride completion after some time
                        await self._simulate_ride_completion()
                    
                except json.JSONDecodeError:
                    logger.warning(f"Client {self.agent.agent_id} received invalid response from {msg.sender}")
                except Exception as e:
                    logger.error(f"Error processing taxi response: {e}")
        
        async def _simulate_ride_completion(self):
            """Simulate the completion of a ride"""
            import asyncio
            
            # Wait for ride duration (simulate)
            ride_duration = random.randint(10, 30)  # 10-30 seconds for simulation
            await asyncio.sleep(ride_duration)
            
            # Update client position (arrived at destination)
            self.agent.current_position = (random.uniform(-50, 50), random.uniform(-50, 50))
            
            logger.info(f"Client {self.agent.agent_id} ride completed. New position: {self.agent.current_position}")

    async def setup(self):
        """Initialize agent behaviors"""
        logger.info(f"Setting up client agent {self.agent_id}")
        
        # Add ride request behavior (every 60 seconds)
        request_behavior = self.RideRequestBehaviour(period=60)
        self.add_behaviour(request_behavior)
        
        # Add response handler
        response_template = Template()
        response_template.set_metadata("performative", "inform-result")
        response_handler = self.ResponseHandler()
        self.add_behaviour(response_handler, response_template)
        
        disability_status = "disabled" if self.is_disabled else "regular"
        logger.info(f"Client {self.agent_id} ({disability_status}) setup complete at position {self.current_position}")

    async def cleanup(self):
        """Cleanup when agent is stopping"""
        logger.info(f"Client {self.agent_id} cleanup complete. Requests sent: {self.ride_requests_sent}")
