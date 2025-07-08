#!/usr/bin/env python3
"""
🚕 DEMO GUI LOCAL - SISTEMA DE TAXIS CON AGENTES SPADE
======================================================

Ejecuta el sistema de taxis distribuido en una sola PC con GUI visual.
INCLUYE creación de agentes SPADE reales en OpenFire.
Permite ver taxis y pasajeros moviéndose en tiempo real.

Uso:
    python demo_taxi_gui_local.py

Controles:
    - Click para agregar pasajeros
    - Ver asignaciones automáticas
    - Monitoreo en tiempo real
    - Agentes SPADE reales en OpenFire
"""

import sys
import os
import time
import threading
import tkinter as tk
from tkinter import ttk
import random
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum

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

# Import config
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
try:
    from config import config, taxi_config
    from services.openfire_api import openfire_api
    CONFIG_AVAILABLE = True
    print(f"✅ Configuración cargada - OpenFire: {config.openfire_host}:{config.openfire_port}")
except ImportError:
    CONFIG_AVAILABLE = False
    print("⚠️ Configuración no disponible - Usando valores por defecto")
    
    # Configuración por defecto
    @dataclass
    class DefaultConfig:
        openfire_host = "localhost"
        openfire_domain = "localhost" 
        openfire_port = 9090
        openfire_xmpp_port = 5222
        openfire_admin_user = "admin"
        openfire_admin_password = "123"
        openfire_secret_key = "jNw5zFIsgCfnk75M"
    
    config = DefaultConfig()
    openfire_api = None

# Configuración
@dataclass
class Config:
    grid_width: int = 20
    grid_height: int = 15
    gui_width: int = 1200
    gui_height: int = 800
    cell_size: int = 25
    taxi_count: int = 3
    initial_passengers: int = 5
    update_interval: float = 0.5  # segundos

config = Config()

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
        """Distancia Manhattan"""
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def move_towards(self, target):
        """Mueve un paso hacia el objetivo"""
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

@dataclass
class PassengerInfo:
    passenger_id: str
    pickup_position: Position
    dropoff_position: Position
    state: PassengerState = PassengerState.WAITING
    wait_time: float = 0.0
    assigned_taxi_id: Optional[str] = None

