#!/usr/bin/env python3
"""
Sistema de Despacho de Taxis Unificado
=====================================

Sistema simplificado que puede ejecutarse tanto local como distribuido.
Siempre utiliza agentes reales de OpenFire/SPADE/XMPP.

Modos de ejecución:
- LOCAL: Todos los agentes en una sola máquina
- DISTRIBUTED: Agentes distribuidos en múltiples hosts

Autor: Sistema de Taxis Inteligente
Fecha: 2025
"""

import asyncio
import json
import logging
import random
import time
import argparse
import socket
import threading
import os
import sys
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import uuid

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.patches as patches
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# SPADE imports
try:
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
    from spade.message import Message
    from spade.template import Template
    SPADE_AVAILABLE = True
except ImportError:
    SPADE_AVAILABLE = False

# Local imports
try:
    from src.config import config, taxi_config
    from src.services.openfire_api import openfire_api
except ImportError:
    # Fallback para ejecución directa
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
    from config import config, taxi_config
    from services.openfire_api import openfire_api

# =============================================================================
# CONFIGURACIÓN UNIFICADA
# =============================================================================

@dataclass
class UnifiedConfig:
    """Configuración unificada para el sistema de taxis"""
    
    # OpenFire/XMPP Configuration
    openfire_host: str = "localhost"
    openfire_port: int = 9090
    openfire_admin_user: str = "admin"
    openfire_admin_password: str = "123"
    openfire_domain: str = "localhost"
    openfire_xmpp_port: int = 5222
    openfire_secret_key: str = "jNw5zFIsgCfnk75M"
    
    # Sistema de Taxis
    grid_width: int = 20
    grid_height: int = 20
    num_taxis: int = 3
    num_passengers: int = 5
    simulation_duration: int = 60  # segundos
    
    # Comportamiento de agentes
    taxi_speed: float = 2.0  # segundos por movimiento
    passenger_patience: int = 30  # segundos antes de cancelar
    
    # Distributed mode
    mode: str = "LOCAL"  # LOCAL o DISTRIBUTED
    coordinator_host: str = "localhost"
    remote_hosts: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.remote_hosts is None:
            self.remote_hosts = []

# Configuración global
unified_config = UnifiedConfig()

# =============================================================================
# MODELOS DE DATOS
# =============================================================================

@dataclass
class Position:
    x: int
    y: int
    
    def distance_to(self, other: 'Position') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
    
    def __str__(self):
        return f"({self.x},{self.y})"

class TaxiStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    MOVING_TO_PASSENGER = "moving_to_passenger"
    TRANSPORTING = "transporting"

class PassengerStatus(Enum):
    WAITING = "waiting"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

@dataclass
class TaxiInfo:
    id: str
    position: Position
    status: TaxiStatus
    passenger_id: Optional[str] = None
    destination: Optional[Position] = None
    
class PassengerRequest:
    def __init__(self, id: str, origin: Position, destination: Position):
        self.id = id
        self.origin = origin
        self.destination = destination
        self.status = PassengerStatus.WAITING
        self.assigned_taxi = None
        self.created_at = time.time()

# =============================================================================
# SISTEMA DE COMUNICACIÓN UNIFICADO
# =============================================================================

class MessageType:
    # Coordinador
    TAXI_REGISTER = "taxi_register"
    PASSENGER_REQUEST = "passenger_request"
    ASSIGN_TAXI = "assign_taxi"
    STATUS_UPDATE = "status_update"
    TRIP_COMPLETED = "trip_completed"
    
    # Sistema
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"

