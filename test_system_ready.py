#!/usr/bin/env python3
"""
Script de validación rápida para verificar que todos los componentes
del sistema están funcionando correctamente antes del despliegue distribuido.

Ejecuta:
    python test_system_ready.py
"""

import sys
import subprocess
import importlib
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_python_requirements():
    """Verifica que todas las dependencias de Python estén instaladas"""
    logger.info("🔍 Checking Python requirements...")
    
    required_packages = [
        'spade',
        'psutil', 
        'ortools',
        'asyncio',
        'tkinter'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'tkinter':
                import tkinter
            else:
                importlib.import_module(package)
            logger.info(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"   ❌ {package} - NOT INSTALLED")
    
    if missing_packages:
        logger.error(f"Missing packages: {missing_packages}")
        logger.info("Install with: pip install " + " ".join(missing_packages))
        return False
    
    logger.info("✅ All Python requirements satisfied")
    return True

def test_project_structure():
    """Verifica que la estructura del proyecto esté completa"""
    logger.info("🔍 Checking project structure...")
    
    required_files = [
        'src/main.py',
        'src/config.py', 
        'src/agent/agent.py',
        'src/agent/libs/taxi_constraints.py',
        'src/gui/taxi_tkinter_gui.py',
        'benchmark_agents.py',
        'distribution_manager.py',
        'demo_taxi_dispatch.py',
        'requirements.txt'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if Path(file_path).exists():
            logger.info(f"   ✅ {file_path}")
        else:
            missing_files.append(file_path)
            logger.error(f"   ❌ {file_path} - NOT FOUND")
    
    if missing_files:
        logger.error(f"Missing files: {missing_files}")
        return False
    
    logger.info("✅ Project structure complete")
    return True

def test_imports():
    """Verifica que los módulos principales se puedan importar"""
    logger.info("🔍 Testing module imports...")
    
    test_imports = [
        ('src.config', 'config'),
        ('src.agent.libs.taxi_constraints', 'TaxiDecisionSolver'),
        ('src.gui.taxi_tkinter_gui', 'TaxiTkinterGUI')
    ]
    
    import_errors = []
    
    # Agregar src al path
    sys.path.insert(0, str(Path('src').absolute()))
    
    for module_name, class_name in test_imports:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, class_name):
                logger.info(f"   ✅ {module_name}.{class_name}")
            else:
                logger.error(f"   ❌ {module_name}.{class_name} - CLASS NOT FOUND")
                import_errors.append(f"{module_name}.{class_name}")
        except Exception as e:
            logger.error(f"   ❌ {module_name} - IMPORT ERROR: {e}")
            import_errors.append(module_name)
    
    if import_errors:
        logger.error(f"Import errors: {import_errors}")
        return False
    
    logger.info("✅ All module imports successful")
    return True

def test_or_tools_constraints():
    """Verifica que las constraints de OR-Tools funcionen"""
    logger.info("🔍 Testing OR-Tools constraints...")
    
    try:
        sys.path.insert(0, str(Path('src').absolute()))
        from agent.libs.taxi_constraints import TaxiConstraints, TaxiDecisionSolver, TaxiState, RideRequest
        
        # Crear objetos de prueba
        constraints = TaxiConstraints()
        solver = TaxiDecisionSolver(constraints)
        
        taxi_state = TaxiState(
            taxi_id="test_taxi",
            current_position=(0, 0),
            max_capacity=4,
            current_passengers=0,
            is_available=True
        )
        
        ride_request = RideRequest(
            client_id="test_client",
            n_pasajeros=2,
            es_discapacitado=False,
            distancia_al_cliente=10.0,
            client_position=(10, 10),
            destination=(20, 20)
        )
        
        # Probar decisión
        accept, reason, details = solver.can_accept_ride(taxi_state, ride_request)
        
        logger.info(f"   Test decision: {accept} - {reason}")
        logger.info("✅ OR-Tools constraints working")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ OR-Tools constraint test failed: {e}")
        return False

def test_gui_creation():
    """Verifica que la GUI se pueda crear (sin mostrarla)"""
    logger.info("🔍 Testing GUI creation...")
    
    try:
        sys.path.insert(0, str(Path('src').absolute()))
        from gui.taxi_tkinter_gui import TaxiTkinterGUI
        
        # Crear GUI
        gui = TaxiTkinterGUI(width=800, height=600)
        
        # Verificar que se puede agregar un taxi
        gui.add_taxi("test_taxi", (10, 10), 4)
        gui.add_client("test_client", (20, 20), 1, False)
        
        # Verificar que los objetos se crearon
        assert "test_taxi" in gui.taxis
        assert "test_client" in gui.clients
        
        # Destruir GUI
        gui.root.destroy()
        
        logger.info("✅ GUI creation successful")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ GUI test failed: {e}")
        return False

def test_benchmark_script():
    """Verifica que el script de benchmark sea ejecutable"""
    logger.info("🔍 Testing benchmark script...")
    
    try:
        # Verificar que el script se puede importar
        import benchmark_agents
        
        # Verificar que las clases principales existen
        assert hasattr(benchmark_agents, 'AgentBenchmark')
        assert hasattr(benchmark_agents, 'SystemMonitor')
        
        logger.info("✅ Benchmark script ready")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Benchmark script test failed: {e}")
        return False

def test_distribution_script():
    """Verifica que el script de distribución sea ejecutable"""
    logger.info("🔍 Testing distribution script...")
    
    try:
        # Verificar que el script se puede importar
        import distribution_manager
        
        # Verificar que las clases principales existen
        assert hasattr(distribution_manager, 'DistributionManager')
        assert hasattr(distribution_manager, 'HostInfo')
        
        logger.info("✅ Distribution script ready")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Distribution script test failed: {e}")
        return False

def test_demo_executable():
    """Verifica que el demo principal sea ejecutable"""
    logger.info("🔍 Testing demo execution...")
    
    try:
        # Verificar que demo_taxi_dispatch.py existe y se puede importar
        with open('demo_taxi_dispatch.py', 'r') as f:
            content = f.read()
            
        # Verificar que contiene las importaciones principales
        assert 'tkinter' in content
        assert 'TaxiTkinterGUI' in content
        
        logger.info("✅ Demo script ready")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Demo script test failed: {e}")
        return False

def check_deployment_scripts():
    """Verifica que los scripts de despliegue estén presentes"""
    logger.info("🔍 Checking deployment scripts...")
    
    scripts = [
        'deploy_distributed.sh',
        'deploy_distributed.bat'
    ]
    
    missing_scripts = []
    
    for script in scripts:
        if Path(script).exists():
            logger.info(f"   ✅ {script}")
        else:
            missing_scripts.append(script)
            logger.error(f"   ❌ {script} - NOT FOUND")
    
    if missing_scripts:
        logger.error(f"Missing deployment scripts: {missing_scripts}")
        return False
    
    logger.info("✅ Deployment scripts ready")
    return True

def main():
    """Ejecuta todas las pruebas de validación"""
    logger.info("🚀 Starting system readiness validation...")
    logger.info("=" * 60)
    
    tests = [
        ("Python Requirements", test_python_requirements),
        ("Project Structure", test_project_structure), 
        ("Module Imports", test_imports),
        ("OR-Tools Constraints", test_or_tools_constraints),
        ("GUI Creation", test_gui_creation),
        ("Benchmark Script", test_benchmark_script),
        ("Distribution Script", test_distribution_script),
        ("Demo Executable", test_demo_executable),
        ("Deployment Scripts", check_deployment_scripts)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 {test_name}")
        logger.info("-" * 40)
        
        try:
            if test_func():
                passed_tests += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
    
    # Resumen
    logger.info("\n" + "=" * 60)
    logger.info("📊 SYSTEM READINESS SUMMARY")
    logger.info("=" * 60)
    
    if passed_tests == total_tests:
        logger.info(f"🎉 ALL TESTS PASSED ({passed_tests}/{total_tests})")
        logger.info("✅ System is ready for distributed deployment!")
        logger.info("\nNext steps:")
        logger.info("1. Run: python demo_taxi_dispatch.py  (test local GUI)")
        logger.info("2. Run: python benchmark_agents.py --host localhost --max-test 20")
        logger.info("3. Configure remote hosts and run distributed deployment")
        return 0
    else:
        logger.error(f"❌ SOME TESTS FAILED ({passed_tests}/{total_tests})")
        logger.error("⚠️  System is NOT ready for deployment")
        logger.info("\nPlease fix the failing tests before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
