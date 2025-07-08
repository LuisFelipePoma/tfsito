#!/usr/bin/env python3
"""
🚕 DEMO CONSOLA - SISTEMA DE TAXIS DISTRIBUIDO
==============================================

Simulación en consola que muestra el sistema distribuido ejecutándose
con estadísticas en tiempo real y visualización ASCII.

Ejecutar: python demo_taxi_console.py
"""

import sys
import os
import time
import threading
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

# Configuración
@dataclass
class Config:
    grid_width: int = 15
    grid_height: int = 10
    taxi_count: int = 4
    max_passengers: int = 8
    update_interval: float = 1.0

config = Config()

# Estados (mismo que GUI)
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
class TaxiAgent:
    taxi_id: str
    position: Position
    state: TaxiState = TaxiState.IDLE
    assigned_passenger_id: Optional[str] = None
    target_position: Optional[Position] = None
    trips_completed: int = 0
    host_id: str = "local"  # Simula host distribuido

@dataclass 
class PassengerAgent:
    passenger_id: str
    pickup_position: Position
    dropoff_position: Position
    state: PassengerState = PassengerState.WAITING
    wait_time: float = 0.0
    assigned_taxi_id: Optional[str] = None
    host_id: str = "local"  # Simula host distribuido

class DistributedTaxiSystem:
    """Sistema de taxis con simulación distribuida"""
    
    def __init__(self):
        self.taxis: Dict[str, TaxiAgent] = {}
        self.passengers: Dict[str, PassengerAgent] = {}
        self.passenger_counter = 0
        self.running = False
        self.total_trips = 0
        self.total_wait_time = 0.0
        
        # Simular hosts distribuidos
        self.hosts = ["coordinator", "taxi_host_1", "taxi_host_2", "passenger_host"]
        
        self._create_taxis()
        self._create_initial_passengers()
    
    def _create_taxis(self):
        """Crea taxis distribuidos en diferentes hosts"""
        hosts_cycle = ["coordinator", "taxi_host_1", "taxi_host_1", "taxi_host_2"]
        
        for i in range(config.taxi_count):
            taxi_id = f"taxi_{i+1}"
            host_id = hosts_cycle[i % len(hosts_cycle)]
            
            position = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
            
            self.taxis[taxi_id] = TaxiAgent(taxi_id, position, host_id=host_id)
    
    def _create_initial_passengers(self):
        """Crea pasajeros iniciales"""
        for i in range(3):  # Empezar con pocos
            self._spawn_passenger()
    
    def _spawn_passenger(self):
        """Genera un nuevo pasajero"""
        if len(self.passengers) >= config.max_passengers:
            return
        
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
        
        # Asegurar distancia mínima
        while pickup.distance_to(dropoff) < 3:
            dropoff = Position(
                random.randint(0, config.grid_width - 1),
                random.randint(0, config.grid_height - 1)
            )
        
        # Asignar a host de pasajeros
        host_id = "passenger_host"
        
        self.passengers[passenger_id] = PassengerAgent(
            passenger_id, pickup, dropoff, host_id=host_id
        )
    
    def update(self, dt: float):
        """Actualiza el sistema"""
        if not self.running:
            return
        
        # Asignar taxis (constraint programming simulado)
        self._assign_taxis_with_constraints()
        
        # Mover taxis
        self._move_taxis()
        
        # Actualizar tiempos de espera
        for passenger in self.passengers.values():
            if passenger.state == PassengerState.WAITING:
                passenger.wait_time += dt
        
        # Generar nuevos pasajeros ocasionalmente
        if random.random() < 0.3:  # 30% probabilidad por update
            self._spawn_passenger()
    
    def _assign_taxis_with_constraints(self):
        """Asignación con constraint programming simulado"""
        idle_taxis = [t for t in self.taxis.values() if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in self.passengers.values() if p.state == PassengerState.WAITING]
        
        if not idle_taxis or not waiting_passengers:
            return
        
        # Simulación de constraint programming
        # Minimizar tiempo total de viaje + tiempo de espera
        assignments = []
        
        for passenger in waiting_passengers:
            best_taxi = None
            best_score = float('inf')
            
            for taxi in idle_taxis:
                # Función de costo: distancia + tiempo de espera
                distance = taxi.position.distance_to(passenger.pickup_position)
                wait_penalty = passenger.wait_time * 2  # Penalizar espera larga
                score = distance + wait_penalty
                
                if score < best_score:
                    best_score = score
                    best_taxi = taxi
            
            if best_taxi:
                assignments.append((best_taxi, passenger))
                idle_taxis.remove(best_taxi)
        
        # Aplicar asignaciones
        for taxi, passenger in assignments:
            taxi.state = TaxiState.PICKUP
            taxi.assigned_passenger_id = passenger.passenger_id
            taxi.target_position = passenger.pickup_position
            passenger.assigned_taxi_id = taxi.taxi_id
    
    def _move_taxis(self):
        """Mueve taxis hacia objetivos"""
        for taxi in self.taxis.values():
            if taxi.state == TaxiState.IDLE or not taxi.target_position:
                continue
            
            if taxi.position.distance_to(taxi.target_position) > 0:
                taxi.position = taxi.position.move_towards(taxi.target_position)
            else:
                self._handle_arrival(taxi)
    
    def _handle_arrival(self, taxi: TaxiAgent):
        """Maneja llegadas de taxis"""
        if taxi.state == TaxiState.PICKUP and taxi.assigned_passenger_id:
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.PICKED_UP
                taxi.state = TaxiState.DROPOFF
                taxi.target_position = passenger.dropoff_position
        
        elif taxi.state == TaxiState.DROPOFF and taxi.assigned_passenger_id:
            passenger = self.passengers.get(taxi.assigned_passenger_id)
            if passenger:
                passenger.state = PassengerState.DELIVERED
                taxi.trips_completed += 1
                self.total_trips += 1
                self.total_wait_time += passenger.wait_time
                
                # Remover pasajero entregado
                del self.passengers[passenger.passenger_id]
            
            taxi.state = TaxiState.IDLE
            taxi.assigned_passenger_id = None
            taxi.target_position = None
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def get_stats(self):
        """Obtiene estadísticas del sistema"""
        taxis_by_state = {}
        for state in TaxiState:
            taxis_by_state[state] = sum(1 for t in self.taxis.values() if t.state == state)
        
        passengers_by_state = {}
        for state in PassengerState:
            passengers_by_state[state] = sum(1 for p in self.passengers.values() if p.state == state)
        
        avg_wait_time = self.total_wait_time / max(self.total_trips, 1)
        
        return {
            'taxis_by_state': taxis_by_state,
            'passengers_by_state': passengers_by_state,
            'total_trips': self.total_trips,
            'avg_wait_time': avg_wait_time,
            'active_passengers': len(self.passengers)
        }