class UnifiedMessageBus:
    """Sistema de mensajería unificado que funciona local y distribuido"""
    
    def __init__(self):
        self.subscribers = {}
        self.message_queue = asyncio.Queue()
        self.running = False
        
    async def subscribe(self, agent_id: str, callback):
        """Suscribir un agente para recibir mensajes"""
        self.subscribers[agent_id] = callback
        
    async def publish(self, message: dict):
        """Publicar un mensaje a todos los suscriptores relevantes"""
        await self.message_queue.put(message)
        
    async def start(self):
        """Iniciar el bus de mensajes"""
        self.running = True
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._distribute_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Error en bus de mensajes: {e}")
                
    async def _distribute_message(self, message: dict):
        """Distribuir mensaje a suscriptores relevantes"""
        for agent_id, callback in self.subscribers.items():
            try:
                await callback(message)
            except Exception as e:
                logging.error(f"Error enviando mensaje a {agent_id}: {e}")
                
    def stop(self):
        """Detener el bus de mensajes"""
        self.running = False

# Instancia global del bus de mensajes
message_bus = UnifiedMessageBus()

# =============================================================================
# AGENTES SPADE
# =============================================================================

class CoordinatorAgent(Agent):
    """Agente coordinador que gestiona el sistema de taxis"""
    
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.taxis = {}
        self.passengers = {}
        self.passenger_requests = []
        
    async def setup(self):
        """Configuración inicial del coordinador"""
        logging.info(f"Coordinador iniciado: {self.jid}")
        
        # Comportamiento para gestionar el sistema
        self.add_behaviour(self.CoordinatorBehaviour())
        
        # Registro en el bus de mensajes
        await message_bus.subscribe(str(self.jid), self.handle_message)
        
    class CoordinatorBehaviour(CyclicBehaviour):
        async def run(self):
            """Comportamiento principal del coordinador"""
            
            # Recibir mensajes XMPP
            msg = await self.receive(timeout=1.0)
            if msg:
                await self.agent.handle_xmpp_message(msg)
                
            # Procesar asignaciones pendientes
            await self.agent.process_assignments()
            await asyncio.sleep(1)
            
    async def handle_message(self, message: dict):
        """Manejar mensajes del bus interno"""
        msg_type = message.get('type')
        
        if msg_type == MessageType.TAXI_REGISTER:
            await self.register_taxi(message)
        elif msg_type == MessageType.PASSENGER_REQUEST:
            await self.handle_passenger_request(message)
        elif msg_type == MessageType.STATUS_UPDATE:
            await self.handle_status_update(message)
            
    async def handle_xmpp_message(self, msg):
        """Manejar mensajes XMPP de otros agentes"""
        try:
            data = json.loads(msg.body)
            await self.handle_message(data)
        except Exception as e:
            logging.error(f"Error procesando mensaje XMPP: {e}")
            
    async def register_taxi(self, message: dict):
        """Registrar un nuevo taxi"""
        taxi_id = message['taxi_id']
        position = Position(**message['position'])
        
        self.taxis[taxi_id] = TaxiInfo(
            id=taxi_id,
            position=position,
            status=TaxiStatus.AVAILABLE
        )
        
        logging.info(f"Taxi registrado: {taxi_id} en {position}")
        
    async def handle_passenger_request(self, message: dict):
        """Manejar nueva solicitud de pasajero"""
        request = PassengerRequest(
            id=message['passenger_id'],
            origin=Position(**message['origin']),
            destination=Position(**message['destination'])
        )
        
        self.passenger_requests.append(request)
        logging.info(f"Nueva solicitud de pasajero: {request.id}")
        
    async def process_assignments(self):
        """Procesar asignaciones de taxis a pasajeros"""
        available_taxis = [t for t in self.taxis.values() if t.status == TaxiStatus.AVAILABLE]
        pending_requests = [r for r in self.passenger_requests if r.status == PassengerStatus.WAITING]
        
        for request in pending_requests:
            if not available_taxis:
                break
                
            # Encontrar el taxi más cercano
            best_taxi = min(available_taxis, 
                          key=lambda t: t.position.distance_to(request.origin))
            
            # Asignar taxi
            best_taxi.status = TaxiStatus.MOVING_TO_PASSENGER
            best_taxi.passenger_id = request.id
            best_taxi.destination = request.origin
            
            request.status = PassengerStatus.PICKED_UP
            request.assigned_taxi = best_taxi.id
            
            available_taxis.remove(best_taxi)
            
            # Enviar asignación al taxi
            await self.send_assignment(best_taxi.id, request)
            
            logging.info(f"Taxi {best_taxi.id} asignado a pasajero {request.id}")
            
    async def send_assignment(self, taxi_id: str, request: PassengerRequest):
        """Enviar asignación a un taxi específico"""
        assignment_msg = Message(to=f"{taxi_id}@{unified_config.openfire_domain}")
        assignment_msg.body = json.dumps({
            'type': MessageType.ASSIGN_TAXI,
            'passenger_id': request.id,
            'origin': asdict(request.origin),
            'destination': asdict(request.destination)
        })
        await self.send(assignment_msg)
        
    async def handle_status_update(self, message: dict):
        """Actualizar estado de taxi"""
        taxi_id = message['taxi_id']
        if taxi_id in self.taxis:
            taxi = self.taxis[taxi_id]
            taxi.position = Position(**message['position'])
            if 'status' in message:
                taxi.status = TaxiStatus(message['status'])

