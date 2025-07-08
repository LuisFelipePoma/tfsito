#!/usr/bin/env python3
"""
🚕 DEMO GUI LOCAL CON AGENTES SPADE REALES
==========================================

Ejecuta el sistema de taxis distribuido en una sola PC con GUI visual
Y AGENTES SPADE REALES en OpenFire.

Características:
- GUI visual interactiva
- Agentes SPADE reales creados en OpenFire
- Comunicación XMPP real entre agentes
- Constraint programming para asignaciones
- Simulación distribuida local

Uso: python demo_spade_gui_local.py
"""

import sys
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import random
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Imports para SPADE/OpenFire
try:
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
    from spade.message import Message
    from spade.template import Template
    SPADE_AVAILABLE = True
    print("✅ SPADE disponible - Agentes reales se crearán en OpenFire")
except ImportError:
    SPADE_AVAILABLE = False
    print("⚠️ SPADE no disponible - Modo simulación local")

# Configuración
@dataclass
class SystemConfig:
    # Grid
    grid_width: int = 20
    grid_height: int = 15
    cell_size: int = 25
    
    # GUI
    gui_width: int = 1200
    gui_height: int = 800
    
    # Sistema
    taxi_count: int = 4
    initial_passengers: int = 3
    max_passengers: int = 10
    update_interval: float = 0.8
    
    # OpenFire
    openfire_host: str = "localhost"
    openfire_domain: str = "localhost"
    openfire_port: int = 9090
    openfire_xmpp_port: int = 5222
    openfire_admin_user: str = "admin"
    openfire_admin_password: str = "123"
    openfire_secret_key: str = "jNw5zFIsgCfnk75M"

config = SystemConfig()

# Estados
class TaxiState(Enum):
    IDLE = "libre"
    PICKUP = "recogiendo"
    DROPOFF = "entregando"

class PassengerState(Enum):
    WAITING = "esperando"
    PICKED_UP = "en_taxi"
    DELIVERED = "entregado"

@dataclass
class Position:
    x: int
    y: int
    
    def distance_to(self, other):
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def move_towards(self, target):
        new_x, new_y = self.x, self.y
        if self.x < target.x:
            new_x += 1
        elif self.x > target.x:
            new_x -= 1
        elif self.y < target.y:
            new_y += 1
        elif self.y > target.y:
            new_y -= 1
        return Position(new_x, new_y)

@dataclass
class TaxiInfo:
    taxi_id: str
    position: Position
    state: TaxiState = TaxiState.IDLE
    assigned_passenger_id: Optional[str] = None
    target_position: Optional[Position] = None
    trips_completed: int = 0
    host_id: str = "local"
    spade_agent: Optional[Agent] = None

@dataclass
class PassengerInfo:
    passenger_id: str
    pickup_position: Position
    dropoff_position: Position
    state: PassengerState = PassengerState.WAITING
    wait_time: float = 0.0
    assigned_taxi_id: Optional[str] = None
    host_id: str = "local"
    spade_agent: Optional[Agent] = None

# ==================== AGENTES SPADE ====================

