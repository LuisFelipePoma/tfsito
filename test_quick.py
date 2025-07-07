#!/usr/bin/env python3
"""
Test rápido de movimiento central
"""

import sys
import os
import time
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.taxi_tkinter_gui import TaxiTkinterGUI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def quick_test():
    """Test rápido que verifica las mejoras"""
    logger.info("🧪 Test rápido de movimiento...")
    
    gui = TaxiTkinterGUI(1200, 800)
    gui.add_taxi("test_taxi", (0, 0))
    
    positions = []
    
    # Solo 8 ciclos para test con más tiempo
    for cycle in range(8):
        gui.update()
        taxi = gui.taxis["test_taxi"]
        positions.append(taxi.position)
        logger.info(f"   Ciclo {cycle+1}: Posición {taxi.position}")
        time.sleep(0.15)  # Un poco más de tiempo
    
    # Verificar que se movió
    first_pos = positions[0]
    last_pos = positions[-1]
    distance = ((last_pos[0] - first_pos[0])**2 + (last_pos[1] - first_pos[1])**2)**0.5
    
    logger.info(f"📊 Movimiento total: {distance:.2f} unidades")
    logger.info(f"📊 Posición final: {last_pos}")
    
    # Verificar que no está en esquinas
    max_coord = max(abs(last_pos[0]), abs(last_pos[1]))
    
    if distance > 1.0:
        logger.info("✅ El taxi se está moviendo")
        if max_coord < 35:
            logger.info("✅ El taxi se mantiene en área central")
            return True
        else:
            logger.warning("⚠️ El taxi se acercó demasiado al borde")
    else:
        logger.warning("❌ El taxi no se movió suficiente")
    
    return False

if __name__ == "__main__":
    if quick_test():
        logger.info("🎉 TEST RÁPIDO PASÓ")
    else:
        logger.error("❌ TEST RÁPIDO FALLÓ")