class TaxiAgent(Agent):
    """Agente taxi que responde a solicitudes"""
    
    def __init__(self, jid, password, taxi_id: str):
        super().__init__(jid, password)
        self.taxi_id = taxi_id
        self.position = Position(
            random.randint(0, unified_config.grid_width-1),
            random.randint(0, unified_config.grid_height-1)
        )
        self.status = TaxiStatus.AVAILABLE
        self.current_passenger = None
        self.destination = None
        
    async def setup(self):
        """Configuración inicial del taxi"""
        logging.info(f"Taxi {self.taxi_id} iniciado en {self.position}")
        
        # Comportamiento principal
        self.add_behaviour(self.TaxiBehaviour())
        
        # Registrarse con el coordinador
        await self.register_with_coordinator()
        
    async def register_with_coordinator(self):
        """Registrarse con el coordinador"""
        register_msg = Message(to=f"coordinator@{unified_config.openfire_domain}")
        register_msg.body = json.dumps({
            'type': MessageType.TAXI_REGISTER,
            'taxi_id': self.taxi_id,
            'position': asdict(self.position)
        })
        await self.send(register_msg)
        
    class TaxiBehaviour(CyclicBehaviour):
        async def run(self):
            """Comportamiento principal del taxi"""
            
            # Recibir mensajes del coordinador
            msg = await self.receive(timeout=1.0)
            if msg:
                await self.agent.handle_coordinator_message(msg)
                
            # Ejecutar acciones según estado actual
            await self.agent.execute_current_action()
            await asyncio.sleep(unified_config.taxi_speed)
            
    async def handle_coordinator_message(self, msg):
        """Manejar mensajes del coordinador"""
        try:
            data = json.loads(msg.body)
            msg_type = data.get('type')
            
            if msg_type == MessageType.ASSIGN_TAXI:
                await self.handle_assignment(data)
        except Exception as e:
            logging.error(f"Error procesando mensaje coordinador: {e}")
            
    async def handle_assignment(self, data: dict):
        """Manejar asignación de pasajero"""
        self.current_passenger = data['passenger_id']
        self.destination = Position(**data['origin'])
        self.status = TaxiStatus.MOVING_TO_PASSENGER
        
        logging.info(f"Taxi {self.taxi_id} asignado a pasajero {self.current_passenger}")
        
    async def execute_current_action(self):
        """Ejecutar acción según estado actual"""
        if self.status == TaxiStatus.MOVING_TO_PASSENGER and self.destination:
            await self.move_towards(self.destination)
            
            if self.position.x == self.destination.x and self.position.y == self.destination.y:
                self.status = TaxiStatus.TRANSPORTING
                logging.info(f"Taxi {self.taxi_id} recogió pasajero {self.current_passenger}")
                
        elif self.status == TaxiStatus.TRANSPORTING:
            # Simular transporte
            await asyncio.sleep(2)
            self.status = TaxiStatus.AVAILABLE
            self.current_passenger = None
            self.destination = None
            logging.info(f"Taxi {self.taxi_id} completó viaje")
            
        # Enviar actualización de estado
        await self.send_status_update()
        
    async def move_towards(self, target: Position):
        """Mover hacia una posición objetivo"""
        if self.position.x < target.x:
            self.position.x += 1
        elif self.position.x > target.x:
            self.position.x -= 1
        elif self.position.y < target.y:
            self.position.y += 1
        elif self.position.y > target.y:
            self.position.y -= 1
            
    async def send_status_update(self):
        """Enviar actualización de estado al coordinador"""
        update_msg = Message(to=f"coordinator@{unified_config.openfire_domain}")
        update_msg.body = json.dumps({
            'type': MessageType.STATUS_UPDATE,
            'taxi_id': self.taxi_id,
            'position': asdict(self.position),
            'status': self.status.value
        })
        await self.send(update_msg)

