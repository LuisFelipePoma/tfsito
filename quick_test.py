#!/usr/bin/env python3
"""
Prueba rápida del constraint solver
"""

import sys
import os

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_logic():
    """Prueba básica sin dependencias externas"""
    print("🧪 Probando lógica básica...")
    
    try:
        # Importar clases básicas
        from taxi_dispatch_system import (
            GridNetwork, GridPosition, TaxiInfo, PassengerInfo, 
            TaxiState, PassengerState
        )
        
        print("✅ Imports básicos funcionan")
        
        # Crear grid
        grid = GridNetwork(5, 5)
        print(f"✅ Grid creado: {grid.width}x{grid.height}")
        
        # Probar pathfinding
        start = GridPosition(0, 0)
        end = GridPosition(2, 2)
        path = grid.get_path(start, end)
        print(f"✅ Pathfinding: ruta de {len(path)} pasos")
        
        # Crear taxi
        taxi = TaxiInfo(
            taxi_id="test_taxi",
            position=GridPosition(1, 1),
            target_position=None,
            state=TaxiState.IDLE,
            capacity=4,
            current_passengers=0,
            assigned_passenger_id=None
        )
        print(f"✅ Taxi creado: {taxi.taxi_id} en estado {taxi.state.value}")
        
        # Crear pasajero
        passenger = PassengerInfo(
            passenger_id="test_passenger",
            pickup_position=GridPosition(2, 2),
            dropoff_position=GridPosition(4, 4),
            state=PassengerState.WAITING,
            wait_time=0.0,
            is_disabled=False,
            is_elderly=True,
            is_child=False,
            is_pregnant=False,
            price=15.0
        )
        print(f"✅ Pasajero creado: {passenger.passenger_id} esperando en ({passenger.pickup_position.x}, {passenger.pickup_position.y})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_constraint_solver():
    """Prueba el constraint solver si está disponible"""
    print("\n🔧 Probando constraint solver...")
    
    try:
        from taxi_dispatch_system import ConstraintSolver
        
        solver = ConstraintSolver()
        print("✅ ConstraintSolver creado")
        
        # Las pruebas más complejas requerirían OR-Tools
        print("ℹ️  Para pruebas completas instalar: conda install ortools")
        
        return True
        
    except Exception as e:
        print(f"❌ Error con constraint solver: {e}")
        return False

if __name__ == "__main__":
    print("🚕 Prueba Rápida del Sistema de Taxis")
    print("=" * 40)
    
    success1 = test_basic_logic()
    success2 = test_constraint_solver()
    
    print("\n" + "=" * 40)
    if success1 and success2:
        print("🎉 ¡Pruebas básicas exitosas!")
        print("La lógica fundamental funciona correctamente.")
    else:
        print("⚠️  Algunas pruebas fallaron.")
    
    print("\n💡 Para probar el sistema completo:")
    print("   1. Instala dependencias: conda install ortools spade-platform")
    print("   2. Ejecuta: python run_taxi_system.py")