class ConsoleDisplay:
    """Display en consola para el sistema"""
    
    def __init__(self, system: DistributedTaxiSystem):
        self.system = system
        self.step = 0
    
    def clear_screen(self):
        """Limpia la pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def draw_grid(self):
        """Dibuja la grilla ASCII"""
        print("🗺️  MAPA DEL SISTEMA (Grilla Distribuida)")
        print("═" * (config.grid_width * 2 + 1))
        
        # Crear grilla vacía
        grid = [['.' for _ in range(config.grid_width)] for _ in range(config.grid_height)]
        
        # Colocar pasajeros
        for passenger in self.system.passengers.values():
            if passenger.state == PassengerState.WAITING:
                x, y = passenger.pickup_position.x, passenger.pickup_position.y
                if 0 <= x < config.grid_width and 0 <= y < config.grid_height:
                    grid[y][x] = '👤'
        
        # Colocar taxis (sobrescribe pasajeros si están en la misma posición)
        for taxi in self.system.taxis.values():
            x, y = taxi.position.x, taxi.position.y
            if 0 <= x < config.grid_width and 0 <= y < config.grid_height:
                if taxi.state == TaxiState.IDLE:
                    grid[y][x] = '🚖'
                elif taxi.state == TaxiState.PICKUP:
                    grid[y][x] = '🟡'
                else:  # DROPOFF
                    grid[y][x] = '🔴'
        
        # Imprimir grilla
        for row in grid:
            print(''.join(f'{cell:<2}' for cell in row))
        
        print("═" * (config.grid_width * 2 + 1))
    
    def show_host_distribution(self):
        """Muestra distribución por hosts"""
        print("\n🖥️  DISTRIBUCIÓN POR HOSTS")
        print("─" * 40)
        
        # Agrupar por hosts
        hosts_data = {}
        
        for taxi in self.system.taxis.values():
            host = taxi.host_id
            if host not in hosts_data:
                hosts_data[host] = {'taxis': [], 'passengers': []}
            hosts_data[host]['taxis'].append(taxi)
        
        for passenger in self.system.passengers.values():
            host = passenger.host_id
            if host not in hosts_data:
                hosts_data[host] = {'taxis': [], 'passengers': []}
            hosts_data[host]['passengers'].append(passenger)
        
        for host, data in hosts_data.items():
            taxis = data['taxis']
            passengers = data['passengers']
            
            print(f"🖥️  {host.upper()}")
            print(f"   🚖 Taxis: {len(taxis)}")
            if taxis:
                for taxi in taxis:
                    state_emoji = {'libre': '🟢', 'recogiendo': '🟡', 'entregando': '🔴'}
                    emoji = state_emoji.get(taxi.state.value, '❓')
                    print(f"      {emoji} {taxi.taxi_id} ({taxi.position.x},{taxi.position.y})")
            
            print(f"   👥 Pasajeros: {len(passengers)}")
            if passengers:
                for passenger in passengers[:2]:  # Mostrar solo 2
                    state_emoji = {'esperando': '⏳', 'en_taxi': '🚖', 'entregado': '✅'}
                    emoji = state_emoji.get(passenger.state.value, '❓')
                    print(f"      {emoji} {passenger.passenger_id}")
            print()
    
    def show_stats(self):
        """Muestra estadísticas"""
        stats = self.system.get_stats()
        
        print("📊 ESTADÍSTICAS EN TIEMPO REAL")
        print("─" * 40)
        print(f"⏱️  Paso de simulación: {self.step}")
        print(f"🚖 Taxis libres: {stats['taxis_by_state'][TaxiState.IDLE]}")
        print(f"🟡 Taxis recogiendo: {stats['taxis_by_state'][TaxiState.PICKUP]}")
        print(f"🔴 Taxis entregando: {stats['taxis_by_state'][TaxiState.DROPOFF]}")
        print(f"👥 Pasajeros esperando: {stats['passengers_by_state'][PassengerState.WAITING]}")
        print(f"🚖 Pasajeros en taxi: {stats['passengers_by_state'][PassengerState.PICKED_UP]}")
        print(f"✅ Viajes completados: {stats['total_trips']}")
        print(f"⏰ Tiempo promedio espera: {stats['avg_wait_time']:.1f}s")
        
        # Eficiencia
        if stats['total_trips'] > 0:
            efficiency = (stats['total_trips'] / (stats['total_trips'] + stats['active_passengers'])) * 100
            print(f"📈 Eficiencia del sistema: {efficiency:.1f}%")
    
    def show_legend(self):
        """Muestra leyenda"""
        print("\n🔍 LEYENDA")
        print("─" * 20)
        print("🚖 Taxi libre")
        print("🟡 Taxi recogiendo")
        print("🔴 Taxi entregando")
        print("👤 Pasajero esperando")
        print(".  Espacio vacío")
    
    def update_display(self):
        """Actualiza toda la pantalla"""
        self.clear_screen()
        
        # Header
        print("🚕" * 25)
        print("  SISTEMA DE TAXIS DISTRIBUIDO - DEMO CONSOLA")
        print("  Constraint Programming + Multi-Host")
        print("🚕" * 25)
        print()
        
        # Grid
        self.draw_grid()
        
        # Stats y hosts lado a lado
        print()
        self.show_stats()
        self.show_host_distribution()
        self.show_legend()
        
        print("\n💡 Presiona Ctrl+C para salir")
        
        self.step += 1

def main():
    """Función principal"""
    print("🚕 Iniciando demo en consola del sistema distribuido...")
    
    # Crear sistema
    system = DistributedTaxiSystem()
    display = ConsoleDisplay(system)
    
    # Iniciar sistema
    system.start()
    
    try:
        while True:
            # Actualizar sistema
            system.update(config.update_interval)
            
            # Actualizar display
            display.update_display()
            
            # Esperar
            time.sleep(config.update_interval)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Sistema detenido por el usuario")
        system.stop()
        
        # Estadísticas finales
        final_stats = system.get_stats()
        print(f"\n📋 ESTADÍSTICAS FINALES:")
        print(f"   ✅ Viajes completados: {final_stats['total_trips']}")
        print(f"   ⏰ Tiempo promedio de espera: {final_stats['avg_wait_time']:.1f}s")
        print(f"   🎯 ¡Gracias por probar el sistema!")

if __name__ == "__main__":
    main()