class PassengerAgent(Agent):
    """Agente pasajero que genera solicitudes"""
    
    def __init__(self, jid, password, passenger_id: str):
        super().__init__(jid, password)
        self.passenger_id = passenger_id
        
    async def setup(self):
        """Configuración inicial del pasajero"""
        logging.info(f"Pasajero {self.passenger_id} iniciado")
        
        # Comportamiento de solicitud
        self.add_behaviour(self.RequestBehaviour())
        
    class RequestBehaviour(OneShotBehaviour):
        async def run(self):
            """Generar solicitud de taxi"""
            await asyncio.sleep(random.uniform(5, 15))  # Esperar antes de solicitar
            
            origin = Position(
                random.randint(0, unified_config.grid_width-1),
                random.randint(0, unified_config.grid_height-1)
            )
            destination = Position(
                random.randint(0, unified_config.grid_width-1),
                random.randint(0, unified_config.grid_height-1)
            )
            
            # Enviar solicitud al coordinador
            request_msg = Message(to=f"coordinator@{unified_config.openfire_domain}")
            request_msg.body = json.dumps({
                'type': MessageType.PASSENGER_REQUEST,
                'passenger_id': self.agent.passenger_id,
                'origin': asdict(origin),
                'destination': asdict(destination)
            })
            await self.agent.send(request_msg)
            
            logging.info(f"Pasajero {self.agent.passenger_id} solicitó taxi de {origin} a {destination}")

# =============================================================================
# SISTEMA PRINCIPAL UNIFICADO
# =============================================================================

