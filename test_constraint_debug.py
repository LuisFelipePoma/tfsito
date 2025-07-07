#!/usr/bin/env python3
"""
Test de debug para el sistema de constraint programming
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logging
import time

# Set up logging with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(message)s'
)

logger = logging.getLogger(__name__)

def test_constraint_programming_debug():
    """Test constraint programming with detailed debugging"""
    from gui.taxi_tkinter_gui import TaxiTkinterGUI
    
    logger.info("🧪 Testing constraint programming with detailed debugging...")
    
    # Create GUI instance without showing window
    gui = TaxiTkinterGUI()
    
    # Add taxi
    gui.add_taxi("test_taxi", (0, 0))
    taxi = gui.taxis["test_taxi"]
    
    # Add client close to the taxi
    gui.add_client("test_client", (10, 10), 2, False)
    client = gui.clients["test_client"]
    
    logger.info(f"   Taxi: {taxi.taxi_id} at {taxi.position}, available: {taxi.is_available}, cycle_mode: {taxi.cycle_mode}")
    logger.info(f"   Client: {client.client_id} at {client.position}, passengers: {client.n_passengers}")
    
    # Calculate distance manually
    distance = ((taxi.position[0] - client.position[0])**2 + 
               (taxi.position[1] - client.position[1])**2)**0.5
    logger.info(f"   Distance: {distance:.2f}")
    
    # Simulate until taxi detects client
    max_iterations = 5
    
    for i in range(max_iterations):
        logger.info(f"--- Iteration {i+1} ---")
        logger.info(f"Taxi state: pos={taxi.position}, available={taxi.is_available}, cycle_mode={taxi.cycle_mode}, pickup_target={taxi.pickup_target}")
        
        # Force constraint programming check by bypassing time limit
        taxi.last_cp_check = 0  # Force check
        taxi._check_for_pickup_opportunities()
        
        logger.info(f"After CP check: cycle_mode={taxi.cycle_mode}, pickup_target={taxi.pickup_target}")
        
        if not taxi.cycle_mode and taxi.pickup_target:
            logger.info(f"✅ SUCCESS! Taxi deviated from cycle!")
            logger.info(f"   Target: {taxi.pickup_target.client_id}")
            logger.info(f"   Going to: {taxi.target_position}")
            return True
            
        time.sleep(0.5)
    
    logger.error("❌ FAILED: Taxi did not deviate from cycle")
    return False

if __name__ == "__main__":
    success = test_constraint_programming_debug()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
