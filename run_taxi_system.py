#!/usr/bin/env python3
"""
Script de inicio para el Sistema de Taxis con Constraint Programming
===================================================================

Este script inicia el sistema completo de taxis con SPADE/OpenFire.
"""

import sys
import os
import subprocess
import time

def check_dependencies():
    """Verifica las dependencias necesarias"""
    try:
        import spade
        import ortools
        import tkinter
        print("✅ Todas las dependencias están disponibles")
        return True
    except ImportError as e:
        print(f"❌ Dependencia faltante: {e}")
        print("💡 Instala las dependencias con: pip install -r requirements.txt")
        return False

def check_openfire():
    """Verifica si OpenFire está corriendo"""
    try:
        import requests
        response = requests.get("http://localhost:9090", timeout=5)
        if response.status_code == 200:
            print("✅ OpenFire está corriendo")
            return True
        else:
            print("❌ OpenFire no responde correctamente")
            return False
    except Exception:
        print("❌ OpenFire no está disponible")
        print("💡 Inicia OpenFire con: docker run -d -p 9090:9090 -p 5222:5222 --name openfire gizmotronic/openfire")
        return False

def main():
    """Función principal"""
    print("🚕 Iniciando Sistema de Taxis con Constraint Programming")
    print("=" * 60)
    
    # Verificar dependencias
    if not check_dependencies():
        return 1
    
    # Verificar OpenFire
    if not check_openfire():
        print("\n⚠️  OpenFire no está disponible. El sistema puede no funcionar correctamente.")
        response = input("¿Deseas continuar de todas formas? (s/N): ")
        if response.lower() != 's':
            return 1
    
    # Cambiar al directorio src
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    os.chdir(src_dir)
    
    print(f"\n🔄 Iniciando desde directorio: {src_dir}")
    print("🎯 Ejecutando sistema principal...")
    
    try:
        # Ejecutar el sistema principal
        result = subprocess.run([sys.executable, "main.py"], check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar el sistema: {e}")
        return e.returncode
    except KeyboardInterrupt:
        print("\n🛑 Sistema interrumpido por el usuario")
        return 0

if __name__ == "__main__":
    sys.exit(main())