class UnifiedTaxiSystem:
    """Sistema principal que gestiona todo"""
    
    def __init__(self):
        self.agents = []
        self.coordinator = None
        self.running = False
        
    async def setup_openfire_agents(self) -> bool:
        """Configurar agentes en OpenFire"""
        try:
            # Crear agentes en OpenFire
            agents_to_create = ["coordinator"] + \
                             [f"taxi{i}" for i in range(unified_config.num_taxis)] + \
                             [f"passenger{i}" for i in range(unified_config.num_passengers)]
            
            for agent_id in agents_to_create:
                success = await openfire_api.create_user(
                    username=agent_id,
                    password="123",
                    name=f"Agent {agent_id}"
                )
                if success:
                    logging.info(f"Agente {agent_id} creado en OpenFire")
                else:
                    logging.warning(f"No se pudo crear agente {agent_id} (puede que ya exista)")
                    
            return True
        except Exception as e:
            logging.error(f"Error configurando agentes OpenFire: {e}")
            return False
            
    async def start_local_mode(self):
        """Iniciar en modo local (una sola máquina)"""
        logging.info("Iniciando sistema en modo LOCAL")
        
        if not SPADE_AVAILABLE:
            logging.error("SPADE no disponible. Instalar con: pip install spade")
            return False
            
        # Configurar agentes en OpenFire
        if not await self.setup_openfire_agents():
            logging.error("Error configurando OpenFire")
            return False
            
        try:
            # Crear e iniciar coordinador
            self.coordinator = CoordinatorAgent(
                f"coordinator@{unified_config.openfire_domain}",
                "123"
            )
            await self.coordinator.start()
            self.agents.append(self.coordinator)
            
            # Crear e iniciar taxis
            for i in range(unified_config.num_taxis):
                taxi = TaxiAgent(
                    f"taxi{i}@{unified_config.openfire_domain}",
                    "123",
                    f"taxi{i}"
                )
                await taxi.start()
                self.agents.append(taxi)
                
            # Crear e iniciar pasajeros
            for i in range(unified_config.num_passengers):
                passenger = PassengerAgent(
                    f"passenger{i}@{unified_config.openfire_domain}",
                    "123",
                    f"passenger{i}"
                )
                await passenger.start()
                self.agents.append(passenger)
                
            # Iniciar bus de mensajes
            message_task = asyncio.create_task(message_bus.start())
            
            logging.info(f"Sistema iniciado con {len(self.agents)} agentes")
            self.running = True
            
            # Ejecutar simulación
            await self.run_simulation()
            
            # Limpiar
            await self.cleanup()
            return True
            
        except Exception as e:
            logging.error(f"Error iniciando sistema local: {e}")
            await self.cleanup()
            return False
            
    async def start_distributed_mode(self, role: str, host_id: str = None):
        """Iniciar en modo distribuido"""
        logging.info(f"Iniciando sistema en modo DISTRIBUTED como {role}")
        
        if role == "coordinator":
            return await self.start_coordinator_node()
        elif role == "taxi_host":
            return await self.start_taxi_node(host_id)
        elif role == "passenger_host":
            return await self.start_passenger_node(host_id)
        else:
            logging.error(f"Rol desconocido: {role}")
            return False
            
    async def start_coordinator_node(self):
        """Iniciar nodo coordinador"""
        try:
            # Configurar agentes en OpenFire
            if not await self.setup_openfire_agents():
                logging.error("Error configurando OpenFire")
                return False
                
            # Crear e iniciar coordinador
            self.coordinator = CoordinatorAgent(
                f"coordinator@{unified_config.openfire_domain}",
                "123"
            )
            await self.coordinator.start()
            self.agents.append(self.coordinator)
            
            logging.info("Nodo coordinador iniciado")
            self.running = True
            
            # Mantener funcionando
            while self.running:
                await asyncio.sleep(1)
                
            return True
        except Exception as e:
            logging.error(f"Error iniciando coordinador: {e}")
            return False
            
    async def start_taxi_node(self, host_id: str):
        """Iniciar nodo de taxis"""
        try:
            # Determinar qué taxis crear en este host
            remote_hosts = unified_config.remote_hosts or []
            if not remote_hosts:
                logging.error("No hay hosts remotos configurados")
                return False
                
            taxis_per_host = unified_config.num_taxis // len(remote_hosts)
            start_idx = int(host_id) * taxis_per_host
            end_idx = start_idx + taxis_per_host
            
            # Crear taxis para este host
            for i in range(start_idx, min(end_idx, unified_config.num_taxis)):
                taxi = TaxiAgent(
                    f"taxi{i}@{unified_config.openfire_domain}",
                    "123",
                    f"taxi{i}"
                )
                await taxi.start()
                self.agents.append(taxi)
                
            logging.info(f"Nodo taxi {host_id} iniciado con {len(self.agents)} taxis")
            self.running = True
            
            # Mantener funcionando
            while self.running:
                await asyncio.sleep(1)
                
            return True
        except Exception as e:
            logging.error(f"Error iniciando nodo taxi: {e}")
            return False
            
    async def start_passenger_node(self, host_id: str):
        """Iniciar nodo de pasajeros"""
        try:
            # Determinar qué pasajeros crear en este host
            remote_hosts = unified_config.remote_hosts or []
            if not remote_hosts:
                logging.error("No hay hosts remotos configurados")
                return False
                
            passengers_per_host = unified_config.num_passengers // len(remote_hosts)
            start_idx = int(host_id) * passengers_per_host
            end_idx = start_idx + passengers_per_host
            
            # Crear pasajeros para este host
            for i in range(start_idx, min(end_idx, unified_config.num_passengers)):
                passenger = PassengerAgent(
                    f"passenger{i}@{unified_config.openfire_domain}",
                    "123",
                    f"passenger{i}"
                )
                await passenger.start()
                self.agents.append(passenger)
                
            logging.info(f"Nodo pasajero {host_id} iniciado con {len(self.agents)} pasajeros")
            self.running = True
            
            # Mantener funcionando
            while self.running:
                await asyncio.sleep(1)
                
            return True
        except Exception as e:
            logging.error(f"Error iniciando nodo pasajero: {e}")
            return False
            
    async def run_simulation(self):
        """Ejecutar simulación por tiempo determinado"""
        logging.info(f"Ejecutando simulación por {unified_config.simulation_duration} segundos")
        
        start_time = time.time()
        while self.running and (time.time() - start_time) < unified_config.simulation_duration:
            await asyncio.sleep(1)
            
            # Mostrar estado cada 10 segundos
            if int(time.time() - start_time) % 10 == 0:
                await self.print_status()
                
        logging.info("Simulación completada")
        
    async def print_status(self):
        """Mostrar estado del sistema"""
        if self.coordinator:
            num_taxis = len(self.coordinator.taxis)
            num_requests = len(self.coordinator.passenger_requests)
            print(f"Estado: {num_taxis} taxis, {num_requests} solicitudes")
            
    async def cleanup(self):
        """Limpiar recursos"""
        logging.info("Limpiando sistema...")
        self.running = False
        message_bus.stop()
        
        for agent in self.agents:
            try:
                await agent.stop()
            except Exception as e:
                logging.error(f"Error deteniendo agente: {e}")
                
        self.agents.clear()

