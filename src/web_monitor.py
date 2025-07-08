"""
Monitor Web para Sistema de Taxis Distribuido
============================================

Interfaz web simple para monitorear el estado del sistema distribuido
usando Flask y conexión a OpenFire para estadísticas en tiempo real.
"""

from flask import Flask, render_template, jsonify, request
import requests
import json
import time
from datetime import datetime
import os

app = Flask(__name__)

# Configuración
OPENFIRE_HOST = os.getenv('OPENFIRE_HOST', 'localhost')
OPENFIRE_PORT = os.getenv('OPENFIRE_PORT', '9090')
OPENFIRE_DOMAIN = os.getenv('OPENFIRE_DOMAIN', 'localhost')

class TaxiSystemMonitor:
    """Monitor del sistema de taxis distribuido"""
    
    def __init__(self):
        self.openfire_base_url = f"http://{OPENFIRE_HOST}:{OPENFIRE_PORT}/plugins/restapi/v1"
        self.stats = {
            'hosts': {},
            'total_users': 0,
            'online_users': 0,
            'last_update': time.time()
        }
    
    def get_openfire_stats(self):
        """Obtiene estadísticas de OpenFire"""
        try:
            # Obtener usuarios totales
            users_response = requests.get(f"{self.openfire_base_url}/users")
            if users_response.status_code == 200:
                users_data = users_response.json()
                self.stats['total_users'] = len(users_data.get('users', []))
            
            # Obtener usuarios en línea
            sessions_response = requests.get(f"{self.openfire_base_url}/sessions")
            if sessions_response.status_code == 200:
                sessions_data = sessions_response.json()
                self.stats['online_users'] = len(sessions_data.get('sessions', []))
                
                # Analizar tipos de hosts conectados
                hosts = {}
                for session in sessions_data.get('sessions', []):
                    username = session.get('username', '')
                    if 'coordinator' in username:
                        hosts['coordinator'] = hosts.get('coordinator', 0) + 1
                    elif 'taxi_host' in username:
                        hosts['taxi_hosts'] = hosts.get('taxi_hosts', 0) + 1
                    elif 'passenger_host' in username:
                        hosts['passenger_hosts'] = hosts.get('passenger_hosts', 0) + 1
                
                self.stats['hosts'] = hosts
            
            self.stats['last_update'] = time.time()
            return True
            
        except Exception as e:
            print(f"Error obteniendo estadísticas de OpenFire: {e}")
            return False
    
    def get_system_health(self):
        """Evalúa la salud del sistema"""
        if time.time() - self.stats['last_update'] > 30:  # Datos antiguos
            return 'unknown'
        
        if self.stats['online_users'] == 0:
            return 'down'
        elif self.stats['hosts'].get('coordinator', 0) == 0:
            return 'degraded'
        elif self.stats['online_users'] < 3:  # Menos de 3 agentes
            return 'warning'
        else:
            return 'healthy'

# Instancia global del monitor
monitor = TaxiSystemMonitor()

@app.route('/')
def index():
    """Página principal del monitor"""
    return render_template('monitor.html')

@app.route('/api/stats')
def api_stats():
    """API endpoint para estadísticas"""
    monitor.get_openfire_stats()
    
    stats_data = {
        **monitor.stats,
        'system_health': monitor.get_system_health(),
        'timestamp': datetime.now().isoformat(),
        'openfire_config': {
            'host': OPENFIRE_HOST,
            'port': OPENFIRE_PORT,
            'domain': OPENFIRE_DOMAIN
        }
    }
    
    return jsonify(stats_data)

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    health = monitor.get_system_health()
    return jsonify({
        'status': health,
        'timestamp': datetime.now().isoformat()
    })

