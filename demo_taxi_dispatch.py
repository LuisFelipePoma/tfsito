# -*- coding: utf-8 -*-
"""
Demo principal del sistema de despacho de taxis con GUI Tkinter
"""

import logging
import time
import sys
import os
import threading
import random

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def taxi_dispatch_demo():
    """
    Demostración del sistema de despacho de taxis con GUI Tkinter
    """
    
    logger.info("Iniciando demostración del sistema de despacho de taxis...")
    
    try:
        # Importar y crear GUI de tkinter (debe ejecutarse en hilo principal)
        from src.gui.taxi_tkinter_gui import TaxiTkinterGUI, set_gui
        
        logger.info("Creando GUI Tkinter...")
        gui = TaxiTkinterGUI(width=1200, height=800)
        
        # Establecer la instancia global para acceso desde otros módulos
        set_gui(gui)
        
        # Agregar taxis iniciales
        taxi_data = [
            {"id": "taxi_01", "position": (-25, -20), "capacity": 4},
            {"id": "taxi_02", "position": (25, 20), "capacity": 4},
            {"id": "taxi_03", "position": (0, -35), "capacity": 6},
            {"id": "taxi_04", "position": (-35, 15), "capacity": 4},
            {"id": "taxi_05", "position": (30, -15), "capacity": 4},
        ]
        
        for taxi in taxi_data:
            gui.add_taxi(taxi["id"], taxi["position"], taxi["capacity"])
        
        logger.info("Taxis agregados a la GUI")
        
        # Agregar clientes iniciales
        initial_clients = [
            {"id": "client_01", "position": (-15, 10), "passengers": 2, "disabled": False},
            {"id": "client_02", "position": (18, -12), "passengers": 1, "disabled": True},
            {"id": "client_03", "position": (-28, 5), "passengers": 3, "disabled": False},
            {"id": "client_04", "position": (22, 25), "passengers": 1, "disabled": False},
        ]
        
        for client in initial_clients:
            gui.add_client(
                client["id"], 
                client["position"], 
                client["passengers"], 
                client["disabled"]
            )
        
        logger.info("Entidades agregadas. Iniciando simulaciones...")
        
        # Función para simular movimiento de taxis en hilo separado
        def simulate_taxi_movement():
            """Simular movimiento de taxis más lento y realista - SOLO para free roaming manual"""
            while gui.running:
                time.sleep(5.0)  # Movimiento cada 5 segundos (más espaciado)
                
                for taxi_info in taxi_data:
                    taxi_id = taxi_info["id"]
                    if taxi_id in gui.taxis:
                        taxi = gui.taxis[taxi_id]
                        
                        # SOLO mover taxis que están completamente libres (sin asignación ni pasajeros)
                        if (taxi.is_available and 
                            not taxi.is_moving and 
                            not taxi.pickup_target and 
                            taxi.current_passengers == 0):
                            
                            new_x = random.uniform(-35, 35)  # Área más pequeña
                            new_y = random.uniform(-35, 35)
                            new_position = (new_x, new_y)
                            
                            # Actualizar estado del taxi con movimiento más lento
                            gui.update_taxi_state(taxi_id, {
                                'position': new_position,
                                'current_passengers': taxi.current_passengers,
                                'is_available': taxi.is_available,
                                'fuel_level': max(0.1, taxi.fuel_level - random.uniform(0.002, 0.005))  # Menos consumo
                            })
                            logger.info(f"Taxi {taxi_id} free roaming to {new_position}")
        
        # Función para simular asignaciones automáticas
        def simulate_assignments():
            """Simular asignaciones de viajes usando constraints simplificadas"""
            time.sleep(5)  # Esperar más antes de empezar las asignaciones
            
            # Importar constraints para asignación inteligente
            from src.agent.libs.taxi_constraints import find_best_taxi_for_client
            
            while gui.running:
                time.sleep(random.uniform(10, 15))  # Asignaciones menos frecuentes (10-15 segundos)
                
                # Encontrar clientes y taxis disponibles con filtros estrictos
                available_clients = [c for c in gui.clients.values() if not c.assigned_taxi]
                available_taxis = [
                    t for t in gui.taxis.values() 
                    if (t.is_available and 
                        not t.is_moving and 
                        not t.pickup_target and 
                        t.current_passengers == 0)
                ]
                
                logger.info(f"Assignment check: {len(available_clients)} clients waiting, {len(available_taxis)} taxis truly available")
                
                # Log detailed status of all taxis for debugging
                for taxi in gui.taxis.values():
                    logger.debug(f"  Taxi {taxi.taxi_id}: available={taxi.is_available}, passengers={taxi.current_passengers}, pickup_target={taxi.pickup_target is not None}, moving={taxi.is_moving}")
                
                if available_clients and available_taxis:
                    # Priorizar clientes que han esperado más tiempo
                    available_clients.sort(key=lambda c: c.waiting_time, reverse=True)
                    client = available_clients[0]  # Cliente que más ha esperado
                    
                    # Convertir taxis a formato esperado por constraints
                    taxis_data = []
                    for taxi in available_taxis:
                        taxi_info = {
                            'id': taxi.taxi_id,
                            'position': taxi.position,
                            'capacity': taxi.max_capacity,
                            'current_passengers': taxi.current_passengers,
                            'is_available': taxi.is_available
                        }
                        taxis_data.append(taxi_info)
                    
                    # Convertir cliente a formato esperado con rango dinámico
                    client_info = {
                        'position': client.position,
                        'passengers': client.n_passengers,
                        'disabled': client.is_disabled,
                        'waiting_time': client.waiting_time,
                        'range_multiplier': client.range_multiplier
                    }
                    
                    # Encontrar el mejor taxi usando constraints con rango dinámico
                    best_taxi_id = find_best_taxi_for_client(client_info, taxis_data)
                    
                    if best_taxi_id:
                        gui.assign_taxi_to_client(best_taxi_id, client.client_id)
                        range_info = f"(rango: {client.range_multiplier:.1f}x, esperando: {client.waiting_time:.1f}s)"
                        logger.info(f"Asignado taxi {best_taxi_id} a cliente {client.client_id} {range_info}")
                        logger.info(f"   Destino del cliente: {client.destination}")
                    else:
                        logger.info(f"No se encontro taxi para cliente {client.client_id} (rango: {client.range_multiplier:.1f}x)")
                else:
                    if not available_clients:
                        logger.info("No hay clientes esperando asignacion")
                    if not available_taxis:
                        logger.info("No hay taxis completamente disponibles")
        
        # Iniciar simulaciones en hilos separados
        movement_thread = threading.Thread(target=simulate_taxi_movement, daemon=True)
        assignment_thread = threading.Thread(target=simulate_assignments, daemon=True)
        
        movement_thread.start()
        assignment_thread.start()
        
        logger.info("=== DEMO INICIADO ===")
        logger.info("Caracteristicas del sistema mejorado:")
        logger.info("- Los taxis se mueven mas lentamente para una simulacion realista")
        logger.info("- Los taxis recogen pasajeros y los transportan a sus destinos especificos")
        logger.info("- El proceso de recogida y transporte es visible y mas lento")
        logger.info("- Tras dejar pasajeros, los taxis vuelven al modo de busqueda libre")
        logger.info("- Se generan nuevos pasajeros automaticamente con destinos unicos")
        logger.info("- Haz clic en el canvas para agregar mas clientes manualmente")
        logger.info("- Cierra la ventana para terminar la simulacion")
        logger.info("")
        logger.info("Observa como los taxis:")
        logger.info("  1. Se mueven libremente (free roaming) cuando disponibles")
        logger.info("  2. Van a recoger al cliente asignado")
        logger.info("  3. Transportan al cliente a su destino especifico")
        logger.info("  4. Vuelven a estar disponibles tras dejar al pasajero")
        
        # Ejecutar GUI en hilo principal (esto bloquea hasta que se cierre la ventana)
        gui.run()
        
        logger.info("Demo terminado")
        
    except Exception as e:
        logger.error(f"Error en la demostración: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Función principal para ejecutar la demostración"""
    print("=== Sistema de Despacho de Taxis ===")
    print("Demostracion con GUI Tkinter - Simulacion Realista")
    print()
    print("Caracteristicas principales:")
    print("- Movimiento lento y realista de taxis con interpolacion suave")
    print("- Recogida real de pasajeros y transporte a destinos especificos") 
    print("- Proceso visible de: pickup -> transporte -> drop-off -> busqueda")
    print("- Generacion automatica de nuevos clientes con destinos unicos")
    print("- Interfaz interactiva (clic para agregar clientes)")
    print("- Monitoreo de rendimiento y estado en tiempo real")
    print("- Visualizacion completa: destinos, rutas, rangos de busqueda")
    print()
    
    try:
        # Ejecutar la demostración
        taxi_dispatch_demo()
        
    except KeyboardInterrupt:
        print("\nDemostración interrumpida por el usuario")
    except Exception as e:
        print(f"Error en la demostración: {e}")
        import traceback
        traceback.print_exc()
    
    print("Demostración finalizada")


if __name__ == "__main__":
    main()