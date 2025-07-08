#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prueba Simple del Sistema de Taxis Distribuido
==============================================

Verifica que el sistema esté funcionando correctamente.
"""

import subprocess
import time
import requests
import os
import sys
from pathlib import Path

def print_header(title):
    """Imprime un header decorado"""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def print_success(message):
    """Imprime un mensaje de éxito"""
    print(f"[OK] {message}")

def print_error(message):
    """Imprime un mensaje de error"""
    print(f"[ERROR] {message}")

def print_warning(message):
    """Imprime un mensaje de advertencia"""
    print(f"[WARNING] {message}")

def test_dependencies():
    """Verifica que todas las dependencias estén instaladas"""
    print_header("Verificando Dependencias")
    
    try:
        import ortools
        print_success("OR-Tools instalado correctamente")
    except ImportError:
        print_error("OR-Tools no está instalado")
        return False
    
    try:
        import spade
        print_success("SPADE instalado correctamente")
    except ImportError:
        print_error("SPADE no está instalado")
        return False
    
    return True

def test_docker_openfire():
    """Verifica que Docker y OpenFire estén funcionando"""
    print_header("Verificando Docker y OpenFire")
    
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "openfire" in result.stdout:
            print_success("Contenedor OpenFire ejecutándose")
        else:
            print_error("Contenedor OpenFire no encontrado")
            return False
    except Exception as e:
        print_error(f"Error con Docker: {e}")
        return False
    
    try:
        response = requests.get("http://localhost:9090", timeout=5)
        if response.status_code == 200:
            print_success("OpenFire API accesible")
        else:
            print_warning(f"OpenFire responde con código {response.status_code}")
    except requests.RequestException as e:
        print_error(f"No se puede conectar a OpenFire: {e}")
        return False
    
    return True

def test_coordinator():
    """Prueba el coordinador distribuido"""
    print_header("Probando Coordinador Distribuido")
    
    try:
        os.chdir(Path(__file__).parent / "src")
        
        # Ejecutar coordinador por unos segundos
        process = subprocess.Popen(
            [sys.executable, "distributed_multi_host_system.py", "--type", "coordinator"],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Esperar 8 segundos para que se conecte
        time.sleep(8)
        
        # Terminar el proceso
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        # Verificar si se conectó exitosamente
        if "connected and authenticated" in stdout:
            print_success("Coordinador conectado exitosamente")
            print_success("Sistema distribuido funcional")
            return True
        else:
            print_error("Coordinador no se pudo conectar")
            print(f"Últimas líneas de salida:")
            for line in stdout.split('\n')[-5:]:
                if line.strip():
                    print(f"  {line}")
            return False
            
    except Exception as e:
        print_error(f"Error en prueba del coordinador: {e}")
        return False

def main():
    """Función principal"""
    print("SISTEMA DE TAXIS DISTRIBUIDO - PRUEBA SIMPLE")
    print("=" * 50)
    
    tests = [
        ("Dependencias", test_dependencies),
        ("Docker y OpenFire", test_docker_openfire),
        ("Coordinador", test_coordinator),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print_error(f"Prueba '{test_name}' falló")
        except Exception as e:
            print_error(f"Error en prueba '{test_name}': {e}")
    
    # Resumen final
    print_header("RESUMEN FINAL")
    print(f"Pruebas exitosas: {passed}/{total}")
    
    if passed == total:
        print_success("¡TODAS LAS PRUEBAS PASARON!")
        print_success("El sistema está completamente funcional")
        print("\nCOMANDOS PARA USAR EL SISTEMA:")
        print("  Coordinador:")
        print("    python src/distributed_multi_host_system.py --type coordinator")
        print("  Host Taxi:")
        print("    python src/distributed_multi_host_system.py --type taxi_host --host-id 1")
        print("  Host Pasajero:")
        print("    python src/distributed_multi_host_system.py --type passenger_host --host-id 1")
        return True
    else:
        print_error(f"{total - passed} pruebas fallaron")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
