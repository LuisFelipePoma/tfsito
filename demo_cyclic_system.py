#!/usr/bin/env python3
"""
Demo del Sistema de Movimiento Cíclico con Constraint Programming
================================================================

Este demo muestra el nuevo sistema implementado donde:
1. Los taxis siguen rutas cíclicas predefinidas (dan vueltas por el mapa)
2. Usan constraint programming (OR-Tools) para decidir cuándo desviarse
3. Solo se mueven en direcciones cardinales (arriba, derecha, abajo, izquierda)
4. Vuelven a su ciclo después de completar una misión

Patrones de Ciclo:
- Taxi 0: Rectángulo perimetral (horario)
- Taxi 1: Rectángulo interno (antihorario)  
- Taxi 2: Patrón de cruz
- Taxi 3: Patrón de figura-8

¡Observa cómo los taxis se desvían cuando encuentran un cliente adecuado!
"""

import sys
import os
import time
import logging
import threading

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from gui.taxi_tkinter_gui import TaxiTkinterGUI, set_gui
import random

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_clients_periodically(gui):
    """Generar clientes periódicamente para demonstrar el sistema"""
    
    def client_generator():
        while gui.running:
            try:
                # Generar cliente cada 8-15 segundos
                time.sleep(random.uniform(8.0, 15.0))
                
                if not gui.running:
                    break
                
                # Generar cliente con datos aleatorios
                client_id = f"demo_client_{int(time.time() * 1000)}"
                position = gui.generate_random_grid_position()
                n_passengers = random.randint(1, 4)
                is_disabled = random.random() < 0.2  # 20% probabilidad de ser discapacitado
                
                gui.add_client(client_id, position, n_passengers, is_disabled)
                
                client_type = "DISCAPACITADO" if is_disabled else "REGULAR"
                logger.info(f"🆕 Cliente generado: {client_id} en {position} ({n_passengers} pasajeros, {client_type})")
                
            except Exception as e:
                logger.error(f"Error generando cliente: {e}")
                break
    
    # Ejecutar generador en hilo separado
    generator_thread = threading.Thread(target=client_generator, daemon=True)
    generator_thread.start()
    return generator_thread

def main():
    """Función principal del demo"""
    print(__doc__)
    print("🚀 Iniciando demo del Sistema de Movimiento Cíclico...")
    print("📍 Los taxis comenzarán a patrullar en sus rutas cíclicas")
    print("🤖 El constraint programming decidirá cuándo recoger clientes")
    print("⏹️  Presiona Ctrl+C o cierra la ventana para salir")
    print("-" * 60)
    
    # Crear GUI
    gui = TaxiTkinterGUI(1400, 900)
    set_gui(gui)
    
    # Agregar taxis con diferentes patrones de ciclo
    logger.info("🚕 Agregando taxis con patrones cíclicos...")
    gui.add_taxi("taxi_0", (-15, -15), 4)  # Patrón rectangular perimetral
    gui.add_taxi("taxi_1", (15, 15), 4)    # Patrón rectangular interno
    gui.add_taxi("taxi_2", (0, 0), 4)      # Patrón de cruz
    gui.add_taxi("taxi_3", (25, -25), 4)   # Patrón figura-8
    
    # Agregar algunos clientes iniciales
    logger.info("👥 Agregando clientes iniciales...")
    gui.add_client("client_1", (-35, 25), 2, False)  # Cliente regular
    gui.add_client("client_2", (30, -35), 1, True)   # Cliente discapacitado
    gui.add_client("client_3", (15, 35), 3, False)   # Cliente regular
    
    # Iniciar generador de clientes automático
    logger.info("🔄 Iniciando generador automático de clientes...")
    client_thread = generate_clients_periodically(gui)
    
    try:
        # Iniciar GUI (esto bloquea hasta que se cierre la ventana)
        logger.info("🖥️  Iniciando interfaz gráfica...")
        gui.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 Demo interrumpido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error en el demo: {e}")
    finally:
        logger.info("🏁 Cerrando demo...")
        gui.stop()

if __name__ == "__main__":
    main()
