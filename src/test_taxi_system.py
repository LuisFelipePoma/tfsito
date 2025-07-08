#!/usr/bin/env python3
"""
Test básico del sistema de despacho de taxis distribuido
Verifica que todos los componentes funcionen correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Prueba que todas las importaciones funcionen"""
    print("🔍 Probando importaciones...")
    
    try:
        from distributed_taxi_system import (
            GridPosition, TaxiInfo, PassengerInfo,
            GridNetwork, ConstraintSolver, GridTaxi, GridPassenger,
            DistributedTaxiSystem, TaxiSystemGUI
        )
        print("✅ Todas las importaciones exitosas")
        return True
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False

def test_grid_network():
    """Prueba la red de grilla"""
    print("🔍 Probando GridNetwork...")
    
    try:
        from distributed_taxi_system import GridNetwork, GridPosition
        
        grid = GridNetwork(10, 10)
        assert len(grid.intersections) == 100
        
        pos1 = GridPosition(0, 0)
        pos2 = GridPosition(3, 4)
        assert pos1.manhattan_distance(pos2) == 7
        
        path = grid.get_path(pos1, pos2)
        assert len(path) >= 2
        assert path[0] == pos1
        assert path[-1] == pos2
        
        print("✅ GridNetwork funciona correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en GridNetwork: {e}")
        return False

def test_constraint_solver():
    """Prueba el solver de restricciones"""
    print("🔍 Probando ConstraintSolver...")
    
    try:
        from distributed_taxi_system import ConstraintSolver, TaxiInfo, PassengerInfo, GridPosition, TaxiState, PassengerState
        
        solver = ConstraintSolver()
        
        # Crear datos de prueba
        taxi = TaxiInfo(
            taxi_id="test_taxi",
            position=GridPosition(0, 0),
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None,
            last_update=0.0
        )
        
        passenger = PassengerInfo(
            passenger_id="test_passenger",
            pickup_position=GridPosition(2, 2),
            dropoff_position=GridPosition(5, 5),
            state=PassengerState.WAITING,
            wait_time=10.0
        )
        
        assignments = solver.solve_assignment([taxi], [passenger])
        print(f"✅ ConstraintSolver genera asignaciones: {assignments}")
        return True
    except Exception as e:
        print(f"❌ Error en ConstraintSolver: {e}")
        return False

def test_taxi_entity():
    """Prueba la entidad taxi"""
    print("🔍 Probando GridTaxi...")
    
    try:
        from distributed_taxi_system import GridTaxi, GridNetwork, GridPosition
        
        grid = GridNetwork(10, 10)
        taxi = GridTaxi("test_taxi", GridPosition(5, 5), grid)
        
        # Probar actualización
        result = taxi.update(0.1)
        assert taxi.info.position.x >= 0 and taxi.info.position.x < 10
        assert taxi.info.position.y >= 0 and taxi.info.position.y < 10
        
        print("✅ GridTaxi funciona correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en GridTaxi: {e}")
        return False

def test_system():
    """Prueba el sistema principal"""
    print("🔍 Probando DistributedTaxiSystem...")
    
    try:
        from distributed_taxi_system import DistributedTaxiSystem
        
        system = DistributedTaxiSystem()
        assert len(system.taxis) == 3  # 3 taxis por defecto
        assert len(system.passengers) == 4  # 4 pasajeros iniciales
        
        # Probar actualización
        system.update(0.1)
        
        # Probar agregar pasajero
        initial_count = len(system.passengers)
        system.add_random_passenger()
        assert len(system.passengers) == initial_count + 1
        
        print("✅ DistributedTaxiSystem funciona correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en DistributedTaxiSystem: {e}")
        return False

def main():
    """Ejecuta todas las pruebas"""
    print("🚕 Test del Sistema de Despacho de Taxis Distribuido")
    print("=" * 55)
    
    tests = [
        test_imports,
        test_grid_network,
        test_constraint_solver,
        test_taxi_entity,
        test_system
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron! El sistema está listo para usar.")
        print("📝 Para iniciar: python distributed_taxi_system.py")
    else:
        print("⚠️ Algunos tests fallaron. Revisar los errores arriba.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
