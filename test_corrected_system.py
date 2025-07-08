#!/usr/bin/env python3
"""
Test rápido del sistema corregido
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.taxi_dispatch_system import (
        TaxiAgent, CoordinatorAgent, GridNetwork, ConstraintSolver,
        TaxiState, PassengerState, GridPosition, TaxiInfo, PassengerInfo
    )
    from src.taxi_dispatch_gui import launch_taxi_gui
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def test_system():
    print("Testing corrected taxi dispatch system...")
    
    try:
        # Crear componentes básicos
        grid = GridNetwork()
        solver = ConstraintSolver()
        print("✓ Grid and solver created successfully")
        
        # Crear posiciones de prueba
        pos1 = GridPosition(5, 5)
        pos2 = GridPosition(10, 10)
        print(f"✓ Grid positions created: {pos1} -> {pos2}")
        
        # Crear información de taxi
        taxi_info = TaxiInfo(
            taxi_id="T001",
            position=pos1,
            state=TaxiState.IDLE,
            target_position=None,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            speed=1.0
        )
        print(f"✓ Taxi info created: {taxi_info.taxi_id} at {taxi_info.position}")
        
        # Crear información de pasajero
        passenger_info = PassengerInfo(
            passenger_id="P001",
            pickup_position=pos1,
            dropoff_position=pos2,
            state=PassengerState.WAITING,
            wait_time=0.0,
            is_disabled=False,
            is_elderly=False,
            is_child=False,
            is_pregnant=False,
            price=15.0
        )
        print(f"✓ Passenger info created: {passenger_info.passenger_id} from {passenger_info.pickup_position} to {passenger_info.dropoff_position}")
        
        # Verificar que solver puede resolver asignaciones
        assignments = solver.solve_assignment([taxi_info], [passenger_info])
        print(f"✓ Constraint solver working: {assignments}")
        
        print("✓ All components validated successfully")
        
        # Probar arranque de GUI
        print("Testing GUI launch...")
        launch_taxi_gui()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_system()
