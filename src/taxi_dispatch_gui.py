# ==================== IMPORTS REQUERIDOS PARA LA GUI ====================
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import asyncio

from src.utils.logger import logger
from src.config import config
from src.services.openfire_api import openfire_api
from src.agent.libs.environment import (
    GridNetwork,
    GridPosition,
    TaxiState,
    PassengerState,
)

# ==================== ESTRUCTURAS DE DATOS ====================
@dataclass
class TaxiPos():
    """Clase para representar la posición de un taxi en la grilla"""
    
    taxi_id: str
    position: GridPosition

# ==================== GUI Y SISTEMA PRINCIPAL ====================
class GridTaxiGUI:
    """Interfaz gráfica principal del sistema de taxis"""

    def __init__(self):
        self.grid = GridNetwork(config.grid_width, config.grid_height)
        self.coordinator = None
        self.running = False

        # GUI setup
        self.root = tk.Tk()
        self.root.title("Sistema de Despacho de Taxis - Constraint Programming")
        self.root.geometry(f"{config.gui_width}x{config.gui_height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Variables de estado
        self.solver_type = tk.StringVar(value="OR-Tools")
        self.taxi_count = tk.StringVar(value="0")
        self.passenger_count = tk.StringVar(value="0")
        self.waiting_passengers = tk.StringVar(value="0")

        self._setup_gui()
        self._start_update_thread()
        
        # Actualizar estadísticas iniciales
        self._update_stats()

        logger.info("GUI initialized")

    def _setup_gui(self):
        """Configura la interfaz gráfica"""
        
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Título
        title_label = ttk.Label(
            main_frame,
            text="🚕 Sistema de Despacho de Taxis con Constraint Programming",
            font=("Arial", 16, "bold"),
        )
        title_label.pack(pady=(0, 10))

        # Frame de contenido
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas de la grilla (lado izquierdo)
        self._setup_grid_canvas(content_frame)

        # Panel de control (lado derecho)
        self._setup_control_panel(content_frame)

        # Status bar
        self._setup_status_bar(main_frame)

    def _setup_grid_canvas(self, parent):
        """Configura el canvas de la grilla"""
        canvas_frame = ttk.LabelFrame(parent, text="Mapa de la Ciudad", padding=10)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Calcular tamaño del canvas
        canvas_width = self.grid.width * config.grid_cell_size
        canvas_height = self.grid.height * config.grid_cell_size

        # Scrollable canvas
        canvas_container = ttk.Frame(canvas_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        # Canvas
        self.canvas = tk.Canvas(
            canvas_container,
            width=min(canvas_width, 800),
            height=min(canvas_height, 600),
            bg="white",
            scrollregion=(0, 0, canvas_width, canvas_height),
        )

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(
            canvas_container, orient=tk.VERTICAL, command=self.canvas.yview
        )
        h_scrollbar = ttk.Scrollbar(
            canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        self.canvas.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        # Pack scrollbars y canvas
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Dibujar grilla inicial
        self._draw_grid()

    def _setup_control_panel(self, parent):
        """Configura el panel de control"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Estadísticas
        stats_frame = ttk.LabelFrame(control_frame, text="📊 Estadísticas", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        stats_data = [
            ("Taxis activos:", self.taxi_count),
            ("Total pasajeros:", self.passenger_count),
            ("Esperando taxi:", self.waiting_passengers),
            ("Solver activo:", self.solver_type),
        ]

        for i, (label, var) in enumerate(stats_data):
            ttk.Label(stats_frame, text=label).grid(
                row=i, column=0, sticky=tk.W, pady=2
            )
            ttk.Label(stats_frame, textvariable=var, font=("Arial", 10, "bold")).grid(
                row=i, column=1, sticky=tk.E, pady=2, padx=(10, 0)
            )

        # Controles
        controls_frame = ttk.LabelFrame(control_frame, text="🎮 Controles", padding=10)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            controls_frame, text="🚀 Iniciar Sistema", command=self._start_system
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            controls_frame, text="⏹️ Detener Sistema", command=self._stop_system
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            controls_frame, text=" Reset Sistema", command=self._reset_system
        ).pack(fill=tk.X, pady=2)

        # Leyenda
        legend_frame = ttk.LabelFrame(control_frame, text="📋 Leyenda", padding=10)
        legend_frame.pack(fill=tk.X)

        legend_items = [
            ("◆", "Taxi disponible", "gold"),
            ("◆", "Taxi ocupado", "orange"),
            ("■", "Pasajero normal", "blue"),
            ("●", "Pasajero discapacitado", "purple"),
            ("▲", "Destino", "red"),
            ("╋", "Intersección", "gray"),
        ]

        for symbol, description, color in legend_items:
            frame = ttk.Frame(legend_frame)
            frame.pack(fill=tk.X, pady=1)
            ttk.Label(frame, text=symbol, font=("Arial", 12), foreground=color).pack(
                side=tk.LEFT
            )
            ttk.Label(frame, text=description).pack(side=tk.LEFT, padx=(5, 0))

    def _setup_status_bar(self, parent):
        """Configura la barra de estado"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.status_text = tk.StringVar(value="Sistema detenido")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_text,
            font=("Arial", 10),
            foreground="blue",
        )
        status_label.pack(side=tk.LEFT)

        # Reloj
        self.clock_text = tk.StringVar()
        clock_label = ttk.Label(
            status_frame, textvariable=self.clock_text, font=("Arial", 10)
        )
        clock_label.pack(side=tk.RIGHT)

        self._update_clock()

    def _draw_grid(self):
        """Dibuja la grilla de intersecciones"""
        self.canvas.delete("grid")

        cell_size = config.grid_cell_size

        # Dibujar líneas de grilla
        for x in range(self.grid.width + 1):
            x_pos = x * cell_size
            self.canvas.create_line(
                x_pos,
                0,
                x_pos,
                self.grid.height * cell_size,
                fill="lightgray",
                width=1,
                tags="grid",
            )

        for y in range(self.grid.height + 1):
            y_pos = y * cell_size
            self.canvas.create_line(
                0,
                y_pos,
                self.grid.width * cell_size,
                y_pos,
                fill="lightgray",
                width=1,
                tags="grid",
            )

        # Dibujar intersecciones
        for intersection in self.grid.intersections:
            x = intersection.x * cell_size + cell_size // 2
            y = intersection.y * cell_size + cell_size // 2
            self.canvas.create_text(
                x, y, text="╋", font=("Arial", 8), fill="gray", tags="grid"
            )

    def _draw_entities(self):
        """Dibuja taxis y pasajeros"""
        self.canvas.delete("entities")

        if not self.coordinator:
            return

        cell_size = config.grid_cell_size

        # Dibujar pasajeros
        for passenger in self.coordinator.passengers.values():
            if passenger.state == PassengerState.WAITING:
                x = passenger.pickup_position.x * cell_size + cell_size // 2
                y = passenger.pickup_position.y * cell_size + cell_size // 2

                # Determinar color y forma según tipo de pasajero
                if passenger.is_disabled:
                    # Pasajero discapacitado: círculo púrpura con símbolo de silla de ruedas
                    passenger_color = "purple"
                    passenger_outline = "darkviolet"
                    passenger_symbol = "♿"
                    passenger_text_color = "darkviolet"
                else:
                    # Pasajero normal: cuadrado azul
                    passenger_color = "blue"
                    passenger_outline = "darkblue"
                    passenger_symbol = "👤"
                    passenger_text_color = "darkblue"

                # Dibujar pasajero con forma apropiada
                if passenger.is_disabled:
                    # Círculo para discapacitados
                    self.canvas.create_oval(
                        x - 8,
                        y - 8,
                        x + 8,
                        y + 8,
                        fill=passenger_color,
                        outline=passenger_outline,
                        width=3,
                        tags="entities",
                    )
                    # Símbolo de silla de ruedas
                    self.canvas.create_text(
                        x,
                        y,
                        text=passenger_symbol,
                        font=("Arial", 10, "bold"),
                        fill="white",
                        tags="entities",
                    )
                else:
                    # Cuadrado para normales
                    self.canvas.create_rectangle(
                        x - 6,
                        y - 6,
                        x + 6,
                        y + 6,
                        fill=passenger_color,
                        outline=passenger_outline,
                        width=2,
                        tags="entities",
                    )

                # Línea punteada al destino
                dest_x = passenger.dropoff_position.x * cell_size + cell_size // 2
                dest_y = passenger.dropoff_position.y * cell_size + cell_size // 2
                line_color = passenger_outline
                self.canvas.create_line(
                    x,
                    y,
                    dest_x,
                    dest_y,
                    fill=line_color,
                    width=2 if passenger.is_disabled else 1,
                    dash=(3, 3),
                    tags="entities",
                )

                # Destino
                self.canvas.create_polygon(
                    dest_x,
                    dest_y - 6,
                    dest_x - 5,
                    dest_y + 4,
                    dest_x + 5,
                    dest_y + 4,
                    fill="red",
                    outline="darkred",
                    width=2,
                    tags="entities",
                )

                # ID del pasajero con tipo
                passenger_type = "D" if passenger.is_disabled else "N"
                self.canvas.create_text(
                    x,
                    y + 15,
                    text=f"{passenger.passenger_id[-2:]}({passenger_type})",
                    font=("Arial", 8, "bold" if passenger.is_disabled else "normal"),
                    fill=passenger_text_color,
                    tags="entities",
                )

        # Dibujar taxis
        for taxi in self.coordinator.taxis.values():
            # Permitir dict o objeto
            def get_attr(obj, attr):
                if isinstance(obj, dict):
                    return obj[attr]
                return getattr(obj, attr)

            pos = get_attr(taxi, "position")
            x = get_attr(pos, "x") * cell_size + cell_size // 2
            y = get_attr(pos, "y") * cell_size + cell_size // 2

            # Color según estado
            state = get_attr(taxi, "state")
            if isinstance(state, str):
                idle = state == "IDLE"
            else:
                idle = state == TaxiState.IDLE
            if idle:
                color = "gold"
                outline = "orange"
            else:
                color = "orange"
                outline = "darkorange"

            # Taxi (diamante)
            self.canvas.create_polygon(
                x,
                y - 8,
                x + 8,
                y,
                x,
                y + 8,
                x - 8,
                y,
                fill=color,
                outline=outline,
                width=2,
                tags="entities",
            )

            # ID del taxi
            taxi_id = get_attr(taxi, "taxi_id")
            self.canvas.create_text(
                x,
                y - 18,
                text=taxi_id,
                font=("Arial", 8, "bold"),
                fill="black",
                tags="entities",
            )

            # Línea hacia objetivo si existe
            target_pos = get_attr(taxi, "target_position")
            if target_pos:
                target_x = get_attr(target_pos, "x") * cell_size + cell_size // 2
                target_y = get_attr(target_pos, "y") * cell_size + cell_size // 2
                self.canvas.create_line(
                    x,
                    y,
                    target_x,
                    target_y,
                    fill=color,
                    width=2,
                    dash=(5, 5),
                    tags="entities",
                )

    def _start_system(self):
        """Inicia el sistema distribuido"""
        if self.running:
            messagebox.showwarning("Sistema", "El sistema ya está en ejecución")
            return

        try:
            # Iniciar sistema en hilo separado
            self.system_thread = threading.Thread(
                target=self._run_distributed_system, daemon=True
            )
            self.system_thread.start()

            self.status_text.set("Sistema iniciado - Conectando agentes...")
            logger.info("Starting distributed taxi system")

        except Exception as e:
            messagebox.showerror("Error", f"Error al iniciar sistema: {e}")
            logger.error(f"Failed to start system: {e}")

    def _stop_system(self):
        """Detiene el sistema"""
        self.running = False
        self.status_text.set("Sistema detenido")
        # Actualizar estadísticas para reflejar que el sistema se detuvo
        self._update_stats()
        logger.info("System stopped")

    def _reset_system(self):
        """Reinicia el sistema"""
        self._stop_system()
        time.sleep(1)
        self._start_system()

    def _run_distributed_system(self):
        """Ejecuta el sistema distribuido en hilo separado"""
        loop = None
        try:
            # Crear nuevo event loop para este hilo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Ejecutar sistema async
            loop.run_until_complete(self._async_system_main())

        except Exception as e:
            logger.error(f"System error: {e}")
            self.status_text.set(f"Error en sistema: {e}")
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def _async_system_main(self):
        """Main async del sistema distribuido"""
        try:
            self.running = True

            # Verificar OpenFire
            if not self._check_openfire():
                self.status_text.set("Error: OpenFire no disponible")
                return

            # Crear coordinador
            try:
                # Crear usuario coordinador
                openfire_api.create_user(
                    "coordinator", "coordinator_pass", "Coordinator Agent"
                )

                logger.info("XMPP users created")
            except Exception as e:
                logger.warning(f"XMPP user creation error (might exist): {e}")
                
            from src.agent.coordinator import CoordinatorAgent
            self.coordinator = CoordinatorAgent(
                f"coordinator@{config.openfire_domain}", "coordinator_pass", self.grid
            )
            await self.coordinator.start(auto_register=True)

            self.status_text.set("Sistema activo - Agentes conectados")

            # Loop principal con actualización de estadísticas
            last_update = time.time()
            last_stats_update = time.time()
            
            while self.running:
                current_time = time.time()
                dt = current_time - last_update

                # Actualizar estadísticas cada segundo
                if current_time - last_stats_update >= 1.0:
                    self.root.after(0, self._update_stats)  # Ejecutar en hilo principal
                    last_stats_update = current_time

                last_update = current_time
                await asyncio.sleep(0.05)  # 20 FPS

        except Exception as e:
            logger.error(f"Async system error: {e}")
            self.status_text.set(f"Error: {e}")
        finally:
            # Cleanup
            self.running = False

    def _check_openfire(self) -> bool:
        """Verifica conexión con OpenFire"""
        try:
            import requests

            response = requests.get(
                f"http://{config.openfire_host}:{config.openfire_port}", timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def _update_stats(self):
        """Actualiza estadísticas de la GUI"""
        try:
            if self.coordinator and hasattr(self.coordinator, 'taxis') and hasattr(self.coordinator, 'passengers'):
                # Contar taxis activos
                taxi_count = len(self.coordinator.taxis) if self.coordinator.taxis else 0
                
                # Contar pasajeros totales
                passenger_count = len(self.coordinator.passengers) if self.coordinator.passengers else 0
                
                # Contar pasajeros esperando
                waiting_count = 0
                if self.coordinator.passengers:
                    for passenger in self.coordinator.passengers.values():
                        try:
                            if hasattr(passenger, 'state'):
                                if passenger.state == PassengerState.WAITING:
                                    waiting_count += 1
                            elif isinstance(passenger, dict) and passenger.get('state') == 'WAITING':
                                waiting_count += 1
                        except:
                            continue
                
                # Actualizar variables de la GUI
                self.taxi_count.set(str(taxi_count))
                self.passenger_count.set(str(passenger_count))
                self.waiting_passengers.set(str(waiting_count))
                
                # Actualizar estado del solver
                if self.running:
                    self.solver_type.set("OR-Tools Activo")
                else:
                    self.solver_type.set("OR-Tools Inactivo")
                
            else:
                # Sistema no iniciado o sin datos
                self.taxi_count.set("0")
                self.passenger_count.set("0")
                self.waiting_passengers.set("0")
                if self.running:
                    self.solver_type.set("Iniciando...")
                else:
                    self.solver_type.set("Sistema Detenido")
                    
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
            # Valores por defecto en caso de error
            self.taxi_count.set("--")
            self.passenger_count.set("--")
            self.waiting_passengers.set("--")
            self.solver_type.set("Error")

    def _update_clock(self):
        """Actualiza el reloj"""
        import datetime

        now = datetime.datetime.now()
        self.clock_text.set(now.strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _start_update_thread(self):
        """Inicia hilo de actualización visual"""

        def update_loop():
            last_stats_update = time.time()
            while True:
                try:
                    current_time = time.time()
                    
                    if self.running and self.coordinator:
                        # Programar actualización visual en hilo principal
                        self.root.after(0, self._draw_entities)
                        
                        # También actualizar estadísticas cada segundo
                        if current_time - last_stats_update >= 1.0:
                            self.root.after(0, self._update_stats)
                            last_stats_update = current_time
                    else:
                        # Actualizar estadísticas incluso cuando no está corriendo
                        if current_time - last_stats_update >= 2.0:
                            self.root.after(0, self._update_stats)
                            last_stats_update = current_time
                    
                    time.sleep(1 / config.fps)  # 20 FPS para visualización
                except Exception as e:
                    logger.error(f"Update thread error: {e}")
                    time.sleep(1)

        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()

    def _on_closing(self):
        """Maneja cierre de ventana"""
        self._stop_system()
        self.root.destroy()

    def run(self):
        """Ejecuta la GUI"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("GUI interrupted")
        finally:
            self._stop_system()


# ==================== FUNCIÓN LAUNCHER ====================
def launch_taxi_gui():
    """Lanza la interfaz gráfica del sistema de taxis"""
    try:
        app = GridTaxiGUI()
        app.run()
    except Exception as e:
        print(f"Error al lanzar GUI: {e}")
        import traceback

        traceback.print_exc()