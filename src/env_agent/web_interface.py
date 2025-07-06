"""
Web interface for the ideological agent system using Flask and WebSockets
"""

import json
import logging
import threading
import time
from typing import Dict, Any, Optional
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

from agent.gui_agent import get_gui_agent
from config import config

logger = logging.getLogger(__name__)

class WebInterface:
    """Flask-based web interface for the ideological agent system with WebSocket support"""
    
    def __init__(self):
        self.app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
        self.app.config['SECRET_KEY'] = 'ideological_agents_secret_key'
        
        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        self.setup_routes()
        self.setup_socketio()
        
        # Data cache and update thread
        self.last_system_state = {}
        self.update_thread = None
        self.running = False
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/api/system_state')
        def get_system_state():
            """Get current system state"""
            gui_agent = get_gui_agent()
            if gui_agent:
                return jsonify(gui_agent.get_system_state())
            else:
                return jsonify({
                    "agents": [],
                    "communities": [],
                    "stats": {
                        "total_agents": 0,
                        "total_communities": 0,
                        "ideology_distribution": {},
                        "conflicts": 0,
                        "ideology_changes": 0,
                        "last_updated": time.time()
                    },
                    "grid_config": {
                        "width": config.grid_width,
                        "height": config.grid_height,
                        "ideologies": config.ideologies or ['red', 'blue', 'green']
                    }
                })
        
        @self.app.route('/api/stats')
        def get_stats():
            """Get system statistics"""
            gui_agent = get_gui_agent()
            if gui_agent:
                return jsonify(gui_agent.system_stats)
            else:
                return jsonify({
                    "total_agents": 0,
                    "total_communities": 0,
                    "ideology_distribution": {},
                    "conflicts": 0,
                    "ideology_changes": 0,
                    "last_updated": time.time()
                })
        
        @self.app.route('/api/config')
        def get_config():
            """Get system configuration"""
            return jsonify({
                "grid_width": config.grid_width,
                "grid_height": config.grid_height,
                "ideologies": config.ideologies or ['red', 'blue', 'green'],
                "influence_radius": config.influence_radius,
                "ideology_change_threshold": config.ideology_change_threshold,
                "max_community_size": config.max_community_size,
                "min_community_size": config.min_community_size
            })
    
    def setup_socketio(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info("Client connected to WebSocket")
            # Send initial system state
            self.emit_system_state()
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info("Client disconnected from WebSocket")
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """Handle manual update request"""
            self.emit_system_state()
    
    def emit_system_state(self):
        """Emit current system state to all connected clients"""
        try:
            gui_agent = get_gui_agent()
            if gui_agent:
                state_data = gui_agent.get_system_state()
            else:
                state_data = {
                    "agents": [],
                    "communities": [],
                    "stats": {
                        "total_agents": 0,
                        "total_communities": 0,
                        "ideology_distribution": {},
                        "conflicts": 0,
                        "ideology_changes": 0,
                        "last_updated": time.time()
                    },
                    "grid_config": {
                        "width": config.grid_width,
                        "height": config.grid_height,
                        "ideologies": config.ideologies or ['red', 'blue', 'green']
                    }
                }
            
            self.socketio.emit('system_state_update', state_data)
            self.last_system_state = state_data
            
        except Exception as e:
            logger.error(f"Error emitting system state: {e}")
    
    def start_update_thread(self):
        """Start the background thread for sending periodic updates"""
        if self.update_thread is None or not self.update_thread.is_alive():
            self.running = True
            self.update_thread = threading.Thread(target=self._update_worker, daemon=True)
            self.update_thread.start()
            logger.info("Update thread started")
    
    def stop_update_thread(self):
        """Stop the background update thread"""
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
            logger.info("Update thread stopped")
    
    def _update_worker(self):
        """Background worker that sends updates every second"""
        while self.running:
            try:
                self.emit_system_state()
                time.sleep(1)  # Send updates every second
            except Exception as e:
                logger.error(f"Error in update worker: {e}")
                time.sleep(1)  # Continue even if there's an error
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False):
        """Run the web interface with SocketIO"""
        host = host or config.web_host
        port = port or config.web_port
        
        logger.info(f"Starting web interface with WebSockets on {host}:{port}")
        
        # Start the update thread
        self.start_update_thread()
        
        try:
            # Run the SocketIO app
            self.socketio.run(self.app, host=host, port=port, debug=debug)
        finally:
            # Stop the update thread when shutting down
            self.stop_update_thread()

# Global web interface instance
web_interface_instance: Optional[WebInterface] = None

def create_web_interface() -> WebInterface:
    """Create the web interface"""
    global web_interface_instance
    
    if web_interface_instance is None:
        web_interface_instance = WebInterface()
    
    return web_interface_instance

def get_web_interface() -> Optional[WebInterface]:
    """Get the web interface instance"""
    return web_interface_instance
