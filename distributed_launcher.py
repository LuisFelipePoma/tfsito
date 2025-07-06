#!/usr/bin/env python3
"""
Distributed launcher for the ideological multi-agent system
"""

import argparse
import subprocess
import time
import sys
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DistributedLauncher:
    """Manages launching agents across multiple hosts"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        
    def launch_host(self, host_id: str, agent_count: int, 
                   openfire_host: str = "localhost", 
                   openfire_port: int = 9090,
                   enable_web: bool = False) -> Optional[subprocess.Popen]:
        """Launch agents on a specific host"""
        
        cmd = [
            sys.executable, "main.py",
            "--host", host_id,
            "--agent-count", str(agent_count),
            "--openfire-host", openfire_host,
            "--openfire-port", str(openfire_port)
        ]
        
        if enable_web:
            cmd.append("--web")
        
        logger.info(f"Launching {agent_count} agents on host {host_id}")
        logger.info(f"Command: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append(process)
            return process
            
        except Exception as e:
            logger.error(f"Failed to launch host {host_id}: {e}")
            return None
    
    def launch_distributed_simulation(self, 
                                    host_configs: List[Dict],
                                    openfire_host: str = "localhost",
                                    openfire_port: int = 9090):
        """Launch a distributed simulation across multiple hosts"""
        
        logger.info(f"Launching distributed simulation with {len(host_configs)} hosts")
        
        # Launch web interface on first host
        first_host = True
        
        for config in host_configs:
            host_id = config["host_id"]
            agent_count = config["agent_count"]
            
            process = self.launch_host(
                host_id=host_id,
                agent_count=agent_count,
                openfire_host=openfire_host,
                openfire_port=openfire_port,
                enable_web=first_host
            )
            
            if process:
                logger.info(f"Started host {host_id} with PID {process.pid}")
                first_host = False
                
                # Small delay between launches
                time.sleep(2.0)
            else:
                logger.error(f"Failed to start host {host_id}")
        
        logger.info(f"Launched {len(self.processes)} host processes")
        
        if self.processes:
            logger.info("Web interface available at: http://localhost:5000")
    
    def monitor_processes(self):
        """Monitor running processes"""
        logger.info("Monitoring processes. Press Ctrl+C to stop all.")
        
        try:
            while self.processes:
                # Check for completed processes
                completed = []
                for i, process in enumerate(self.processes):
                    poll = process.poll()
                    if poll is not None:
                        logger.info(f"Process {process.pid} completed with code {poll}")
                        completed.append(i)
                
                # Remove completed processes
                for i in reversed(completed):
                    self.processes.pop(i)
                
                if self.processes:
                    time.sleep(5.0)
                else:
                    logger.info("All processes completed")
                    break
                    
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            self.shutdown_all()
    
    def shutdown_all(self):
        """Shutdown all running processes"""
        logger.info("Shutting down all processes...")
        
        for process in self.processes:
            try:
                logger.info(f"Terminating process {process.pid}")
                process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing process {process.pid}")
                    process.kill()
                    
            except Exception as e:
                logger.error(f"Error shutting down process {process.pid}: {e}")
        
        self.processes.clear()
        logger.info("All processes shut down")


def main():
    parser = argparse.ArgumentParser(description="Distributed Ideological Agent System Launcher")
    parser.add_argument("--openfire-host", default="localhost", help="Openfire server host")
    parser.add_argument("--openfire-port", type=int, default=9090, help="Openfire server port")
    parser.add_argument("--total-agents", type=int, default=50, help="Total number of agents")
    parser.add_argument("--hosts", type=int, default=3, help="Number of host processes")
    parser.add_argument("--config", help="JSON configuration file for custom setup")
    
    args = parser.parse_args()
    
    launcher = DistributedLauncher()
    
    try:
        if args.config:
            # Load custom configuration
            import json
            with open(args.config, 'r') as f:
                host_configs = json.load(f)
        else:
            # Generate default configuration
            agents_per_host = args.total_agents // args.hosts
            remainder = args.total_agents % args.hosts
            
            host_configs = []
            for i in range(args.hosts):
                agent_count = agents_per_host
                if i < remainder:
                    agent_count += 1
                
                host_configs.append({
                    "host_id": f"host_{i+1}",
                    "agent_count": agent_count
                })
        
        # Print configuration
        total_agents = sum(config["agent_count"] for config in host_configs)
        logger.info(f"Configuration: {len(host_configs)} hosts, {total_agents} total agents")
        for config in host_configs:
            logger.info(f"  {config['host_id']}: {config['agent_count']} agents")
        
        # Launch simulation
        launcher.launch_distributed_simulation(
            host_configs=host_configs,
            openfire_host=args.openfire_host,
            openfire_port=args.openfire_port
        )
        
        # Monitor processes
        launcher.monitor_processes()
        
    except Exception as e:
        logger.error(f"Launcher error: {e}")
        launcher.shutdown_all()
        sys.exit(1)


if __name__ == "__main__":
    main()
