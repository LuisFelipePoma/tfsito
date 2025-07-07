#!/usr/bin/env python3
"""
Test específico para verificar que los taxis NO van a las esquinas
"""

import sys
import os
import time
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.taxi_tkinter_gui import TaxiTkinterGUI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_taxis_stay_central():
    """Test que verifica que los taxis se mantienen en el área central del mapa"""
    logger.info("🧪 Iniciando test de área central...")
    
    # Crear GUI
    gui = TaxiTkinterGUI(1200, 800)
    
    # Agregar taxis en posiciones centrales
    gui.add_taxi("central_taxi_1", (0, 0))
    gui.add_taxi("central_taxi_2", (10, -10))
    gui.add_taxi("central_taxi_3", (-15, 5))
    
    logger.info("🔄 Simulando 15 ciclos de movimiento...")
    
    corner_violations = 0
    total_positions = 0
    position_history = {}
    
    for cycle in range(15):
        gui.update()
        
        for taxi_id, taxi in gui.taxis.items():
            x, y = taxi.position
            total_positions += 1
            
            if taxi_id not in position_history:
                position_history[taxi_id] = []
            position_history[taxi_id].append((x, y))
            
            # Verificar si está muy cerca de las esquinas (área peligrosa)
            corner_distance_threshold = 35.0  # Si está a menos de 35 del borde, es área peligrosa
            
            if (abs(x) > corner_distance_threshold or abs(y) > corner_distance_threshold):
                corner_violations += 1
                logger.warning(f"⚠️  {taxi_id} muy cerca del borde: ({x:.1f}, {y:.1f})")
        
        time.sleep(0.3)
    
    # Análisis de resultados
    logger.info("📊 Análisis de posiciones:")
    for taxi_id, positions in position_history.items():
        logger.info(f"   {taxi_id}: {len(positions)} posiciones registradas")
        
        if positions:
            # Calcular estadísticas
            x_coords = [p[0] for p in positions]
            y_coords = [p[1] for p in positions]
            
            max_x = max(abs(x) for x in x_coords)
            max_y = max(abs(y) for y in y_coords)
            
            logger.info(f"      Máximo |x|: {max_x:.1f}, Máximo |y|: {max_y:.1f}")
            
            # Verificar algunas posiciones
            recent_positions = positions[-3:]
            for i, (x, y) in enumerate(recent_positions):
                logger.info(f"      Posición {len(positions)-3+i}: ({x:.1f}, {y:.1f})")
    
    violation_rate = corner_violations / total_positions if total_positions > 0 else 0
    
    logger.info(f"📈 Violaciones de esquina: {corner_violations}/{total_positions} ({violation_rate*100:.1f}%)")
    
    if violation_rate < 0.1:  # Menos del 10% en área peligrosa
        logger.info("✅ TEST PASÓ: Los taxis se mantienen en área central")
        return True
    else:
        logger.warning("❌ TEST FALLÓ: Demasiadas incursiones en las esquinas")
        return False

def test_movement_smoothness():
    """Test que verifica que el movimiento es suave y no demasiado brusco"""
    logger.info("🧪 Iniciando test de suavidad de movimiento...")
    
    gui = TaxiTkinterGUI(1200, 800)
    gui.add_taxi("smooth_taxi", (0, 0))
    
    positions = []
    
    for cycle in range(10):
        gui.update()
        taxi = gui.taxis["smooth_taxi"]
        positions.append(taxi.position)
        time.sleep(0.2)
    
    # Analizar distancias entre movimientos consecutivos
    distances = []
    for i in range(1, len(positions)):
        prev_x, prev_y = positions[i-1]
        curr_x, curr_y = positions[i]
        distance = ((curr_x - prev_x)**2 + (curr_y - prev_y)**2)**0.5
        distances.append(distance)
        logger.info(f"   Movimiento {i}: {distance:.2f} unidades")
    
    if distances:
        avg_distance = sum(distances) / len(distances)
        max_distance = max(distances)
        
        logger.info(f"📊 Distancia promedio: {avg_distance:.2f}")
        logger.info(f"📊 Distancia máxima: {max_distance:.2f}")
        
        # Criterios para movimiento suave
        if avg_distance < 20.0 and max_distance < 40.0:
            logger.info("✅ TEST PASÓ: Movimiento suave y controlado")
            return True
        else:
            logger.warning("❌ TEST FALLÓ: Movimiento demasiado brusco")
            return False
    
    return False

if __name__ == "__main__":
    logger.info("🚀 INICIANDO TESTS DE CALIDAD DE MOVIMIENTO")
    logger.info("="*70)
    
    success = True
    
    try:
        # Test 1: Mantener área central
        if not test_taxis_stay_central():
            success = False
        
        logger.info("\n" + "="*70)
        
        # Test 2: Suavidad de movimiento
        if not test_movement_smoothness():
            success = False
            
    except Exception as e:
        logger.error(f"❌ Error durante tests: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    logger.info("\n" + "="*70)
    if success:
        logger.info("🎉 TODOS LOS TESTS DE CALIDAD PASARON")
    else:
        logger.error("❌ ALGUNOS TESTS DE CALIDAD FALLARON")
    
    logger.info("="*70)