# =============================================================================
# INTERFAZ GRÁFICA (OPCIONAL)
# =============================================================================

class TaxiSystemGUI:
    """Interfaz gráfica para el sistema de taxis"""
    
    def __init__(self):
        if not GUI_AVAILABLE:
            raise ImportError("GUI no disponible. Instalar dependencias: pip install matplotlib tkinter")
            
        self.root = tk.Tk()
        self.root.title("Sistema de Taxis Unificado")
        self.root.geometry("800x600")
        
        self.system = UnifiedTaxiSystem()
        self.running = False
        
        self.setup_gui()
        
    def setup_gui(self):
        """Configurar interfaz gráfica"""
        # Frame de controles
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        # Botones
        ttk.Button(control_frame, text="Iniciar Local", 
                  command=self.start_local).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Detener", 
                  command=self.stop_system).pack(side=tk.LEFT, padx=5)
        
        # Configuración
        config_frame = ttk.LabelFrame(self.root, text="Configuración")
        config_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(config_frame, text="Taxis:").grid(row=0, column=0, sticky=tk.W)
        self.taxi_var = tk.StringVar(value=str(unified_config.num_taxis))
        ttk.Entry(config_frame, textvariable=self.taxi_var, width=10).grid(row=0, column=1)
        
        ttk.Label(config_frame, text="Pasajeros:").grid(row=0, column=2, sticky=tk.W)
        self.passenger_var = tk.StringVar(value=str(unified_config.num_passengers))
        ttk.Entry(config_frame, textvariable=self.passenger_var, width=10).grid(row=0, column=3)
        
        # Log
        log_frame = ttk.LabelFrame(self.root, text="Log del Sistema")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=20)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configurar logging para mostrar en GUI
        self.setup_logging()
        
    def setup_logging(self):
        """Configurar logging para mostrar en la GUI"""
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record)
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END)
                
        gui_handler = GUILogHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(gui_handler)
        
    def start_local(self):
        """Iniciar sistema en modo local"""
        if self.running:
            messagebox.showwarning("Advertencia", "El sistema ya está funcionando")
            return
            
        # Actualizar configuración
        try:
            unified_config.num_taxis = int(self.taxi_var.get())
            unified_config.num_passengers = int(self.passenger_var.get())
        except ValueError:
            messagebox.showerror("Error", "Valores de configuración inválidos")
            return
            
        # Iniciar sistema en hilo separado
        self.running = True
        threading.Thread(target=self._run_local_async, daemon=True).start()
        
    def _run_local_async(self):
        """Ejecutar sistema local de forma asíncrona"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.system.start_local_mode())
        except Exception as e:
            logging.error(f"Error en sistema: {e}")
        finally:
            self.running = False
            
    def stop_system(self):
        """Detener sistema"""
        if self.running:
            self.system.running = False
            self.running = False
            logging.info("Sistema detenido por usuario")
        else:
            messagebox.showinfo("Info", "El sistema no está funcionando")
            
    def run(self):
        """Ejecutar interfaz gráfica"""
        self.root.mainloop()

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

async def check_prerequisites():
    """Verificar prerrequisitos del sistema"""
    logging.info("Verificando prerrequisitos...")
    
    # Verificar SPADE
    if not SPADE_AVAILABLE:
        logging.error("SPADE no disponible. Instalar con: pip install spade")
        return False
        
    # Verificar conexión a OpenFire
    try:
        # Simplemente verificar que podemos acceder a la API
        success = openfire_api.list_users()  # Usar método existente
        logging.info("Conexión a OpenFire verificada")
    except Exception as e:
        logging.error(f"Error verificando OpenFire: {e}")
        return False
        
    logging.info("Prerrequisitos verificados correctamente")
    return True

def setup_logging(level=logging.INFO):
    """Configurar logging del sistema"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('unified_taxi_system.log')
        ]
    )

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