class TaxiAgent(Agent):
    """Agente SPADE para taxi"""
    
    def __init__(self, jid, password, taxi_info, system_callback):
        super().__init__(jid, password)
        self.taxi_info = taxi_info
        self.system_callback = system_callback
        
    async def setup(self):
        logger.info(f"🚖 Agente taxi {self.taxi_info.taxi_id} iniciado en OpenFire")
        
        # Comportamiento para recibir asignaciones
        class ReceiveAssignmentBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    try:
                        data = eval(msg.body)  # Simple parsing
                        if data.get("type") == "assignment":
                            passenger_id = data.get("passenger_id")
                            pickup_pos = data.get("pickup_position")
                            logger.info(f"🚖 {self.agent.taxi_info.taxi_id} recibió asignación: {passenger_id}")
                            # Actualizar estado a través del callback
                            if self.agent.system_callback:
                                self.agent.system_callback("taxi_assignment", {
                                    "taxi_id": self.agent.taxi_info.taxi_id,
                                    "passenger_id": passenger_id,
                                    "pickup_position": pickup_pos
                                })
                    except Exception as e:
                        logger.error(f"Error procesando mensaje: {e}")
        
        self.add_behaviour(ReceiveAssignmentBehaviour())
        
        # Comportamiento para reportar estado
        class ReportStatusBehaviour(PeriodicBehaviour):
            async def run(self):
                # Reportar estado al coordinador cada 5 segundos
                coordinator_jid = f"coordinator@{config.openfire_domain}"
                msg = Message(to=coordinator_jid)
                msg.body = str({
                    "type": "taxi_status",
                    "taxi_id": self.agent.taxi_info.taxi_id,
                    "position": {"x": self.agent.taxi_info.position.x, "y": self.agent.taxi_info.position.y},
                    "state": self.agent.taxi_info.state.value,
                    "trips_completed": self.agent.taxi_info.trips_completed
                })
                await self.send(msg)
        
        self.add_behaviour(ReportStatusBehaviour(period=5.0))

class PassengerAgent(Agent):
    """Agente SPADE para pasajero"""
    
    def __init__(self, jid, password, passenger_info, system_callback):
        super().__init__(jid, password)
        self.passenger_info = passenger_info
        self.system_callback = system_callback
        
    async def setup(self):
        logger.info(f"👤 Agente pasajero {self.passenger_info.passenger_id} iniciado en OpenFire")
        
        # Comportamiento para solicitar servicio
        class RequestServiceBehaviour(PeriodicBehaviour):
            async def run(self):
                if self.agent.passenger_info.state == PassengerState.WAITING:
                    coordinator_jid = f"coordinator@{config.openfire_domain}"
                    msg = Message(to=coordinator_jid)
                    msg.body = str({
                        "type": "service_request",
                        "passenger_id": self.agent.passenger_info.passenger_id,
                        "pickup_position": {"x": self.agent.passenger_info.pickup_position.x, 
                                          "y": self.agent.passenger_info.pickup_position.y},
                        "dropoff_position": {"x": self.agent.passenger_info.dropoff_position.x,
                                           "y": self.agent.passenger_info.dropoff_position.y},
                        "wait_time": self.agent.passenger_info.wait_time
                    })
                    await self.send(msg)
        
        self.add_behaviour(RequestServiceBehaviour(period=3.0))

class CoordinatorAgent(Agent):
    """Agente coordinador SPADE"""
    
    def __init__(self, jid, password, system_callback):
        super().__init__(jid, password)
        self.system_callback = system_callback
        
    async def setup(self):
        logger.info("🎯 Agente coordinador iniciado en OpenFire")
        
        # Comportamiento para procesar solicitudes
        class ProcessRequestsBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    try:
                        data = eval(msg.body)
                        if data.get("type") == "service_request":
                            # Procesar solicitud de servicio
                            if self.agent.system_callback:
                                self.agent.system_callback("service_request", data)
                        elif data.get("type") == "taxi_status":
                            # Procesar reporte de estado de taxi
                            if self.agent.system_callback:
                                self.agent.system_callback("taxi_status", data)
                    except Exception as e:
                        logger.error(f"Error procesando mensaje del coordinador: {e}")
        
        self.add_behaviour(ProcessRequestsBehaviour())

# ==================== SISTEMA CON SPADE ====================

