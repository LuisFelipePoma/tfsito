
#!/usr/bin/env python3
"""
Sistema de Taxis con Constraint Programming y OpenFire/SPADE
============================================================

Punto de entrada principal del sistema de despacho de taxis.
"""

import sys
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    """Función principal del sistema"""
    print("🚕 Sistema de Taxis con Constraint Programming")
    print("=" * 50)
    
    try:
        from taxi_dispatch_gui import launch_taxi_gui
        print("✅ Módulos cargados correctamente")
        print("🔥 Iniciando sistema...")
        
        # Lanzar la interfaz gráfica
        launch_taxi_gui()
        
    except KeyboardInterrupt:
        print("\n🛑 Sistema interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error al iniciar el sistema: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