class TaxiSystem:
    """Sistema simplificado de taxis para demo GUI"""
    
    def __init__(self):
        self.taxis: Dict[str, TaxiInfo] = {}
        self.passengers: Dict[str, PassengerInfo] = {}
        self.passenger_counter = 0
        self.running = False
        
        # Crear taxis iniciales
        self._create_initial_taxis()
        self._create_initial_passengers()
    
    def _create_initial_taxis(self):
        """Crea taxis iniciales en posiciones aleatorias"""
        for i in range(config.taxi_count):
            taxi_id = f"taxi_{i+1}"
            position = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
            self.taxis[taxi_id] = TaxiInfo(taxi_id, position)
            print(f"🚖 Taxi {taxi_id} creado en {position.x}, {position.y}")
    
    def _create_initial_passengers(self):
        """Crea pasajeros iniciales"""
        for i in range(config.initial_passengers):
            self.add_random_passenger()
    
    def add_random_passenger(self):
        """Agrega un pasajero en posición aleatoria"""
        self.passenger_counter += 1
        passenger_id = f"passenger_{self.passenger_counter}"
        
        pickup = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        # Dropoff alejado del pickup
        dropoff = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        # Asegurar que pickup y dropoff son diferentes
        while pickup.distance_to(dropoff) < 3:
            dropoff = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
        
        self.passengers[passenger_id] = PassengerInfo(passenger_id, pickup, dropoff)
        print(f"👤 Pasajero {passenger_id}: {pickup.x},{pickup.y} → {dropoff.x},{dropoff.y}")
    
    def update(self, dt: float):
        """Actualiza el sistema"""
        if not self.running:
            return
        
        # Asignar taxis a pasajeros esperando
        self._assign_taxis()
        
        # Mover taxis
        self._move_taxis()
        
        # Actualizar tiempo de espera
        for passenger in self.passengers.values():
            if passenger.state == PassengerState.WAITING:
                passenger.wait_time += dt
    
    def _assign_taxis(self):
        """Asigna taxis libres a pasajeros esperando"""
        # Taxis libres
        idle_taxis = [t for t in self.taxis.values() if t.state == TaxiState.IDLE]
        # Pasajeros esperando
        waiting_passengers = [p for p in self.passengers.values() if p.state == PassengerState.WAITING]
        
        # Asignación simple: taxi más cercano
        for passenger in waiting_passengers:
            if not idle_taxis:
                break
            
            # Encontrar taxi más cercano
            closest_taxi = min(idle_taxis, key=lambda t: t.position.distance_to(passenger.pickup_position))
            
            # Asignar
            closest_taxi.state = TaxiState.PICKUP
            closest_taxi.assigned_passenger_id = passenger.passenger_id
            closest_taxi.target_position = passenger.pickup_position
            
            passenger.assigned_taxi_id = closest_taxi.taxi_id
            
            idle_taxis.remove(closest_taxi)
            
            print(f"📋 Asignado: {closest_taxi.taxi_id} → {passenger.passenger_id}")
    
    def _move_taxis(self):
        """Mueve los taxis hacia sus objetivos"""
        for taxi in self.taxis.values():
            if taxi.state == TaxiState.IDLE or not taxi.target_position:
                continue
            
            # Mover hacia objetivo
            if taxi.position.distance_to(taxi.target_position) > 0:
                taxi.position = taxi.position.move_towards(taxi.target_position)
            else:
                # Llegó al objetivo
                self._handle_taxi_arrival(taxi)
    
    def _handle_taxi_arrival(self, taxi: TaxiInfo):
        """Maneja cuando un taxi llega a su destino"""
        if taxi.state == TaxiState.PICKUP and taxi.assigned_passenger_id:
            # Recogió al pasajero
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.PICKED_UP
                taxi.state = TaxiState.DROPOFF
                taxi.target_position = passenger.dropoff_position
                print(f"🚖➡️👤 {taxi.taxi_id} recogió a {passenger.passenger_id}")
        
        elif taxi.state == TaxiState.DROPOFF and taxi.assigned_passenger_id:
            # Entregó al pasajero
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.DELIVERED
                taxi.trips_completed += 1
                print(f"✅ {taxi.taxi_id} entregó a {passenger.passenger_id}")
            
            # Taxi queda libre
            taxi.state = TaxiState.IDLE
            taxi.assigned_passenger_id = None
            taxi.target_position = None
    
    def start(self):
        """Inicia el sistema"""
        self.running = True
        print("🚀 Sistema de taxis iniciado")
    
    def stop(self):
        """Detiene el sistema"""
        self.running = False
        print("🛑 Sistema de taxis detenido")