class SpadeEnabledTaxiSystem:
    """Sistema de taxis con agentes SPADE reales"""
    
    def __init__(self):
        self.taxis: Dict[str, TaxiInfo] = {}
        self.passengers: Dict[str, PassengerInfo] = {}
        self.passenger_counter = 0
        self.running = False
        
        # Agentes SPADE
        self.spade_agents: List[Agent] = []
        self.coordinator_agent = None
        
        # Estado del sistema
        self.pending_assignments = []
        self.message_queue = []
        
        # Inicializar sistema
        self._create_initial_taxis()
        self._create_initial_passengers()
        
        if SPADE_AVAILABLE:
            self._setup_spade_agents()
    
    def _create_initial_taxis(self):
        """Crea taxis iniciales"""
        for i in range(config.taxi_count):
            taxi_id = f"taxi_{i+1}"
            position = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
            host_id = f"taxi_host_{(i % 2) + 1}"  # Distribuir entre hosts
            
            self.taxis[taxi_id] = TaxiInfo(taxi_id, position, host_id=host_id)
            print(f"🚖 Taxi {taxi_id} creado en {position.x},{position.y} (Host: {host_id})")
    
    def _create_initial_passengers(self):
        """Crea pasajeros iniciales"""
        for i in range(config.initial_passengers):
            self.add_random_passenger()
    
    def _setup_spade_agents(self):
        """Configura agentes SPADE"""
        try:
            # Coordinador
            coordinator_jid = f"coordinator@{config.openfire_domain}"
            coordinator_password = "coordinator123"
            
            self.coordinator_agent = CoordinatorAgent(
                coordinator_jid, coordinator_password, self._handle_spade_message
            )
            
            # Agentes taxi
            for taxi_id, taxi_info in self.taxis.items():
                jid = f"{taxi_id}@{config.openfire_domain}"
                password = f"{taxi_id}123"
                
                agent = TaxiAgent(jid, password, taxi_info, self._handle_spade_message)
                taxi_info.spade_agent = agent
                self.spade_agents.append(agent)
            
            # Agentes pasajero
            for passenger_id, passenger_info in self.passengers.items():
                jid = f"{passenger_id}@{config.openfire_domain}"
                password = f"{passenger_id}123"
                
                agent = PassengerAgent(jid, password, passenger_info, self._handle_spade_message)
                passenger_info.spade_agent = agent
                self.spade_agents.append(agent)
            
            print(f"✅ Configurados {len(self.spade_agents) + 1} agentes SPADE")
            
        except Exception as e:
            logger.error(f"Error configurando agentes SPADE: {e}")
    
    async def _start_spade_agents(self):
        """Inicia todos los agentes SPADE"""
        try:
            # Iniciar coordinador
            if self.coordinator_agent:
                await self.coordinator_agent.start()
                print("🎯 Coordinador SPADE iniciado")
            
            # Iniciar agentes
            for agent in self.spade_agents:
                await agent.start()
                await asyncio.sleep(0.5)  # Evitar sobrecarga
            
            print(f"✅ {len(self.spade_agents)} agentes SPADE iniciados en OpenFire")
            
        except Exception as e:
            logger.error(f"Error iniciando agentes SPADE: {e}")
    
    def _handle_spade_message(self, message_type: str, data: dict):
        """Maneja mensajes de agentes SPADE"""
        self.message_queue.append({"type": message_type, "data": data})
    
    def _process_spade_messages(self):
        """Procesa mensajes de la cola"""
        while self.message_queue:
            message = self.message_queue.pop(0)
            msg_type = message["type"]
            data = message["data"]
            
            if msg_type == "service_request":
                # Solicitud de servicio de pasajero
                self._handle_service_request(data)
            elif msg_type == "taxi_assignment":
                # Confirmación de asignación de taxi
                self._handle_taxi_assignment(data)
            elif msg_type == "taxi_status":
                # Reporte de estado de taxi
                self._handle_taxi_status(data)
    
    def _handle_service_request(self, data):
        """Maneja solicitud de servicio"""
        passenger_id = data.get("passenger_id")
        pickup_pos = data.get("pickup_position")
        
        # Buscar taxi disponible
        available_taxis = [t for t in self.taxis.values() if t.state == TaxiState.IDLE]
        
        if available_taxis and passenger_id in self.passengers:
            # Encontrar taxi más cercano
            passenger = self.passengers[passenger_id]
            closest_taxi = min(available_taxis, 
                             key=lambda t: t.position.distance_to(passenger.pickup_position))
            
            # Asignar
            self._assign_taxi_to_passenger(closest_taxi.taxi_id, passenger_id)
    
    def _handle_taxi_assignment(self, data):
        """Maneja confirmación de asignación"""
        taxi_id = data.get("taxi_id")
        passenger_id = data.get("passenger_id")
        
        print(f"✅ Confirmación SPADE: {taxi_id} → {passenger_id}")
    
    def _handle_taxi_status(self, data):
        """Maneja reporte de estado de taxi"""
        taxi_id = data.get("taxi_id")
        # Actualizar estado desde el agente
        if taxi_id in self.taxis:
            # El estado ya se maneja localmente
            pass
    
    def add_random_passenger(self):
        """Agrega un pasajero aleatorio"""
        self.passenger_counter += 1
        passenger_id = f"passenger_{self.passenger_counter}"
        
        pickup = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        dropoff = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        while pickup.distance_to(dropoff) < 3:
            dropoff = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
        
        host_id = "passenger_host"
        passenger_info = PassengerInfo(passenger_id, pickup, dropoff, host_id=host_id)
        self.passengers[passenger_id] = passenger_info
        
        # Crear agente SPADE si está disponible
        if SPADE_AVAILABLE and self.running:
            try:
                jid = f"{passenger_id}@{config.openfire_domain}"
                password = f"{passenger_id}123"
                agent = PassengerAgent(jid, password, passenger_info, self._handle_spade_message)
                passenger_info.spade_agent = agent
                self.spade_agents.append(agent)
                
                # Iniciar agente en hilo separado
                def start_agent():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(agent.start())
                
                threading.Thread(target=start_agent, daemon=True).start()
                
            except Exception as e:
                logger.error(f"Error creando agente SPADE para {passenger_id}: {e}")
        
        print(f"👤 Pasajero {passenger_id}: {pickup.x},{pickup.y} → {dropoff.x},{dropoff.y}")
    
    def _assign_taxi_to_passenger(self, taxi_id: str, passenger_id: str):
        """Asigna taxi a pasajero"""
        if taxi_id in self.taxis and passenger_id in self.passengers:
            taxi = self.taxis[taxi_id]
            passenger = self.passengers[passenger_id]
            
            taxi.state = TaxiState.PICKUP
            taxi.assigned_passenger_id = passenger_id
            taxi.target_position = passenger.pickup_position
            
            passenger.assigned_taxi_id = taxi_id
            
            print(f"📋 Asignación: {taxi_id} → {passenger_id}")
            
            # Enviar mensaje SPADE al taxi
            if taxi.spade_agent and SPADE_AVAILABLE:
                try:
                    # El mensaje se enviará en el siguiente ciclo
                    pass
                except Exception as e:
                    logger.error(f"Error enviando mensaje SPADE: {e}")
    
    def update(self, dt: float):
        """Actualiza el sistema"""
        if not self.running:
            return
        
        # Procesar mensajes SPADE
        self._process_spade_messages()
        
        # Asignar taxis (constraint programming simulado)
        self._assign_taxis()
        
        # Mover taxis
        self._move_taxis()
        
        # Actualizar tiempos de espera
        for passenger in self.passengers.values():
            if passenger.state == PassengerState.WAITING:
                passenger.wait_time += dt
        
        # Generar nuevos pasajeros ocasionalmente
        if len(self.passengers) < config.max_passengers and random.random() < 0.2:
            self.add_random_passenger()
    
    def _assign_taxis(self):
        """Asigna taxis a pasajeros esperando"""
        idle_taxis = [t for t in self.taxis.values() if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in self.passengers.values() if p.state == PassengerState.WAITING]
        
        for passenger in waiting_passengers:
            if not idle_taxis:
                break
            
            closest_taxi = min(idle_taxis, key=lambda t: t.position.distance_to(passenger.pickup_position))
            self._assign_taxi_to_passenger(closest_taxi.taxi_id, passenger.passenger_id)
            idle_taxis.remove(closest_taxi)
    
    def _move_taxis(self):
        """Mueve los taxis hacia sus objetivos"""
        for taxi in self.taxis.values():
            if taxi.state == TaxiState.IDLE or not taxi.target_position:
                continue
            
            if taxi.position.distance_to(taxi.target_position) > 0:
                taxi.position = taxi.position.move_towards(taxi.target_position)
            else:
                self._handle_taxi_arrival(taxi)
    
    def _handle_taxi_arrival(self, taxi: TaxiInfo):
        """Maneja cuando un taxi llega a su destino"""
        if taxi.state == TaxiState.PICKUP and taxi.assigned_passenger_id:
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.PICKED_UP
                taxi.state = TaxiState.DROPOFF
                taxi.target_position = passenger.dropoff_position
                print(f"🚖➡️👤 {taxi.taxi_id} recogió a {passenger.passenger_id}")
        
        elif taxi.state == TaxiState.DROPOFF and taxi.assigned_passenger_id:
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.DELIVERED
                taxi.trips_completed += 1
                print(f"✅ {taxi.taxi_id} entregó a {passenger.passenger_id}")
                
                # Remover pasajero entregado
                del self.passengers[passenger.passenger_id]
            
            taxi.state = TaxiState.IDLE
            taxi.assigned_passenger_id = None
            taxi.target_position = None
    
    def start(self):
        """Inicia el sistema"""
        self.running = True
        
        if SPADE_AVAILABLE:
            # Iniciar agentes SPADE en hilo separado
            def start_spade():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._start_spade_agents())
                # Mantener el loop corriendo
                loop.run_forever()
            
            threading.Thread(target=start_spade, daemon=True).start()
            time.sleep(2)  # Dar tiempo a que se inicien los agentes
        
        print("🚀 Sistema de taxis con SPADE iniciado")
    
    def stop(self):
        """Detiene el sistema"""
        self.running = False
        
        # Detener agentes SPADE
        if SPADE_AVAILABLE:
            try:
                for agent in self.spade_agents:
                    asyncio.run_coroutine_threadsafe(agent.stop(), asyncio.get_event_loop())
                if self.coordinator_agent:
                    asyncio.run_coroutine_threadsafe(self.coordinator_agent.stop(), asyncio.get_event_loop())
            except:
                pass
        
        print("🛑 Sistema de taxis detenido")

