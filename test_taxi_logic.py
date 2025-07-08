#!/usr/bin/env python3
"""
Prueba simple de la lógica del sistema de taxis
================================================

Prueba básica para verificar que el constraint programming funciona correctamente.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.taxi_dispatch_system import (
    GridNetwork, GridPosition, TaxiInfo, PassengerInfo, 
    TaxiState, PassengerState, ConstraintSolver
)
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def test_constraint_solver():
    """Prueba básica del constraint solver"""
    print("🧪 Probando Constraint Solver...")
    
    # Crear grid
    grid = GridNetwork(10, 10)
    
    # Crear taxis
    taxis = [
        TaxiInfo(
            taxi_id="taxi_0",
            position=GridPosition(0, 0),
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            speed=1.0
        ),
        TaxiInfo(
            taxi_id="taxi_1",
            position=GridPosition(5, 5),
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            speed=1.0
        ),
        TaxiInfo(
            taxi_id="taxi_2",
            position=GridPosition(9, 9),
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            speed=1.0
        )
    ]
    
    # Crear pasajeros
    passengers = [
        PassengerInfo(
            passenger_id="P1",
            pickup_position=GridPosition(1, 1),
            dropoff_position=GridPosition(8, 8),
            state=PassengerState.WAITING,
            wait_time=0.0,
            is_disabled=True,  # Prioridad alta
            is_elderly=False,
            is_child=False,
            is_pregnant=False,
            price=15.0
        ),
        PassengerInfo(
            passenger_id="P2",
            pickup_position=GridPosition(3, 3),
            dropoff_position=GridPosition(7, 7),
            state=PassengerState.WAITING,
            wait_time=5.0,  # Más tiempo esperando
            is_disabled=False,
            is_elderly=True,  # Prioridad media
            is_child=False,
            is_pregnant=False,
            price=12.0
        ),
        PassengerInfo(
            passenger_id="P3",
            pickup_position=GridPosition(6, 6),
            dropoff_position=GridPosition(2, 2),
            state=PassengerState.WAITING,
            wait_time=2.0,
            is_disabled=False,
            is_elderly=False,
            is_child=False,
            is_pregnant=False,
            price=20.0  # Precio alto
        )
    ]
    
    # Probar solver
    solver = ConstraintSolver()
    
    print("\n📊 Estado inicial:")
    print("Taxis:")
    for taxi in taxis:
        print(f"  {taxi.taxi_id}: pos({taxi.position.x}, {taxi.position.y}), estado: {taxi.state.value}")
    
    print("\nPasajeros:")
    for passenger in passengers:
        priorities = []
        if passenger.is_disabled: priorities.append("DISABLED")
        if passenger.is_elderly: priorities.append("ELDERLY")
        if passenger.is_child: priorities.append("CHILD")
        if passenger.is_pregnant: priorities.append("PREGNANT")
        priority_str = f" [{', '.join(priorities)}]" if priorities else ""
        
        print(f"  {passenger.passenger_id}{priority_str}: pos({passenger.pickup_position.x}, {passenger.pickup_position.y}) -> ({passenger.dropoff_position.x}, {passenger.dropoff_position.y}), precio: S/{passenger.price:.2f}, espera: {passenger.wait_time:.1f}s")
    
    # Resolver asignaciones
    assignments = solver.solve_assignment(taxis, passengers)
    
    print(f"\n✅ Asignaciones resueltas: {len(assignments)}")
    for taxi_id, passenger_id in assignments.items():
        passenger = next(p for p in passengers if p.passenger_id == passenger_id)
        taxi = next(t for t in taxis if t.taxi_id == taxi_id)
        distance = taxi.position.manhattan_distance(passenger.pickup_position)
        print(f"  {taxi_id} -> {passenger_id} (distancia: {distance}, precio: S/{passenger.price:.2f})")
    
    return len(assignments) > 0

def test_grid_pathfinding():
    """Prueba el pathfinding del grid"""
    print("\n🗺️ Probando Grid Pathfinding...")
    
    grid = GridNetwork(5, 5)
    
    start = GridPosition(0, 0)
    end = GridPosition(4, 4)
    
    path = grid.get_path(start, end)
    
    print(f"Ruta de ({start.x}, {start.y}) a ({end.x}, {end.y}):")
    for i, pos in enumerate(path):
        print(f"  {i}: ({pos.x}, {pos.y})")
    
    # Verificar que la ruta es correcta
    expected_length = abs(end.x - start.x) + abs(end.y - start.y) + 1
    print(f"Longitud esperada: {expected_length}, longitud actual: {len(path)}")
    
    return len(path) == expected_length

def main():
    """Función principal de prueba"""
    print("🚕 Sistema de Taxis - Pruebas de Lógica")
    print("=" * 50)
    
    try:
        # Prueba 1: Grid pathfinding
        test1_passed = test_grid_pathfinding()
        
        # Prueba 2: Constraint solver
        test2_passed = test_constraint_solver()
        
        print("\n" + "=" * 50)
        print("📋 Resumen de Pruebas:")
        print(f"  Grid Pathfinding: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        print(f"  Constraint Solver: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        
        if test1_passed and test2_passed:
            print("\n🎉 ¡Todas las pruebas pasaron!")
            print("La lógica básica del sistema funciona correctamente.")
            return 0
        else:
            print("\n⚠️ Algunas pruebas fallaron.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
