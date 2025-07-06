#!/usr/bin/env python3
"""
Herramienta de benchmark para determinar la capacidad máxima de agentes
que puede soportar un host específico.

Uso:
    python benchmark_agents.py --host localhost --max-test 100 --increment 5
"""

import asyncio
import argparse
import logging
import time
import psutil
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import uuid

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from src.agent.index import create_agent, cleanup_agent
from src.config import config, load_config_from_env
from src.services.openfire_api import openfire_api


class SystemMonitor:
    """Monitor de recursos del sistema en tiempo real"""
    
    def __init__(self):
        self.baseline_metrics = self._get_current_metrics()
        
    def _get_current_metrics(self) -> Dict:
        """Obtiene métricas actuales del sistema"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        return {
            'timestamp': time.time(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'memory_used_gb': memory.used / (1024**3),
            'process_count': len(psutil.pids()),
            'load_average': getattr(os, 'getloadavg', lambda: [0, 0, 0])()
        }
    
    def get_resource_usage(self) -> Dict:
        """Obtiene uso de recursos comparado con baseline"""
        current = self._get_current_metrics()
        return {
            'current': current,
            'baseline': self.baseline_metrics,
            'delta': {
                'cpu_percent': current['cpu_percent'] - self.baseline_metrics['cpu_percent'],
                'memory_percent': current['memory_percent'] - self.baseline_metrics['memory_percent'],
                'memory_used_gb': current['memory_used_gb'] - self.baseline_metrics['memory_used_gb'],
                'process_count': current['process_count'] - self.baseline_metrics['process_count']
            }
        }


class AgentBenchmark:
    """Benchmark para determinar la capacidad máxima de agentes"""
    
    def __init__(self, host_id: str, max_cpu_threshold: float = 80.0, max_memory_threshold: float = 85.0):
        self.host_id = host_id
        self.max_cpu_threshold = max_cpu_threshold
        self.max_memory_threshold = max_memory_threshold
        self.monitor = SystemMonitor()
        self.agents: List = []
        self.benchmark_results = []
        self.max_agents_found = 0
        
    async def initialize(self) -> bool:
        """Inicializa el sistema de benchmark"""
        logger.info(f"Initializing benchmark for host {self.host_id}")
        
        # Cargar configuración
        load_config_from_env()
        
        # Verificar conexión con Openfire
        if not openfire_api.health_check():
            logger.error("Cannot connect to Openfire server")
            return False
            
        logger.info("Openfire connection verified")
        logger.info(f"Baseline system metrics: {self.monitor.baseline_metrics}")
        return True
    
    async def spawn_agent_batch(self, batch_size: int, start_index: int) -> int:
        """Spawns a batch of agents and returns the number successfully created"""
        successful_spawns = 0
        
        for i in range(batch_size):
            agent_id = f"{self.host_id}_benchmark_{start_index + i}_{uuid.uuid4().hex[:8]}"
            
            try:
                agent = await create_agent(agent_id, self.host_id)
                if agent:
                    self.agents.append(agent)
                    successful_spawns += 1
                    logger.debug(f"Successfully spawned agent {agent_id}")
                else:
                    logger.warning(f"Failed to spawn agent {agent_id}")
                    break
                    
                # Small delay between spawns to avoid overwhelming the system
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error spawning agent {agent_id}: {e}")
                break
                
        return successful_spawns
    
    def check_system_limits(self) -> Tuple[bool, str]:
        """Verifica si el sistema ha alcanzado los límites de recursos"""
        metrics = self.monitor.get_resource_usage()
        current = metrics['current']
        
        if current['cpu_percent'] > self.max_cpu_threshold:
            return False, f"CPU usage too high: {current['cpu_percent']:.1f}% > {self.max_cpu_threshold}%"
            
        if current['memory_percent'] > self.max_memory_threshold:
            return False, f"Memory usage too high: {current['memory_percent']:.1f}% > {self.max_memory_threshold}%"
            
        if current['memory_available_gb'] < 0.5:  # Less than 500MB available
            return False, f"Memory available too low: {current['memory_available_gb']:.2f}GB"
            
        return True, "System resources within limits"
    
    async def test_agent_capacity(self, max_agents: int = 100, increment: int = 5, stabilization_time: float = 3.0) -> Dict:
        """
        Prueba la capacidad de agentes incrementalmente
        
        Args:
            max_agents: Máximo número de agentes a probar
            increment: Incremento de agentes en cada paso
            stabilization_time: Tiempo de espera para estabilización entre incrementos
        """
        logger.info(f"Starting agent capacity test (max: {max_agents}, increment: {increment})")
        
        current_agents = 0
        
        while current_agents < max_agents:
            # Calcular cuántos agentes agregar en este batch
            target_agents = min(current_agents + increment, max_agents)
            batch_size = target_agents - current_agents
            
            logger.info(f"Testing with {target_agents} agents (adding {batch_size})...")
            
            # Spawnear batch de agentes
            successful_spawns = await self.spawn_agent_batch(batch_size, current_agents)
            current_agents += successful_spawns
            
            if successful_spawns < batch_size:
                logger.warning(f"Only {successful_spawns}/{batch_size} agents spawned successfully")
            
            # Tiempo de estabilización
            await asyncio.sleep(stabilization_time)
            
            # Verificar recursos del sistema
            within_limits, reason = self.check_system_limits()
            metrics = self.monitor.get_resource_usage()
            
            # Registrar resultado de este paso
            step_result = {
                'agent_count': current_agents,
                'successful_spawns': successful_spawns,
                'within_limits': within_limits,
                'limit_reason': reason,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
            self.benchmark_results.append(step_result)
            
            logger.info(f"Agents: {current_agents}, CPU: {metrics['current']['cpu_percent']:.1f}%, "
                       f"Memory: {metrics['current']['memory_percent']:.1f}%, Status: {reason}")
            
            # Si superamos los límites del sistema, detener la prueba
            if not within_limits:
                logger.warning(f"System limits reached at {current_agents} agents: {reason}")
                self.max_agents_found = current_agents - increment if current_agents >= increment else current_agents
                break
                
            self.max_agents_found = current_agents
            
        return {
            'max_agents_achieved': current_agents,
            'max_safe_agents': self.max_agents_found,
            'final_metrics': self.monitor.get_resource_usage(),
            'total_steps': len(self.benchmark_results),
            'benchmark_successful': True
        }
    
    async def cleanup_all_agents(self):
        """Limpia todos los agentes creados durante el benchmark"""
        logger.info(f"Cleaning up {len(self.agents)} agents...")
        
        cleanup_tasks = []
        for agent in self.agents:
            cleanup_tasks.append(cleanup_agent(agent))
            
        if cleanup_tasks:
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.warning(f"Errors during cleanup: {len(errors)} agents failed to cleanup properly")
            else:
                logger.info("All agents cleaned up successfully")
                
        self.agents.clear()
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """Guarda los resultados del benchmark en un archivo JSON"""
        if filename is None:
            filename = f"benchmark_results_{self.host_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        results = {
            'host_id': self.host_id,
            'benchmark_config': {
                'max_cpu_threshold': self.max_cpu_threshold,
                'max_memory_threshold': self.max_memory_threshold
            },
            'max_agents_found': self.max_agents_found,
            'baseline_metrics': self.monitor.baseline_metrics,
            'detailed_results': self.benchmark_results,
            'summary': self._generate_summary(),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Benchmark results saved to {filename}")
        return filename
    
    def _generate_summary(self) -> Dict:
        """Genera un resumen de los resultados del benchmark"""
        if not self.benchmark_results:
            return {}
            
        return {
            'recommended_max_agents': max(1, self.max_agents_found - 5),  # Buffer de seguridad
            'absolute_max_agents': self.max_agents_found,
            'peak_cpu_usage': max(r['metrics']['current']['cpu_percent'] for r in self.benchmark_results),
            'peak_memory_usage': max(r['metrics']['current']['memory_percent'] for r in self.benchmark_results),
            'total_test_duration_minutes': (
                (datetime.fromisoformat(self.benchmark_results[-1]['timestamp']) - 
                 datetime.fromisoformat(self.benchmark_results[0]['timestamp'])).total_seconds() / 60
            ) if len(self.benchmark_results) > 1 else 0,
            'performance_degradation': self._calculate_performance_degradation()
        }
    
    def _calculate_performance_degradation(self) -> Dict:
        """Calcula la degradación del rendimiento durante el test"""
        if len(self.benchmark_results) < 2:
            return {}
            
        first = self.benchmark_results[0]['metrics']['current']
        last = self.benchmark_results[-1]['metrics']['current']
        
        return {
            'cpu_increase_percent': last['cpu_percent'] - first['cpu_percent'],
            'memory_increase_percent': last['memory_percent'] - first['memory_percent'],
            'memory_increase_gb': last['memory_used_gb'] - first['memory_used_gb']
        }


async def main():
    parser = argparse.ArgumentParser(description="Benchmark agent capacity for a host")
    parser.add_argument("--host", type=str, default="localhost", help="Host identifier")
    parser.add_argument("--max-test", type=int, default=100, help="Maximum agents to test")
    parser.add_argument("--increment", type=int, default=5, help="Agent increment per step")
    parser.add_argument("--cpu-threshold", type=float, default=80.0, help="CPU usage threshold (%)")
    parser.add_argument("--memory-threshold", type=float, default=85.0, help="Memory usage threshold (%)")
    parser.add_argument("--stabilization-time", type=float, default=3.0, help="Stabilization time between steps (seconds)")
    parser.add_argument("--output", type=str, help="Output filename for results")
    
    args = parser.parse_args()
    
    benchmark = AgentBenchmark(
        host_id=args.host,
        max_cpu_threshold=args.cpu_threshold,
        max_memory_threshold=args.memory_threshold
    )
    
    try:
        # Inicializar
        if not await benchmark.initialize():
            logger.error("Failed to initialize benchmark")
            return 1
            
        # Ejecutar benchmark
        results = await benchmark.test_agent_capacity(
            max_agents=args.max_test,
            increment=args.increment,
            stabilization_time=args.stabilization_time
        )
        
        # Mostrar resultados
        logger.info("=" * 60)
        logger.info("BENCHMARK RESULTS")
        logger.info("=" * 60)
        logger.info(f"Maximum agents achieved: {results['max_agents_achieved']}")
        logger.info(f"Recommended safe limit: {benchmark._generate_summary().get('recommended_max_agents', 'N/A')}")
        logger.info(f"Final CPU usage: {results['final_metrics']['current']['cpu_percent']:.1f}%")
        logger.info(f"Final Memory usage: {results['final_metrics']['current']['memory_percent']:.1f}%")
        
        # Guardar resultados
        output_file = benchmark.save_results(args.output)
        logger.info(f"Detailed results saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1
        
    finally:
        # Cleanup
        await benchmark.cleanup_all_agents()


if __name__ == "__main__":
    import sys
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        sys.exit(1)