# Template HTML embebido
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor Sistema de Taxis Distribuido</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; text-align: center; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; margin: 10px 0; }
        .status-healthy { color: #27ae60; }
        .status-warning { color: #f39c12; }
        .status-degraded { color: #e74c3c; }
        .status-down { color: #8b0000; }
        .status-unknown { color: #7f8c8d; }
        .refresh-btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .refresh-btn:hover { background: #2980b9; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }
        .config-info { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚕 Monitor Sistema de Taxis Distribuido</h1>
            <button class="refresh-btn" onclick="updateStats()">🔄 Actualizar</button>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 Estado del Sistema</h3>
                <div id="system-health" class="stat-value">Cargando...</div>
                <div id="last-update" class="timestamp"></div>
            </div>
            
            <div class="stat-card">
                <h3>👥 Usuarios OpenFire</h3>
                <div class="stat-value">
                    <span id="online-users">0</span> / <span id="total-users">0</span>
                </div>
                <div>En línea / Total</div>
            </div>
            
            <div class="stat-card">
                <h3>🎯 Coordinador</h3>
                <div id="coordinator-count" class="stat-value">0</div>
                <div>Instancias activas</div>
            </div>
            
            <div class="stat-card">
                <h3>🚖 Hosts de Taxis</h3>
                <div id="taxi-hosts-count" class="stat-value">0</div>
                <div>Hosts conectados</div>
            </div>
            
            <div class="stat-card">
                <h3>👥 Hosts de Pasajeros</h3>
                <div id="passenger-hosts-count" class="stat-value">0</div>
                <div>Hosts conectados</div>
            </div>
        </div>
        
        <div class="config-info">
            <h3>⚙️ Configuración OpenFire</h3>
            <div id="openfire-config">Cargando configuración...</div>
        </div>
    </div>

    <script>
        function updateStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // Estado del sistema
                    const healthElement = document.getElementById('system-health');
                    healthElement.textContent = getHealthText(data.system_health);
                    healthElement.className = 'stat-value status-' + data.system_health;
                    
                    // Usuarios
                    document.getElementById('online-users').textContent = data.online_users;
                    document.getElementById('total-users').textContent = data.total_users;
                    
                    // Hosts
                    document.getElementById('coordinator-count').textContent = data.hosts.coordinator || 0;
                    document.getElementById('taxi-hosts-count').textContent = data.hosts.taxi_hosts || 0;
                    document.getElementById('passenger-hosts-count').textContent = data.hosts.passenger_hosts || 0;
                    
                    // Timestamp
                    document.getElementById('last-update').textContent = 
                        'Última actualización: ' + new Date(data.timestamp).toLocaleString();
                    
                    // Configuración OpenFire
                    document.getElementById('openfire-config').innerHTML = 
                        `<strong>Host:</strong> ${data.openfire_config.host}:${data.openfire_config.port}<br>
                         <strong>Dominio:</strong> ${data.openfire_config.domain}`;
                })
                .catch(error => {
                    console.error('Error actualizando estadísticas:', error);
                    document.getElementById('system-health').textContent = 'Error de conexión';
                    document.getElementById('system-health').className = 'stat-value status-unknown';
                });
        }
        
        function getHealthText(health) {
            const healthTexts = {
                'healthy': '✅ Saludable',
                'warning': '⚠️ Advertencia',
                'degraded': '🔸 Degradado',
                'down': '❌ Inactivo',
                'unknown': '❓ Desconocido'
            };
            return healthTexts[health] || '❓ Desconocido';
        }
        
        // Actualizar cada 5 segundos
        setInterval(updateStats, 5000);
        
        // Actualización inicial
        updateStats();
    </script>
</body>
</html>
'''

# Crear directorio de templates si no existe
import os
if not os.path.exists('templates'):
    os.makedirs('templates')

# Escribir template
with open('templates/monitor.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    print(f"🌐 Iniciando monitor web en puerto 8080")
    print(f"📍 OpenFire: {OPENFIRE_HOST}:{OPENFIRE_PORT}")
    print(f"🔗 Acceder a: http://localhost:8080")
    
    app.run(host='0.0.0.0', port=8080, debug=False)
