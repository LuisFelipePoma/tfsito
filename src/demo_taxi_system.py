#!/usr/bin/env python3
"""
Demostración del Sistema de Despacho de Taxis Distribuido
=========================================================

Ejecuta una simulación de consola del sistema de taxis para mostrar:
- Constraint programming en acción
- Asignaciones óptimas de taxi-pasajero
- Movimiento y entrega de pasajeros
- Estadísticas en tiempo real

Ejecutar: python demo_taxi_system.py
"""

import sys
import os
import time
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distributed_taxi_system import DistributedTaxiSystem, TaxiState, PassengerState

def print_header():
    """Imprime el header de la demostración"""
    print("🚕" * 20)
    print("   SISTEMA DE DESPACHO DE TAXIS DISTRIBUIDO")
    print("   Demostración de Constraint Programming")
    print("🚕" * 20)
    print()

def print_system_state(system, step):
    """Imprime el estado actual del sistema"""
    print(f"\n📊 ESTADO DEL SISTEMA - Paso {step}")
    print("=" * 50)
    
    # Estado de taxis
    print("🚖 TAXIS:")
    for taxi_id, taxi in system.taxis.items():
        state_emoji = {
            TaxiState.IDLE: "🟢",
            TaxiState.PICKUP: "🟡", 
            TaxiState.DROPOFF: "🟠"
        }
        emoji = state_emoji[taxi.info.state]
        pos = f"({taxi.info.position.x}, {taxi.info.position.y})"
        
        if taxi.info.assigned_passenger_id:
            print(f"  {emoji} {taxi_id} en {pos} - {taxi.info.state.value} - Pasajero: {taxi.info.assigned_passenger_id}")
        else:
            print(f"  {emoji} {taxi_id} en {pos} - {taxi.info.state.value}")
    
    # Estado de pasajeros
    waiting_passengers = [p for p in system.passengers.values() if p.info.state == PassengerState.WAITING]
    picked_passengers = [p for p in system.passengers.values() if p.info.state == PassengerState.PICKED_UP]
    delivered_passengers = [p for p in system.passengers.values() if p.info.state == PassengerState.DELIVERED]
    
    print(f"\n👥 PASAJEROS:")
    print(f"  🔴 Esperando: {len(waiting_passengers)}")
    print(f"  🟣 En taxi: {len(picked_passengers)}")
    print(f"  ✅ Entregados: {len(delivered_passengers)}")
    
    if waiting_passengers:
        print("  📍 Pasajeros esperando:")
        for p in waiting_passengers[:3]:  # Mostrar solo los primeros 3
            pickup = f"({p.info.pickup_position.x}, {p.info.pickup_position.y})"
            dropoff = f"({p.info.dropoff_position.x}, {p.info.dropoff_position.y})"
            wait_time = int(p.info.wait_time)
            print(f"    • {p.info.passenger_id}: {pickup} → {dropoff} (esperando {wait_time}s)")

def simulate_step(system, step):
    """Simula un paso del sistema"""
    print(f"\n⏰ Ejecutando paso {step}...")
    
    # Actualizar sistema
    system.update(1.0)  # 1 segundo por paso
    
    # Imprimir estado
    print_system_state(system, step)
    
    # Estadísticas
    total_passengers = len(system.passengers)
    delivered = len([p for p in system.passengers.values() if p.info.state == PassengerState.DELIVERED])
    active_assignments = len([t for t in system.taxis.values() if t.info.state != TaxiState.IDLE])
    
    print(f"\n📈 ESTADÍSTICAS:")
    print(f"  • Total pasajeros: {total_passengers}")
    print(f"  • Entregados: {delivered}")
    print(f"  • Asignaciones activas: {active_assignments}")
    print(f"  • Eficiencia: {(delivered/total_passengers*100):.1f}%" if total_passengers > 0 else "  • Eficiencia: N/A")

def main():
    """Función principal de la demostración"""
    print_header()
    
    # Crear sistema
    print("🔧 Inicializando sistema...")
    system = DistributedTaxiSystem()
    system.start()
    
    print("✅ Sistema inicializado")
    print(f"📍 Mapa: {system.grid.width}x{system.grid.height}")
    print(f"🚖 Taxis: {len(system.taxis)}")
    print(f"👥 Pasajeros iniciales: {len(system.passengers)}")
    
    try:
        # Simulación por pasos
        for step in range(1, 21):  # 20 pasos
            simulate_step(system, step)
            
            # Pausa para leer
            if step % 5 == 0:
                print(f"\n⏸️ Pausa (presiona Enter para continuar...)")
                input()
            else:
                time.sleep(2)  # 2 segundos entre pasos
        
        # Resumen final
        print("\n" + "🎉" * 20)
        print("   SIMULACIÓN COMPLETADA")
        print("🎉" * 20)
        
        delivered = len([p for p in system.passengers.values() if p.info.state == PassengerState.DELIVERED])
        total = len(system.passengers)
        
        print(f"\n📊 RESUMEN FINAL:")
        print(f"  • Total pasajeros procesados: {total}")
        print(f"  • Pasajeros entregados: {delivered}")
        print(f"  • Tasa de éxito: {(delivered/total*100):.1f}%")
        print(f"  • Promedio por paso: {total/20:.1f} pasajeros")
        
        print(f"\n💡 El sistema utilizó:")
        print(f"  • Constraint programming: {'OR-Tools' if hasattr(system.solver, '_solve_with_ortools') else 'Algoritmo greedy'}")
        print(f"  • Comunicación distribuida: {'SPADE habilitado' if system.communication else 'Modo local'}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Simulación interrumpida por el usuario")
    finally:
        system.stop()
        print("\n👋 ¡Gracias por usar el sistema de despacho de taxis!")

if __name__ == "__main__":
    main()
