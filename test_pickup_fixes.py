#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rápido para validar que las correcciones de recogida de pasajeros funcionen
"""

import sys
import os
import logging

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_taxi_pickup_flow():
    """Test rápido del flujo de recogida y transporte"""
    
    logger.info("🧪 INICIANDO TEST DE FLUJO DE RECOGIDA")
    logger.info("=" * 60)
    
    try:
        from src.gui.taxi_tkinter_gui import TaxiTkinterGUI, set_gui
        from src.agent.libs.taxi_constraints import find_best_taxi_for_client
        
        # Crear GUI sin mostrarla
        gui = TaxiTkinterGUI(width=800, height=600)
        set_gui(gui)
        
        # Agregar un taxi
        taxi_id = "test_taxi"
        taxi_pos = (0, 0)
        gui.add_taxi(taxi_id, taxi_pos, 4)
        logger.info(f"✅ Taxi agregado: {taxi_id} en posición {taxi_pos}")
        
        # Agregar un cliente
        client_id = "test_client"
        client_pos = (10, 10)
        gui.add_client(client_id, client_pos, 2, False)
        logger.info(f"✅ Cliente agregado: {client_id} en posición {client_pos}")
        
        # Verificar estados iniciales
        taxi = gui.taxis[taxi_id]
        client = gui.clients[client_id]
        
        logger.info(f"📊 Estado inicial del taxi:")
        logger.info(f"   - Disponible: {taxi.is_available}")
        logger.info(f"   - Pasajeros: {taxi.current_passengers}")
        logger.info(f"   - Objetivo pickup: {taxi.pickup_target}")
        logger.info(f"   - Moviendose: {taxi.is_moving}")
        
        # Test de asignación usando constraints
        taxis_data = [{
            'id': taxi_id,
            'position': taxi_pos,
            'capacity': 4,
            'current_passengers': 0,
            'is_available': True
        }]
        
        client_info = {
            'position': client_pos,
            'passengers': 2,
            'disabled': False,
            'waiting_time': 0.0,
            'range_multiplier': 1.0
        }
        
        best_taxi = find_best_taxi_for_client(client_info, taxis_data)
        logger.info(f"🎯 Mejor taxi encontrado: {best_taxi}")
        
        if best_taxi:
            # Asignar taxi al cliente
            gui.assign_taxi_to_client(best_taxi, client_id)
            logger.info(f"✅ Taxi {best_taxi} asignado al cliente {client_id}")
            
            # Verificar estado después de asignación
            logger.info(f"📊 Estado después de asignación:")
            logger.info(f"   - Taxi disponible: {taxi.is_available}")
            logger.info(f"   - Taxi pickup_target: {taxi.pickup_target is not None}")
            logger.info(f"   - Cliente asignado a taxi: {client.assigned_taxi}")
            logger.info(f"   - Taxi moviendose: {taxi.is_moving}")
            logger.info(f"   - Destino del cliente: {client.destination}")
            
            if (not taxi.is_available and 
                taxi.pickup_target is not None and 
                client.assigned_taxi == taxi_id):
                logger.info("✅ ASIGNACIÓN CORRECTA")
                return True
            else:
                logger.error("❌ ASIGNACIÓN INCORRECTA")
                return False
        else:
            logger.error("❌ No se encontró taxi disponible")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Test de Correcciones de Recogida de Pasajeros")
    print("=" * 50)
    
    success = test_taxi_pickup_flow()
    
    if success:
        print("\n✅ TEST EXITOSO - Las correcciones parecen funcionar")
        print("💡 Puedes ejecutar la demo completa con: python demo_taxi_dispatch.py")
    else:
        print("\n❌ TEST FALLIDO - Revisar correcciones")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