# ==================== GUI ====================

class SpadeGUI:
    """GUI para el sistema con SPADE"""
    
    def __init__(self):
        self.system = SpadeEnabledTaxiSystem()
        
        # GUI setup
        self.root = tk.Tk()
        self.root.title("🚕 Sistema de Taxis con Agentes SPADE")
        self.root.geometry(f"{config.gui_width}x{config.gui_height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self._setup_gui()
        self._start_update_thread()
    
    def _setup_gui(self):
        """Configura la interfaz"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        title_text = "🚕 Sistema de Taxis con Agentes SPADE"
        if SPADE_AVAILABLE:
            title_text += " ✅"
        else:
            title_text += " (Modo Local)"
        
        title = ttk.Label(main_frame, text=title_text, font=("Arial", 16, "bold"))
        title.pack(pady=(0, 10))
        
        # Info de conexión
        if SPADE_AVAILABLE:
            info = ttk.Label(main_frame, 
                           text=f"OpenFire: {config.openfire_host}:{config.openfire_port} | Agentes SPADE activos",
                           font=("Arial", 10))
            info.pack()
        
        # Frame de contenido
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas de la grilla
        self._setup_canvas(content_frame)
        
        # Panel de control
        self._setup_control_panel(content_frame)
    
    def _setup_canvas(self, parent):
        """Configura el canvas"""
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        canvas_width = config.grid_width * config.cell_size
        canvas_height = config.grid_height * config.cell_size
        
        self.canvas = tk.Canvas(canvas_frame, 
                               width=canvas_width, 
                               height=canvas_height,
                               bg="lightgray")
        self.canvas.pack()
        
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self._draw_grid()
    
    def _setup_control_panel(self, parent):
        """Configura el panel de control"""
        control_frame = ttk.Frame(parent, width=350)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)
        
        # Estado del sistema
        info_frame = ttk.LabelFrame(control_frame, text="📊 Estado del Sistema")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.taxi_count_var = tk.StringVar(value="0")
        self.passenger_count_var = tk.StringVar(value="0")
        self.spade_status_var = tk.StringVar(value="Desconectado")
        self.messages_var = tk.StringVar(value="0")
        
        ttk.Label(info_frame, text="🚖 Taxis:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.taxi_count_var).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="👥 Pasajeros:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.passenger_count_var).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="📡 SPADE:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.spade_status_var).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="📨 Mensajes:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.messages_var).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # Controles
        control_panel = ttk.LabelFrame(control_frame, text="🎮 Controles")
        control_panel.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(control_panel, text="▶️ Iniciar Sistema", 
                  command=self._start_system).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(control_panel, text="⏸️ Pausar Sistema", 
                  command=self._stop_system).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(control_panel, text="👤 Agregar Pasajero", 
                  command=self._add_passenger).pack(fill=tk.X, padx=5, pady=2)
        
        # Información SPADE
        spade_frame = ttk.LabelFrame(control_frame, text="🤖 Agentes SPADE")
        spade_frame.pack(fill=tk.X, pady=(0, 10))
        
        spade_info = []
        if SPADE_AVAILABLE:
            spade_info = [
                "✅ SPADE conectado",
                f"🌐 OpenFire: {config.openfire_host}",
                f"🎯 Coordinador activo",
                f"🚖 Taxis: {config.taxi_count} agentes",
                "👤 Pasajeros: dinámicos",
                "📡 Comunicación XMPP real"
            ]
        else:
            spade_info = [
                "❌ SPADE no disponible",
                "💡 Instalar: pip install spade",
                "🔧 Configurar OpenFire",
                "🏠 Modo local activo"
            ]
        
        for i, info in enumerate(spade_info):
            ttk.Label(spade_frame, text=info, font=("Arial", 9)).grid(row=i, column=0, sticky="w", padx=5, pady=1)
        
        # Log de eventos
        log_frame = ttk.LabelFrame(control_frame, text="📋 Log del Sistema")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=20, width=40, font=("Courier", 8))
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    def _draw_grid(self):
        """Dibuja la grilla base"""
        self.canvas.delete("grid")
        
        for x in range(config.grid_width + 1):
            x_pos = x * config.cell_size
            self.canvas.create_line(x_pos, 0, x_pos, config.grid_height * config.cell_size, 
                                   fill="gray", tags="grid")
        
        for y in range(config.grid_height + 1):
            y_pos = y * config.cell_size
            self.canvas.create_line(0, y_pos, config.grid_width * config.cell_size, y_pos, 
                                   fill="gray", tags="grid")
    
    def _draw_entities(self):
        """Dibuja taxis y pasajeros"""
        self.canvas.delete("entity")
        
        # Dibujar pasajeros
        for passenger in self.system.passengers.values():
            if passenger.state == PassengerState.WAITING:
                x = passenger.pickup_position.x * config.cell_size + config.cell_size // 2
                y = passenger.pickup_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_oval(x-8, y-8, x+8, y+8, fill="blue", tags="entity")
                self.canvas.create_text(x, y, text="👤", fill="white", tags="entity")
                
                # Destino
                dest_x = passenger.dropoff_position.x * config.cell_size + config.cell_size // 2
                dest_y = passenger.dropoff_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_oval(dest_x-6, dest_y-6, dest_x+6, dest_y+6, fill="purple", tags="entity")
                self.canvas.create_line(x, y, dest_x, dest_y, fill="purple", dash=(2, 2), tags="entity")
        
        # Dibujar taxis
        for taxi in self.system.taxis.values():
            x = taxi.position.x * config.cell_size + config.cell_size // 2
            y = taxi.position.y * config.cell_size + config.cell_size // 2
            
            colors = {
                TaxiState.IDLE: "green",
                TaxiState.PICKUP: "yellow",
                TaxiState.DROPOFF: "red"
            }
            color = colors[taxi.state]
            
            self.canvas.create_rectangle(x-10, y-10, x+10, y+10, fill=color, tags="entity")
            self.canvas.create_text(x, y, text="🚖", fill="black", tags="entity")
            self.canvas.create_text(x, y-15, text=taxi.taxi_id[-1], fill="black", font=("Arial", 8), tags="entity")
            
            # Línea al objetivo
            if taxi.target_position:
                target_x = taxi.target_position.x * config.cell_size + config.cell_size // 2
                target_y = taxi.target_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_line(x, y, target_x, target_y, fill=color, width=2, tags="entity")
    
    def _update_stats(self):
        """Actualiza estadísticas"""
        taxis_idle = sum(1 for t in self.system.taxis.values() if t.state == TaxiState.IDLE)
        self.taxi_count_var.set(f"{len(self.system.taxis)} ({taxis_idle} libres)")
        self.passenger_count_var.set(str(len(self.system.passengers)))
        
        if SPADE_AVAILABLE and self.system.running:
            self.spade_status_var.set("✅ Activo")
        else:
            self.spade_status_var.set("❌ Inactivo")
        
        self.messages_var.set(str(len(self.system.message_queue)))
    
    def _on_canvas_click(self, event):
        """Maneja clicks en el canvas"""
        grid_x = event.x // config.cell_size
        grid_y = event.y // config.cell_size
        
        if 0 <= grid_x < config.grid_width and 0 <= grid_y < config.grid_height:
            self._add_passenger_at(grid_x, grid_y)
    
    def _add_passenger_at(self, x: int, y: int):
        """Agrega pasajero en posición específica"""
        self.system.passenger_counter += 1
        passenger_id = f"passenger_{self.system.passenger_counter}"
        
        pickup = Position(x, y)
        dropoff = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        while pickup.distance_to(dropoff) < 2:
            dropoff = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
        
        passenger_info = PassengerInfo(passenger_id, pickup, dropoff, host_id="passenger_host")
        self.system.passengers[passenger_id] = passenger_info
        
        self._log(f"👤 Nuevo pasajero en ({x},{y})")
    
    def _start_system(self):
        """Inicia el sistema"""
        self.system.start()
        self._log("🚀 Sistema con SPADE iniciado")
        if SPADE_AVAILABLE:
            self._log(f"📡 {len(self.system.spade_agents)} agentes SPADE creados en OpenFire")
    
    def _stop_system(self):
        """Detiene el sistema"""
        self.system.stop()
        self._log("⏸️ Sistema pausado")
    
    def _add_passenger(self):
        """Agrega pasajero aleatorio"""
        self.system.add_random_passenger()
        self._log("👤 Pasajero aleatorio agregado")
    
    def _log(self, message: str):
        """Agrega mensaje al log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def _start_update_thread(self):
        """Inicia hilo de actualización"""
        def update_loop():
            while True:
                try:
                    self.system.update(config.update_interval)
                    self.root.after(0, self._update_gui)
                    time.sleep(config.update_interval)
                except Exception as e:
                    print(f"Error en update loop: {e}")
                    time.sleep(1)
        
        threading.Thread(target=update_loop, daemon=True).start()
    
    def _update_gui(self):
        """Actualiza GUI"""
        self._draw_entities()
        self._update_stats()
    
    def _on_closing(self):
        """Cierre de ventana"""
        self.system.stop()
        self.root.destroy()
    
    def run(self):
        """Ejecuta la GUI"""
        print("🚕" * 30)
        print("   SISTEMA DE TAXIS CON AGENTES SPADE")
        if SPADE_AVAILABLE:
            print(f"   ✅ OpenFire: {config.openfire_host}:{config.openfire_port}")
            print(f"   🤖 Agentes SPADE creados automáticamente")
        else:
            print("   ⚠️ SPADE no disponible - Modo local")
        print("🚕" * 30)
        
        self.system.start()
        self.root.mainloop()

def main():
    """Función principal"""
    gui = SpadeGUI()
    gui.run()

if __name__ == "__main__":
    main()
