#!/usr/bin/env python3
"""
Prueba Rápida del Sistema de Taxis
==================================

Verifica que el sistema inicie correctamente sin errores de bucle de eventos
en modo no interactivo.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distributed_taxi_system import DistributedTaxiSystem

def test_system_startup():
    """Prueba que el sistema se inicie sin errores"""
    print("🔍 Probando inicio del sistema...")
    
    try:
        # Crear sistema
        system = DistributedTaxiSystem()
        print("✅ Sistema creado correctamente")
        
        # Iniciar sistema (esto debe funcionar sin errores de bucle de eventos)
        system.start()
        print("✅ Sistema iniciado correctamente")
        
        # Verificar que tiene taxis y pasajeros
        assert len(system.taxis) > 0, "Debe tener taxis"
        assert len(system.passengers) > 0, "Debe tener pasajeros"
        print(f"✅ Sistema tiene {len(system.taxis)} taxis y {len(system.passengers)} pasajeros")
        
        # Probar una asignación
        taxi_infos = [taxi.info for taxi in system.taxis.values()]
        passenger_infos = [passenger.info for passenger in system.passengers.values()]
        assignments = system.solver.solve_assignment(taxi_infos, passenger_infos)
        print(f"✅ Asignaciones generadas: {len(assignments)}")
        
        # Detener sistema
        system.stop()
        print("✅ Sistema detenido correctamente")
        
        print("\n🎉 ¡Prueba exitosa! El sistema funciona sin errores de bucle de eventos.")
        return True
        
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚕 Prueba Rápida del Sistema de Taxis")
    print("=====================================")
    
    success = test_system_startup()
    
    if success:
        print("\n✅ TODAS LAS PRUEBAS PASARON")
        print("💡 El sistema está listo para:")
        print("  • Ejecutar demo: python demo_taxi_system.py")
        print("  • Ejecutar GUI: python distributed_taxi_system.py")
        print("  • Ejecutar tests: python test_taxi_system.py")
    else:
        print("\n❌ ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisar los logs para más detalles")
        sys.exit(1)