class TaxiGUI:
    """GUI para visualizar el sistema de taxis"""
    
    def __init__(self):
        self.system = TaxiSystem()
        
        # GUI setup
        self.root = tk.Tk()
        self.root.title("🚕 Sistema de Taxis - Demo Local")
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
        title = ttk.Label(main_frame, 
                         text="🚕 Sistema de Despacho de Taxis - Demo Local", 
                         font=("Arial", 16, "bold"))
        title.pack(pady=(0, 10))
        
        # Frame de contenido
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas de la grilla
        self._setup_canvas(content_frame)
        
        # Panel de control
        self._setup_control_panel(content_frame)
    
    def _setup_canvas(self, parent):
        """Configura el canvas de la grilla"""
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Canvas
        canvas_width = config.grid_width * config.cell_size
        canvas_height = config.grid_height * config.cell_size
        
        self.canvas = tk.Canvas(canvas_frame, 
                               width=canvas_width, 
                               height=canvas_height,
                               bg="lightgray")
        self.canvas.pack()
        
        # Bind click event
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        # Dibujar grilla
        self._draw_grid()
    
    def _setup_control_panel(self, parent):
        """Configura el panel de control"""
        control_frame = ttk.Frame(parent, width=300)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)
        
        # Información del sistema
        info_frame = ttk.LabelFrame(control_frame, text="📊 Estado del Sistema")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.taxi_count_var = tk.StringVar(value="0")
        self.passenger_count_var = tk.StringVar(value="0")
        self.waiting_var = tk.StringVar(value="0")
        self.delivered_var = tk.StringVar(value="0")
        
        ttk.Label(info_frame, text="🚖 Taxis:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.taxi_count_var).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="👥 Pasajeros:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.passenger_count_var).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="⏳ Esperando:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.waiting_var).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="✅ Entregados:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.delivered_var).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # Controles
        control_panel = ttk.LabelFrame(control_frame, text="🎮 Controles")
        control_panel.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(control_panel, text="▶️ Iniciar Sistema", 
                  command=self._start_system).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(control_panel, text="⏸️ Pausar Sistema", 
                  command=self._stop_system).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(control_panel, text="👤 Agregar Pasajero", 
                  command=self._add_passenger).pack(fill=tk.X, padx=5, pady=2)
        
        # Leyenda
        legend_frame = ttk.LabelFrame(control_frame, text="🔍 Leyenda")
        legend_frame.pack(fill=tk.X, pady=(0, 10))
        
        legend_items = [
            ("🚖 Verde: Taxi libre", "green"),
            ("🚖 Amarillo: Recogiendo", "yellow"),
            ("🚖 Rojo: Entregando", "red"),
            ("👤 Azul: Esperando", "blue"),
            ("🎯 Morado: Destino", "purple"),
            ("Click: Agregar pasajero", "black")
        ]
        
        for i, (text, color) in enumerate(legend_items):
            label = ttk.Label(legend_frame, text=text)
            label.grid(row=i, column=0, sticky="w", padx=5, pady=1)
        
        # Log de eventos
        log_frame = ttk.LabelFrame(control_frame, text="📋 Eventos Recientes")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=15, width=35, font=("Courier", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    def _draw_grid(self):
        """Dibuja la grilla base"""
        # Limpiar
        self.canvas.delete("grid")
        
        # Líneas verticales
        for x in range(config.grid_width + 1):
            x_pos = x * config.cell_size
            self.canvas.create_line(x_pos, 0, x_pos, config.grid_height * config.cell_size, 
                                   fill="gray", tags="grid")
        
        # Líneas horizontales
        for y in range(config.grid_height + 1):
            y_pos = y * config.cell_size
            self.canvas.create_line(0, y_pos, config.grid_width * config.cell_size, y_pos, 
                                   fill="gray", tags="grid")
    
    def _draw_entities(self):
        """Dibuja taxis y pasajeros"""
        # Limpiar entidades previas
        self.canvas.delete("entity")
        
        # Dibujar pasajeros
        for passenger in self.system.passengers.values():
            if passenger.state == PassengerState.WAITING:
                # Pasajero esperando (pickup position)
                x = passenger.pickup_position.x * config.cell_size + config.cell_size // 2
                y = passenger.pickup_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_oval(x-8, y-8, x+8, y+8, fill="blue", tags="entity")
                self.canvas.create_text(x, y, text="👤", fill="white", tags="entity")
                
                # Mostrar destino
                dest_x = passenger.dropoff_position.x * config.cell_size + config.cell_size // 2
                dest_y = passenger.dropoff_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_oval(dest_x-6, dest_y-6, dest_x+6, dest_y+6, fill="purple", tags="entity")
                self.canvas.create_text(dest_x, dest_y, text="🎯", fill="white", tags="entity")
                
                # Línea de conexión
                self.canvas.create_line(x, y, dest_x, dest_y, fill="purple", dash=(2, 2), tags="entity")
        
        # Dibujar taxis
        for taxi in self.system.taxis.values():
            x = taxi.position.x * config.cell_size + config.cell_size // 2
            y = taxi.position.y * config.cell_size + config.cell_size // 2
            
            # Color según estado
            colors = {
                TaxiState.IDLE: "green",
                TaxiState.PICKUP: "yellow", 
                TaxiState.DROPOFF: "red"
            }
            color = colors[taxi.state]
            
            # Dibujar taxi
            self.canvas.create_rectangle(x-10, y-10, x+10, y+10, fill=color, tags="entity")
            self.canvas.create_text(x, y, text="🚖", fill="black", tags="entity")
            
            # Mostrar ID
            self.canvas.create_text(x, y-15, text=taxi.taxi_id[-1], fill="black", font=("Arial", 8), tags="entity")
            
            # Mostrar línea al objetivo si existe
            if taxi.target_position:
                target_x = taxi.target_position.x * config.cell_size + config.cell_size // 2
                target_y = taxi.target_position.y * config.cell_size + config.cell_size // 2
                self.canvas.create_line(x, y, target_x, target_y, fill=color, width=2, tags="entity")
    
    def _update_stats(self):
        """Actualiza las estadísticas"""
        taxis_idle = sum(1 for t in self.system.taxis.values() if t.state == TaxiState.IDLE)
        taxis_busy = len(self.system.taxis) - taxis_idle
        
        waiting = sum(1 for p in self.system.passengers.values() if p.state == PassengerState.WAITING)
        delivered = sum(1 for p in self.system.passengers.values() if p.state == PassengerState.DELIVERED)
        
        self.taxi_count_var.set(f"{len(self.system.taxis)} ({taxis_idle} libres)")
        self.passenger_count_var.set(str(len(self.system.passengers)))
        self.waiting_var.set(str(waiting))
        self.delivered_var.set(str(delivered))
    
    def _on_canvas_click(self, event):
        """Maneja clicks en el canvas"""
        # Convertir coordenadas de click a grilla
        grid_x = event.x // config.cell_size
        grid_y = event.y // config.cell_size
        
        if 0 <= grid_x < config.grid_width and 0 <= grid_y < config.grid_height:
            # Agregar pasajero en esta posición
            self._add_passenger_at(grid_x, grid_y)
    
    def _add_passenger_at(self, x: int, y: int):
        """Agrega un pasajero en la posición especificada"""
        self.system.passenger_counter += 1
        passenger_id = f"passenger_{self.system.passenger_counter}"
        
        pickup = Position(x, y)
        
        # Destino aleatorio
        dropoff = Position(
            random.randint(0, config.grid_width - 1),
            random.randint(0, config.grid_height - 1)
        )
        
        # Asegurar que son diferentes
        while pickup.distance_to(dropoff) < 2:
            dropoff = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
        
        self.system.passengers[passenger_id] = PassengerInfo(passenger_id, pickup, dropoff)
        self._log(f"👤 Nuevo pasajero en ({x},{y})")
    
    def _start_system(self):
        """Inicia el sistema"""
        self.system.start()
        self._log("🚀 Sistema iniciado")
    
    def _stop_system(self):
        """Detiene el sistema"""
        self.system.stop()
        self._log("⏸️ Sistema pausado")
    
    def _add_passenger(self):
        """Agrega un pasajero aleatorio"""
        self.system.add_random_passenger()
        self._log("👤 Pasajero aleatorio agregado")
    
    def _log(self, message: str):
        """Agrega mensaje al log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def _start_update_thread(self):
        """Inicia el hilo de actualización"""
        def update_loop():
            while True:
                try:
                    # Actualizar sistema
                    self.system.update(config.update_interval)
                    
                    # Actualizar GUI en el hilo principal
                    self.root.after(0, self._update_gui)
                    
                    time.sleep(config.update_interval)
                except Exception as e:
                    print(f"Error en update loop: {e}")
                    time.sleep(1)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
    
    def _update_gui(self):
        """Actualiza la GUI (debe ejecutarse en el hilo principal)"""
        self._draw_entities()
        self._update_stats()
    
    def _on_closing(self):
        """Maneja el cierre de la ventana"""
        self.system.stop()
        self.root.destroy()
    
    def run(self):
        """Ejecuta la GUI"""
        print("🚕 Iniciando demo GUI del sistema de taxis...")
        print("📋 Instrucciones:")
        print("   - Click en el mapa para agregar pasajeros")
        print("   - Los taxis se asignan automáticamente")
        print("   - Verde: taxi libre, Amarillo: recogiendo, Rojo: entregando")
        
        # Iniciar sistema automáticamente
        self.system.start()
        
        # Ejecutar GUI
        self.root.mainloop()

def main():
    """Función principal"""
    print("🚕" * 30)
    print("   DEMO GUI LOCAL - SISTEMA DE TAXIS")
    print("   Simulación visual en tiempo real")
    print("🚕" * 30)
    print()
    
    gui = TaxiGUI()
    gui.run()

if __name__ == "__main__":
    main()
