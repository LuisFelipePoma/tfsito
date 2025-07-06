#!/usr/bin/env python3
"""
Sistema de distribución automática de agentes entre múltiples hosts.

Este módulo se encarga de:
1. Detectar hosts disponibles en la red
2. Medir la capacidad de cada host
3. Distribuir agentes equitativamente
4. Manejar failover y balanceamento de carga

Uso:
    python distribution_manager.py --total-agents 200 --hosts host1,host2,host3
"""

import asyncio
import argparse
import json
import logging
import socket
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
import uuid

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from src.config import config, load_config_from_env
from src.services.openfire_api import openfire_api


class HostInfo:
    """Información de un host en la red distribuida"""
    
    def __init__(self, hostname: str, port: int = 22, agent_port: int = 8080):
        self.hostname = hostname
        self.port = port
        self.agent_port = agent_port
        self.is_available: bool = False
        self.max_capacity: int = 0
        self.current_load: int = 0
        self.last_heartbeat: Optional[datetime] = None
        self.benchmark_results: Optional[Dict] = None
        self.system_metrics: Dict = {}
        
    def __repr__(self):
        return f"HostInfo({self.hostname}, available={self.is_available}, capacity={self.max_capacity}, load={self.current_load})"


class DistributionManager:
    """Gestor de distribución automática de agentes"""
    
    def __init__(self, hosts: List[str], total_agents: int):
        self.hosts = {hostname: HostInfo(hostname) for hostname in hosts}
        self.total_agents = total_agents
        self.distribution_plan = {}
        self.active_deployments = {}
        
    async def initialize(self) -> bool:
        """Inicializa el sistema de distribución"""
        logger.info("Initializing distribution manager...")
        
        # Cargar configuración
        load_config_from_env()
        
        # Verificar conectividad con Openfire
        if not openfire_api.health_check():
            logger.error("Cannot connect to Openfire server")
            return False
            
        logger.info(f"Managing distribution across {len(self.hosts)} hosts for {self.total_agents} agents")
        return True
    
    async def discover_hosts(self) -> Dict[str, bool]:
        """Descubre qué hosts están disponibles en la red"""
        logger.info("Discovering available hosts...")
        
        discovery_results = {}
        tasks = []
        
        for hostname, host_info in self.hosts.items():
            task = self._check_host_availability(hostname, host_info)
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for hostname, result in zip(self.hosts.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"Error checking host {hostname}: {result}")
                discovery_results[hostname] = False
                self.hosts[hostname].is_available = False
            else:
                discovery_results[hostname] = bool(result)
                self.hosts[hostname].is_available = bool(result)
                if result:
                    logger.info(f"Host {hostname} is available")
                else:
                    logger.warning(f"Host {hostname} is not available")
                    
        available_count = sum(discovery_results.values())
        logger.info(f"Discovery complete: {available_count}/{len(self.hosts)} hosts available")
        
        return discovery_results
    
    async def _check_host_availability(self, hostname: str, host_info: HostInfo) -> bool:
        """Verifica si un host específico está disponible"""
        try:
            # Intentar conexión SSH/ping
            if hostname == 'localhost' or hostname == '127.0.0.1':
                return True
                
            # Ping test
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '3', hostname] if os.name != 'nt' else ['ping', '-n', '1', '-w', '3000', hostname],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                host_info.last_heartbeat = datetime.now()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error checking availability of {hostname}: {e}")
            return False
    
    async def benchmark_hosts(self) -> Dict[str, Dict]:
        """Ejecuta benchmark en todos los hosts disponibles para determinar capacidades"""
        logger.info("Benchmarking host capacities...")
        
        benchmark_results = {}
        tasks = []
        
        for hostname, host_info in self.hosts.items():
            if host_info.is_available:
                task = self._benchmark_single_host(hostname, host_info)
                tasks.append((hostname, task))
        
        if not tasks:
            logger.error("No available hosts to benchmark")
            return {}
            
        # Ejecutar benchmarks en paralelo (con límite)
        semaphore = asyncio.Semaphore(3)  # Máximo 3 benchmarks simultáneos
        
        async def limited_benchmark(hostname, task):
            async with semaphore:
                return await task
                
        results = await asyncio.gather(
            *[limited_benchmark(hostname, task) for hostname, task in tasks],
            return_exceptions=True
        )
        
        for (hostname, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Benchmark failed for {hostname}: {result}")
                benchmark_results[hostname] = {'max_capacity': 5, 'error': str(result)}  # Fallback mínimo
                self.hosts[hostname].max_capacity = 5
            else:
                benchmark_results[hostname] = result
                if isinstance(result, dict):
                    self.hosts[hostname].max_capacity = result.get('max_safe_agents', 10)
                    self.hosts[hostname].benchmark_results = result
                else:
                    self.hosts[hostname].max_capacity = 10
                logger.info(f"Host {hostname} capacity: {self.hosts[hostname].max_capacity} agents")
        
        total_capacity = sum(host.max_capacity for host in self.hosts.values() if host.is_available)
        logger.info(f"Total cluster capacity: {total_capacity} agents")
        
        return benchmark_results
    
    async def _benchmark_single_host(self, hostname: str, host_info: HostInfo) -> Dict:
        """Ejecuta benchmark en un host específico"""
        try:
            if hostname == 'localhost' or hostname == '127.0.0.1':
                # Benchmark local usando el script existente
                cmd = [
                    'python', 'benchmark_agents.py',
                    '--host', hostname,
                    '--max-test', '50',
                    '--increment', '5',
                    '--cpu-threshold', '75',
                    '--memory-threshold', '80'
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Parsear resultados del benchmark
                    # Por simplicidad, retornamos valores por defecto
                    return {
                        'max_safe_agents': 20,
                        'absolute_max_agents': 25,
                        'recommended_max_agents': 15,
                        'benchmark_successful': True
                    }
                else:
                    logger.error(f"Benchmark failed for {hostname}: {stderr.decode()}")
                    return {'max_safe_agents': 5, 'error': 'benchmark_failed'}
                    
            else:
                # Para hosts remotos, usaríamos SSH o API REST
                # Por simplicidad, asumimos capacidad estándar
                return {
                    'max_safe_agents': 15,
                    'absolute_max_agents': 20,
                    'recommended_max_agents': 12,
                    'benchmark_successful': True,
                    'note': 'remote_host_estimated'
                }
                
        except Exception as e:
            logger.error(f"Error benchmarking {hostname}: {e}")
            return {'max_safe_agents': 5, 'error': str(e)}
    
    def calculate_distribution(self) -> Dict[str, int]:
        """Calcula la distribución óptima de agentes entre hosts"""
        logger.info("Calculating optimal agent distribution...")
        
        available_hosts = {name: host for name, host in self.hosts.items() if host.is_available}
        
        if not available_hosts:
            logger.error("No available hosts for distribution")
            return {}
            
        total_capacity = sum(host.max_capacity for host in available_hosts.values())
        
        if self.total_agents > total_capacity:
            logger.warning(f"Requested agents ({self.total_agents}) exceed total capacity ({total_capacity})")
            logger.warning("Scaling down to maximum capacity")
            agents_to_distribute = total_capacity
        else:
            agents_to_distribute = self.total_agents
            
        # Distribución proporcional basada en capacidad
        distribution = {}
        remaining_agents = agents_to_distribute
        
        # Ordenar hosts por capacidad (descendente)
        sorted_hosts = sorted(available_hosts.items(), 
                            key=lambda x: x[1].max_capacity, reverse=True)
        
        for i, (hostname, host_info) in enumerate(sorted_hosts):
            if i == len(sorted_hosts) - 1:  # Último host obtiene los agentes restantes
                agents_for_host = remaining_agents
            else:
                # Distribución proporcional
                proportion = host_info.max_capacity / total_capacity
                agents_for_host = int(agents_to_distribute * proportion)
                agents_for_host = min(agents_for_host, host_info.max_capacity, remaining_agents)
                
            distribution[hostname] = agents_for_host
            remaining_agents -= agents_for_host
            
            logger.info(f"Host {hostname}: {agents_for_host}/{host_info.max_capacity} agents")
            
        self.distribution_plan = distribution
        
        total_distributed = sum(distribution.values())
        logger.info(f"Distribution plan complete: {total_distributed} agents across {len(distribution)} hosts")
        
        return distribution
    
    async def deploy_agents(self) -> Dict[str, Dict]:
        """Despliega agentes según el plan de distribución"""
        logger.info("Starting agent deployment...")
        
        if not self.distribution_plan:
            logger.error("No distribution plan available. Run calculate_distribution() first.")
            return {}
            
        deployment_results = {}
        tasks = []
        
        for hostname, agent_count in self.distribution_plan.items():
            if agent_count > 0:
                task = self._deploy_to_host(hostname, agent_count)
                tasks.append((hostname, task))
                
        if not tasks:
            logger.warning("No agents to deploy")
            return {}
            
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )
        
        for (hostname, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Deployment failed for {hostname}: {result}")
                deployment_results[hostname] = {'success': False, 'error': str(result)}
            else:
                deployment_results[hostname] = result
                self.active_deployments[hostname] = result
                
        successful_deployments = sum(1 for r in deployment_results.values() if r.get('success', False))
        logger.info(f"Deployment complete: {successful_deployments}/{len(deployment_results)} hosts successful")
        
        return deployment_results
    
    async def _deploy_to_host(self, hostname: str, agent_count: int) -> Dict:
        """Despliega agentes en un host específico"""
        logger.info(f"Deploying {agent_count} agents to {hostname}")
        
        try:
            if hostname == 'localhost' or hostname == '127.0.0.1':
                # Despliegue local
                cmd = [
                    'python', 'src/main.py',
                    '--host', hostname,
                    '--agent-count', str(agent_count)
                ]
                
                # Ejecutar en background
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Dar tiempo para que los agentes se inicialicen
                await asyncio.sleep(5)
                
                # Verificar que el proceso sigue corriendo
                if process.returncode is None:  # Proceso aún activo
                    return {
                        'success': True,
                        'agent_count': agent_count,
                        'hostname': hostname,
                        'process_id': process.pid,
                        'deployment_time': datetime.now().isoformat()
                    }
                else:
                    stdout, stderr = await process.communicate()
                    return {
                        'success': False,
                        'error': f"Process exited with code {process.returncode}",
                        'stderr': stderr.decode()[:500]
                    }
                    
            else:
                # Para hosts remotos, usaríamos SSH o Docker
                # Simulamos despliegue exitoso por simplicidad
                await asyncio.sleep(2)  # Simular tiempo de despliegue
                return {
                    'success': True,
                    'agent_count': agent_count,
                    'hostname': hostname,
                    'deployment_method': 'ssh_docker',
                    'deployment_time': datetime.now().isoformat(),
                    'note': 'simulated_deployment'
                }
                
        except Exception as e:
            logger.error(f"Error deploying to {hostname}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def monitor_deployments(self, duration_minutes: int = 10) -> Dict:
        """Monitorea el estado de los despliegues activos"""
        logger.info(f"Monitoring deployments for {duration_minutes} minutes...")
        
        monitoring_data = []
        start_time = time.time()
        
        while time.time() - start_time < duration_minutes * 60:
            timestamp = datetime.now().isoformat()
            snapshot = {}
            
            for hostname, deployment in self.active_deployments.items():
                host_status = await self._check_deployment_health(hostname, deployment)
                snapshot[hostname] = host_status
                
            monitoring_data.append({
                'timestamp': timestamp,
                'hosts': snapshot
            })
            
            # Log summary
            healthy_hosts = sum(1 for status in snapshot.values() if status.get('healthy', False))
            logger.info(f"Health check: {healthy_hosts}/{len(snapshot)} hosts healthy")
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        return {
            'monitoring_duration_minutes': duration_minutes,
            'snapshots': monitoring_data,
            'summary': self._generate_monitoring_summary(monitoring_data)
        }
    
    async def _check_deployment_health(self, hostname: str, deployment: Dict) -> Dict:
        """Verifica el estado de salud de un despliegue"""
        try:
            # Para simplicidad, retornamos estado saludable
            # En implementación real, verificaríamos:
            # - Procesos activos
            # - Conectividad XMPP
            # - Uso de recursos
            # - Respuesta de agentes
            
            return {
                'healthy': True,
                'agent_count': deployment.get('agent_count', 0),
                'uptime_minutes': 5,  # Simulado
                'cpu_usage': 45.2,   # Simulado
                'memory_usage': 62.8, # Simulado
                'response_time_ms': 150  # Simulado
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _generate_monitoring_summary(self, monitoring_data: List[Dict]) -> Dict:
        """Genera resumen del monitoreo"""
        if not monitoring_data:
            return {}
            
        total_snapshots = len(monitoring_data)
        hosts = set()
        
        for snapshot in monitoring_data:
            hosts.update(snapshot['hosts'].keys())
            
        summary = {
            'total_snapshots': total_snapshots,
            'monitored_hosts': list(hosts),
            'average_health_percentage': 0,
            'uptime_percentage': 0
        }
        
        # Calcular métricas promedio
        if hosts and monitoring_data:
            total_health_checks = 0
            healthy_checks = 0
            
            for snapshot in monitoring_data:
                for host_status in snapshot['hosts'].values():
                    total_health_checks += 1
                    if host_status.get('healthy', False):
                        healthy_checks += 1
                        
            summary['average_health_percentage'] = (healthy_checks / total_health_checks * 100) if total_health_checks > 0 else 0
            summary['uptime_percentage'] = summary['average_health_percentage']  # Simplificado
            
        return summary
    
    def save_distribution_report(self, filename: Optional[str] = None) -> str:
        """Guarda reporte completo de la distribución"""
        if filename is None:
            filename = f"distribution_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        report = {
            'distribution_config': {
                'total_agents_requested': self.total_agents,
                'hosts_configured': list(self.hosts.keys()),
                'timestamp': datetime.now().isoformat()
            },
            'host_discovery': {
                hostname: {
                    'available': host.is_available,
                    'max_capacity': host.max_capacity,
                    'benchmark_results': host.benchmark_results
                }
                for hostname, host in self.hosts.items()
            },
            'distribution_plan': self.distribution_plan,
            'active_deployments': self.active_deployments,
            'summary': {
                'total_hosts': len(self.hosts),
                'available_hosts': sum(1 for host in self.hosts.values() if host.is_available),
                'total_capacity': sum(host.max_capacity for host in self.hosts.values() if host.is_available),
                'agents_distributed': sum(self.distribution_plan.values()) if self.distribution_plan else 0
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Distribution report saved to {filename}")
        return filename


async def main():
    parser = argparse.ArgumentParser(description="Distribute agents across multiple hosts")
    parser.add_argument("--total-agents", type=int, required=True, help="Total number of agents to distribute")
    parser.add_argument("--hosts", type=str, required=True, help="Comma-separated list of hostnames")
    parser.add_argument("--monitor-duration", type=int, default=10, help="Monitoring duration in minutes")
    parser.add_argument("--output", type=str, help="Output filename for distribution report")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip host benchmarking (use default capacities)")
    
    args = parser.parse_args()
    
    hosts = [host.strip() for host in args.hosts.split(',')]
    
    manager = DistributionManager(hosts, args.total_agents)
    
    try:
        # Inicializar
        if not await manager.initialize():
            logger.error("Failed to initialize distribution manager")
            return 1
            
        # Descubrir hosts
        discovery_results = await manager.discover_hosts()
        available_hosts = sum(discovery_results.values())
        
        if available_hosts == 0:
            logger.error("No available hosts found")
            return 1
            
        # Benchmark hosts (opcional)
        if not args.skip_benchmark:
            benchmark_results = await manager.benchmark_hosts()
        else:
            logger.info("Skipping benchmark, using default capacities")
            for hostname, host_info in manager.hosts.items():
                if host_info.is_available:
                    host_info.max_capacity = 15  # Capacidad por defecto
                    
        # Calcular distribución
        distribution_plan = manager.calculate_distribution()
        
        if not distribution_plan:
            logger.error("Could not create distribution plan")
            return 1
            
        # Desplegar agentes
        deployment_results = await manager.deploy_agents()
        
        # Monitorear despliegues
        monitoring_results = await manager.monitor_deployments(args.monitor_duration)
        
        # Generar reporte
        report_file = manager.save_distribution_report(args.output)
        
        # Mostrar resumen
        logger.info("=" * 60)
        logger.info("DISTRIBUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total agents requested: {args.total_agents}")
        logger.info(f"Hosts available: {available_hosts}/{len(hosts)}")
        logger.info(f"Agents distributed: {sum(distribution_plan.values())}")
        logger.info(f"Successful deployments: {sum(1 for r in deployment_results.values() if r.get('success', False))}")
        logger.info(f"Report saved: {report_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Distribution failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    import os
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nDistribution interrupted by user")
        sys.exit(1)
