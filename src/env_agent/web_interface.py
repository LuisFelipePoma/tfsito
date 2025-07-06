"""
Web interface for the ideological agent system using Flask
"""

import json
import logging
import threading
import time
from typing import Dict, Any, Optional
from flask import Flask, render_template, jsonify

from agent.gui_agent import get_gui_agent
from config import config

logger = logging.getLogger(__name__)

class WebInterface:
    """Flask-based web interface for the ideological agent system"""
    
    def __init__(self):
        self.app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
        self.app.config['SECRET_KEY'] = 'ideological_agents_secret_key'
        
        self.setup_routes()
        
        # Data cache
        self.last_system_state = {}
        
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
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False):
        """Run the web interface"""
        host = host or config.web_host
        port = port or config.web_port
        
        logger.info(f"Starting web interface on {host}:{port}")
        
        # Run the Flask app
        self.app.run(host=host, port=port, debug=debug, threaded=True)

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