async def main():
    """Función principal del sistema"""
    # Configurar logging
    setup_logging()
    
    # Parser de argumentos
    parser = argparse.ArgumentParser(description="Sistema de Taxis Unificado")
    parser.add_argument("--mode", choices=["local", "distributed"], default="local",
                       help="Modo de ejecución")
    parser.add_argument("--role", choices=["coordinator", "taxi_host", "passenger_host"],
                       help="Rol en modo distribuido")
    parser.add_argument("--host-id", type=str, help="ID del host para modo distribuido")
    parser.add_argument("--gui", action="store_true", help="Usar interfaz gráfica")
    parser.add_argument("--taxis", type=int, default=3, help="Número de taxis")
    parser.add_argument("--passengers", type=int, default=5, help="Número de pasajeros")
    parser.add_argument("--duration", type=int, default=60, help="Duración en segundos")
    
    args = parser.parse_args()
    
    # Actualizar configuración
    unified_config.num_taxis = args.taxis
    unified_config.num_passengers = args.passengers
    unified_config.simulation_duration = args.duration
    
    # Verificar prerrequisitos
    if not await check_prerequisites():
        return False
        
    # Ejecutar según modo
    if args.gui and args.mode == "local":
        # Modo GUI
        if not GUI_AVAILABLE:
            logging.error("GUI no disponible. Instalar dependencias.")
            return False
            
        gui = TaxiSystemGUI()
        gui.run()
        return True
        
    else:
        # Modo consola
        system = UnifiedTaxiSystem()
        
        if args.mode == "local":
            success = await system.start_local_mode()
        else:
            if not args.role:
                logging.error("Rol requerido para modo distribuido")
                return False
            success = await system.start_distributed_mode(args.role, args.host_id)
            
        return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logging.info("Sistema interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error fatal: {e}")
        sys.exit(1)
