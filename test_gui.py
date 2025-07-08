#!/usr/bin/env python3
"""
Prueba rápida de la GUI sin dependencias externas
"""

import sys
import os

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_gui_import():
    """Prueba que la GUI se puede importar y crear"""
    print("🧪 Probando import de GUI...")
    
    try:
        from taxi_dispatch_gui import GridTaxiGUI, launch_taxi_gui
        print("✅ Import de GUI exitoso")
        
        # Verificar que la clase tiene el método run
        gui = GridTaxiGUI()
        if hasattr(gui, 'run'):
            print("✅ Método run() existe")
        else:
            print("❌ Método run() no existe")
            return False
            
        # No ejecutar la GUI, solo verificar que se puede crear
        print("✅ GUI se puede crear correctamente")
        
        # Limpiar
        gui.root.destroy()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Prueba Rápida de GUI")
    print("=" * 30)
    
    success = test_gui_import()
    
    print("\n" + "=" * 30)
    if success:
        print("🎉 ¡GUI funcionando correctamente!")
        print("\n💡 Para ejecutar el sistema completo:")
        print("   cd src && python main.py")
    else:
        print("⚠️  Hay problemas con la GUI.")
