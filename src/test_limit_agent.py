import subprocess
import time
import psutil
import sys
import os
from datetime import datetime
import json

class HostLimitTester:
    def __init__(self):
        self.log_file = "comparador_multi_host.log"
        open(self.log_file, 'w').close()

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    def run_host_test(self, num_hosts, agents_per_host, test_duration=20):
        self.log(f"Prueba: {num_hosts} hosts, {agents_per_host} agentes/host")
        total_agents = num_hosts * agents_per_host
        processes, agents_ready = [], [0] * num_hosts
        start = time.time()

        for i in range(num_hosts):
            cmd = [sys.executable, "main.py", "--host", f"taxi_host_{i+1}", "--agent-type", "taxi", "--agent-count", str(agents_per_host)]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            processes.append((f"taxi_host_{i+1}", p))

        print("Iniciando prueba de creacion de agentes...")
        memory_limit = False
        while not memory_limit and any(a < agents_per_host for a in agents_ready):
            print(psutil.virtual_memory().percent)
            print(type(psutil.virtual_memory().percent))
            if psutil.virtual_memory().percent >= 85.0:
                memory_limit = True
                break
            for idx, (name, proc) in enumerate(processes):
                if proc.poll() is not None: continue
                try:
                    while True:
                        line = proc.stdout.readline()
                        if not line: break
                        if "Taxi agent" in line and "created" in line:
                            agents_ready[idx] += 1
                except: pass

        total_created = sum(agents_ready)
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                proc.kill()

        success = total_created == total_agents and not memory_limit
        return {'success': success, 'total_agents': total_agents, 'agents_created': total_created, 'memory_limited': memory_limit}

    def find_limit_for_hosts(self, num_hosts):
        min_agents, max_agents = 2, 10000
        best = {'success': False}
        while min_agents <= max_agents:
            mid = (min_agents + max_agents) // 2
            result = self.run_host_test(num_hosts, mid)
            print(result)
            if result['success']:
                best = result
                min_agents = mid + 1
            else:
                max_agents = mid - 1
            time.sleep(2)
        return best.get('agents_created', 0), best

    def run_comparison(self):
        self.log("Inicio comparacion multi-host")
        if not os.path.exists("main.py"):
            self.log("ERROR: main.py no encontrado")
            return

        results = {}
        for hosts, factor in [(2, 2), (3, 3)]:
            limit, config = self.find_limit_for_hosts(hosts)
            results[f'{hosts}_hosts'] = {'max_agents': limit, 'config': config}
            if limit > 0:
                stress_agents = max(2, (limit * factor) // hosts)
                stress_result = self.run_host_test(hosts, stress_agents)
                results[f'{hosts}_hosts_stress'] = {'requested_agents': stress_agents * hosts, 'config': stress_result}

        self.generate_report(results)

    def generate_report(self, results):
        self.log("\nReporte final:")
        for key, res in results.items():
            agents = res.get('max_agents', res.get('requested_agents', 0))
            success = res['config'].get('success')
            self.log(f"{key}: {agents} agentes - {'EXITO' if success else 'FALLO'}")
        with open('comparacion_multi_host.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        self.log("Reporte guardado: comparacion_multi_host.json")

if __name__ == "__main__":
    try:
        HostLimitTester().run_comparison()
    except KeyboardInterrupt:
        print("Interrumpido por el usuario")
