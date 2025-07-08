#!/usr/bin/env python3
"""
Prueba Comprehensiva del Sistema de Taxis Distribuido
====================================================

Este script ejecuta una serie de pruebas para verificar que todo
el sistema esté funcionando correctamente.
"""

import subprocess
import time
import requests
import os
import sys
from pathlib import Path

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def print_header(title):
    """Imprime un header decorado"""
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def print_success(message):
    """Imprime un mensaje de éxito"""
    print(f"✅ {message}")

def print_error(message):
    """Imprime un mensaje de error"""
    print(f"❌ {message}")

def print_warning(message):
    """Imprime un mensaje de advertencia"""
    print(f"⚠️  {message}")

def test_dependencies():
    """Verifica que todas las dependencias estén instaladas"""
    print_header("Verificando Dependencias")
    
    try:
        import ortools
        print_success("OR-Tools instalado correctamente")
    except ImportError:
        print_error("OR-Tools no está instalado. Ejecute: pip install ortools")
        return False
    
    try:
        import spade
        print_success("SPADE instalado correctamente")
    except ImportError:
        print_error("SPADE no está instalado. Ejecute: pip install spade")
        return False
    
    try:
        import tkinter
        print_success("Tkinter disponible para GUI")
    except ImportError:
        print_warning("Tkinter no disponible - GUI no funcionará")
    
    return True

def test_docker_openfire():
    """Verifica que Docker y OpenFire estén funcionando"""
    print_header("Verificando Docker y OpenFire")
    
    # Verificar Docker
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            if "openfire" in result.stdout:
                print_success("Contenedor OpenFire está ejecutándose")
            else:
                print_error("Contenedor OpenFire no encontrado")
                print("Para iniciarlo: docker-compose up -d openfire")
                return False
        else:
            print_error("Docker no está disponible o no está ejecutándose")
            return False
    except subprocess.TimeoutExpired:
        print_error("Timeout al verificar Docker")
        return False
    except FileNotFoundError:
        print_error("Docker no está instalado")
        return False
    
    # Verificar API de OpenFire
    try:
        response = requests.get("http://localhost:9090", timeout=5)
        if response.status_code == 200:
            print_success("OpenFire API accesible en http://localhost:9090")
        else:
            print_warning(f"OpenFire responde pero con código {response.status_code}")
    except requests.RequestException as e:
        print_error(f"No se puede conectar a OpenFire API: {e}")
        return False
    
    return True

def test_local_system():
    """Prueba el sistema local (no distribuido)"""
    print_header("Probando Sistema Local")
    
    try:
        os.chdir(Path(__file__).parent / "src")
        result = subprocess.run([sys.executable, "quick_test.py"], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print_success("Sistema local funciona correctamente")
            print("📊 Resultados de la prueba:")
            # Mostrar solo las líneas importantes
            for line in result.stdout.split('\n'):
                if any(marker in line for marker in ['✅', '🎉', 'TODAS LAS PRUEBAS']):
                    print(f"   {line}")
            return True
        else:
            print_error("Sistema local falló")
            print("❌ Error:", result.stderr[-500:])  # Últimos 500 caracteres del error
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Timeout en prueba del sistema local")
        return False
    except Exception as e:
        print_error(f"Error ejecutando prueba local: {e}")
        return False

def test_spade_connection():
    """Prueba la conexión SPADE con OpenFire"""
    print_header("Probando Conexión SPADE")
    
    try:
        # Cambiar al directorio del proyecto
        original_dir = os.getcwd()
        os.chdir(Path(__file__).parent)
        
        # Crear script de prueba rápida
        test_script = """
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
import time

class TestAgent(Agent):
    class TestBehaviour(OneShotBehaviour):
        async def run(self):
            print("✅ SPADE Agent conectado y ejecutándose")
            await asyncio.sleep(1)
            self.agent.stop()
    
    async def setup(self):
        self.add_behaviour(self.TestBehaviour())

async def main():
    try:
        agent = TestAgent("test_agent@localhost", "123")
        await agent.start()
        print("✅ Agente SPADE iniciado")
        
        # Esperar un poco para que el comportamiento se ejecute
        await asyncio.sleep(3)
        
        await agent.stop()
        print("✅ Agente SPADE detenido correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en agente SPADE: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
"""
        
        with open("temp_spade_test.py", "w") as f:
            f.write(test_script)
        
        result = subprocess.run([sys.executable, "temp_spade_test.py"], 
                              capture_output=True, text=True, timeout=20)
        
        # Limpiar archivo temporal
        if os.path.exists("temp_spade_test.py"):
            os.remove("temp_spade_test.py")
        
        os.chdir(original_dir)
        
        if result.returncode == 0:
            print_success("Conexión SPADE funciona correctamente")
            return True
        else:
            print_error("Conexión SPADE falló")
            print("❌ Error:", result.stderr[-300:])
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Timeout en prueba SPADE")
        return False
    except Exception as e:
        print_error(f"Error en prueba SPADE: {e}")
        return False

def test_coordinator_quick():
    """Prueba rápida del coordinador distribuido"""
    print_header("Probando Coordinador Distribuido (Prueba Rápida)")
    
    try:
        os.chdir(Path(__file__).parent / "src")
        
        # Ejecutar coordinador por unos segundos
        process = subprocess.Popen([sys.executable, "distributed_multi_host_system.py", "--type", "coordinator"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Esperar 5 segundos
        time.sleep(5)
        
        # Terminar el proceso
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        
        # Verificar si se conectó exitosamente
        if "connected and authenticated" in stdout:
            print_success("Coordinador se conectó exitosamente a OpenFire")
            print_success("Sistema distribuido funcional")
            return True
        else:
            print_error("Coordinador no se pudo conectar")
            print("❌ Output:", stdout[-500:])
            print("❌ Error:", stderr[-500:])
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Timeout en prueba del coordinador")
        return False
    except Exception as e:
        print_error(f"Error en prueba del coordinador: {e}")
        return False

def main():
    """Función principal que ejecuta todas las pruebas"""
    print("🚕 SISTEMA DE TAXIS DISTRIBUIDO - PRUEBA COMPREHENSIVA")
    print("=" * 60)
    
    tests = [
        ("Dependencias", test_dependencies),
        ("Docker y OpenFire", test_docker_openfire),
        ("Sistema Local", test_local_system),
        ("Conexión SPADE", test_spade_connection),
        ("Coordinador Distribuido", test_coordinator_quick),
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
    print(f"✅ Pruebas exitosas: {passed}/{total}")
    
    if passed == total:
        print_success("🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print_success("El sistema está completamente funcional")
        print("\n📋 COMANDOS PARA USAR EL SISTEMA:")
        print("   • Coordinador: python src/distributed_multi_host_system.py --type coordinator")
        print("   • Host Taxi: python src/distributed_multi_host_system.py --type taxi_host --host-id 1")
        print("   • Host Pasajero: python src/distributed_multi_host_system.py --type passenger_host --host-id 1")
        print("   • Demo Local: python src/demo_taxi_system.py")
        print("   • GUI Local: python src/taxi_dispatch_gui.py")
        return True
    else:
        print_error(f"❌ {total - passed} pruebas fallaron")
        print_error("Revise los errores anteriores y corrija los problemas")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
    