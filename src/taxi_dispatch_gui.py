# ==================== CONTINUACIÓN: GUI Y SISTEMA PRINCIPAL ====================

class GridTaxiGUI:
    """Interfaz gráfica principal del sistema de taxis"""
    
    def __init__(self):
        self.grid = GridNetwork(config.grid_width, config.grid_height)
        self.coordinator = None
        self.taxis = {}
        self.running = False
        
        # GUI setup
        self.root = tk.Tk()
        self.root.title("Sistema de Despacho de Taxis - Constraint Programming")
        self.root.geometry(f"{config.gui_width}x{config.gui_height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Variables de estado
        self.solver_type = tk.StringVar(value="OR-Tools" if OR_TOOLS_AVAILABLE else "Greedy")
        self.taxi_count = tk.StringVar(value="0")
        self.passenger_count = tk.StringVar(value="0")
        self.waiting_passengers = tk.StringVar(value="0")
        
        self._setup_gui()
        self._start_update_thread()
        
        logger.info("GUI initialized")
    
    def _setup_gui(self):
        """Configura la interfaz gráfica"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text="🚕 Sistema de Despacho de Taxis con Constraint Programming", 
                               font=("Arial", 16, "bold"))
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
        self.canvas = tk.Canvas(canvas_container,
                               width=min(canvas_width, 800),
                               height=min(canvas_height, 600),
                               bg="white",
                               scrollregion=(0, 0, canvas_width, canvas_height))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
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
            ("Solver activo:", self.solver_type)
        ]
        
        for i, (label, var) in enumerate(stats_data):
            ttk.Label(stats_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            ttk.Label(stats_frame, textvariable=var, font=("Arial", 10, "bold")).grid(
                row=i, column=1, sticky=tk.E, pady=2, padx=(10, 0))
        
        # Controles
        controls_frame = ttk.LabelFrame(control_frame, text="🎮 Controles", padding=10)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(controls_frame, text="🚀 Iniciar Sistema", 
                  command=self._start_system).pack(fill=tk.X, pady=2)
        ttk.Button(controls_frame, text="⏹️ Detener Sistema", 
                  command=self._stop_system).pack(fill=tk.X, pady=2)
        ttk.Button(controls_frame, text="👤 Agregar Pasajero", 
                  command=self._add_passenger).pack(fill=tk.X, pady=2)
        ttk.Button(controls_frame, text="🔄 Reset Sistema", 
                  command=self._reset_system).pack(fill=tk.X, pady=2)
        
        # Leyenda
        legend_frame = ttk.LabelFrame(control_frame, text="📋 Leyenda", padding=10)
        legend_frame.pack(fill=tk.X)
        
        legend_items = [
            ("◆", "Taxi disponible", "gold"),
            ("◆", "Taxi ocupado", "orange"),
            ("■", "Pasajero esperando", "blue"),
            ("▲", "Destino", "red"),
            ("╋", "Intersección", "gray")
        ]
        
        for symbol, description, color in legend_items:
            frame = ttk.Frame(legend_frame)
            frame.pack(fill=tk.X, pady=1)
            ttk.Label(frame, text=symbol, font=("Arial", 12), foreground=color).pack(side=tk.LEFT)
            ttk.Label(frame, text=description).pack(side=tk.LEFT, padx=(5, 0))
    
    def _setup_status_bar(self, parent):
        """Configura la barra de estado"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_text = tk.StringVar(value="Sistema detenido")
        status_label = ttk.Label(status_frame, textvariable=self.status_text, 
                                font=("Arial", 10), foreground="blue")
        status_label.pack(side=tk.LEFT)
        
        # Reloj
        self.clock_text = tk.StringVar()
        clock_label = ttk.Label(status_frame, textvariable=self.clock_text, 
                               font=("Arial", 10))
        clock_label.pack(side=tk.RIGHT)
        
        self._update_clock()
    
    def _draw_grid(self):
        """Dibuja la grilla de intersecciones"""
        self.canvas.delete("grid")
        
        cell_size = config.grid_cell_size
        
        # Dibujar líneas de grilla
        for x in range(self.grid.width + 1):
            x_pos = x * cell_size
            self.canvas.create_line(x_pos, 0, x_pos, self.grid.height * cell_size,
                                   fill="lightgray", width=1, tags="grid")
        
        for y in range(self.grid.height + 1):
            y_pos = y * cell_size
            self.canvas.create_line(0, y_pos, self.grid.width * cell_size, y_pos,
                                   fill="lightgray", width=1, tags="grid")
        
        # Dibujar intersecciones
        for intersection in self.grid.intersections:
            x = intersection.x * cell_size + cell_size // 2
            y = intersection.y * cell_size + cell_size // 2
            self.canvas.create_text(x, y, text="╋", font=("Arial", 8), 
                                   fill="gray", tags="grid")
    
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
                
                # Pasajero
                self.canvas.create_rectangle(x-6, y-6, x+6, y+6, 
                                           fill="blue", outline="darkblue", width=2,
                                           tags="entities")
                
                # Línea punteada al destino
                dest_x = passenger.dropoff_position.x * cell_size + cell_size // 2
                dest_y = passenger.dropoff_position.y * cell_size + cell_size // 2
                self.canvas.create_line(x, y, dest_x, dest_y, 
                                       fill="blue", width=1, dash=(3, 3), tags="entities")
                
                # Destino
                self.canvas.create_polygon(dest_x, dest_y-6, dest_x-5, dest_y+4, 
                                         dest_x+5, dest_y+4, 
                                         fill="red", outline="darkred", width=2,
                                         tags="entities")
                
                # ID del pasajero
                self.canvas.create_text(x, y+15, text=passenger.passenger_id[-2:], 
                                       font=("Arial", 8), fill="darkblue", tags="entities")
        
        # Dibujar taxis
        for taxi in self.coordinator.taxis.values():
            x = taxi.position.x * cell_size + cell_size // 2
            y = taxi.position.y * cell_size + cell_size // 2
            
            # Color según estado
            if taxi.state == TaxiState.IDLE:
                color = "gold"
                outline = "orange"
            else:
                color = "orange"
                outline = "darkorange"
            
            # Taxi (diamante)
            self.canvas.create_polygon(x, y-8, x+8, y, x, y+8, x-8, y,
                                     fill=color, outline=outline, width=2,
                                     tags="entities")
            
            # ID del taxi
            self.canvas.create_text(x, y-18, text=taxi.taxi_id, 
                                   font=("Arial", 8, "bold"), fill="black", tags="entities")
            
            # Línea hacia objetivo si existe
            if taxi.target_position:
                target_x = taxi.target_position.x * cell_size + cell_size // 2
                target_y = taxi.target_position.y * cell_size + cell_size // 2
                self.canvas.create_line(x, y, target_x, target_y, 
                                       fill=color, width=2, dash=(5, 5), tags="entities")
    
    def _start_system(self):
        """Inicia el sistema distribuido"""
        if self.running:
            messagebox.showwarning("Sistema", "El sistema ya está en ejecución")
            return
        
        try:
            # Iniciar sistema en hilo separado
            self.system_thread = threading.Thread(target=self._run_distributed_system, daemon=True)
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
        logger.info("System stopped")
    
    def _add_passenger(self):
        """Agrega un nuevo pasajero"""
        if self.coordinator:
            self.coordinator._create_new_passenger()
            self.status_text.set("Nuevo pasajero agregado")
        else:
            messagebox.showwarning("Sistema", "Inicie el sistema primero")
    
    def _reset_system(self):
        """Reinicia el sistema"""
        self._stop_system()
        time.sleep(1)
        self._start_system()
    
    def _run_distributed_system(self):
        """Ejecuta el sistema distribuido en hilo separado"""
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
            
            # Crear usuarios XMPP
            await self._setup_xmpp_users()
            
            # Crear coordinador
            coordinator_jid = f"coordinator@{config.openfire_domain}"
            self.coordinator = CoordinatorAgent(coordinator_jid, "coordinator_pass", self.grid)
            await self.coordinator.start()
            
            # Crear taxis
            await self._create_taxis()
            
            self.status_text.set("Sistema activo - Agentes conectados")
            
            # Loop principal
            last_update = time.time()
            while self.running:
                current_time = time.time()
                dt = current_time - last_update
                
                # Actualizar tiempos de espera
                if self.coordinator:
                    self.coordinator.update_passenger_wait_times(dt)
                
                # Actualizar estadísticas
                self._update_stats()
                
                last_update = current_time
                await asyncio.sleep(0.05)  # 20 FPS
                
        except Exception as e:
            logger.error(f"Async system error: {e}")
            self.status_text.set(f"Error: {e}")
        finally:
            # Cleanup
            await self._cleanup_agents()
            self.running = False
    
    def _check_openfire(self) -> bool:
        """Verifica conexión con OpenFire"""
        try:
            import requests
            response = requests.get(f"http://{config.openfire_host}:{config.openfire_port}", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def _setup_xmpp_users(self):
        """Configura usuarios XMPP"""
        try:
            # Crear usuario coordinador
            openfire_api.create_user("coordinator", "coordinator_pass", "Coordinator Agent")
            
            # Crear usuarios para taxis
            for i in range(3):
                taxi_id = f"taxi_{i}"
                openfire_api.create_user(taxi_id, f"{taxi_id}_pass", f"Taxi Agent {i}")
                
            logger.info("XMPP users created")
        except Exception as e:
            logger.warning(f"XMPP user creation error (might exist): {e}")
    
    async def _create_taxis(self):
        """Crea agentes taxi"""
        for i in range(3):
            taxi_id = f"taxi_{i}"
            taxi_jid = f"{taxi_id}@{config.openfire_domain}"
            
            initial_pos = self.grid.get_random_intersection()
            taxi_agent = TaxiAgent(taxi_jid, f"{taxi_id}_pass", taxi_id, initial_pos, self.grid)
            
            await taxi_agent.start()
            self.taxis[taxi_id] = taxi_agent
            
            logger.info(f"Created taxi agent {taxi_id}")
    
    async def _cleanup_agents(self):
        """Limpia agentes al cerrar"""
        try:
            for taxi in self.taxis.values():
                await taxi.stop()
            
            if self.coordinator:
                await self.coordinator.stop()
                
            logger.info("Agents cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def _update_stats(self):
        """Actualiza estadísticas de la GUI"""
        if self.coordinator:
            waiting = sum(1 for p in self.coordinator.passengers.values() 
                         if p.state == PassengerState.WAITING)
            
            self.taxi_count.set(str(len(self.coordinator.taxis)))
            self.passenger_count.set(str(len(self.coordinator.passengers)))
            self.waiting_passengers.set(str(waiting))
    
    def _update_clock(self):
        """Actualiza el reloj"""
        import datetime
        now = datetime.datetime.now()
        self.clock_text.set(now.strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)
    
    def _start_update_thread(self):
        """Inicia hilo de actualización visual"""
        def update_loop():
            while True:
                try:
                    if self.running:
                        # Programar actualización en hilo principal
                        self.root.after(0, self._draw_entities)
                    time.sleep(1/config.fps)  # 20 FPS
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

# ==================== SCRIPT PRINCIPAL ====================

def main():
    """Función principal"""
    print("🚕 Sistema de Despacho de Taxis con Constraint Programming")
    print("=" * 60)
    print(f"Grid: {config.grid_width}x{config.grid_height}")
    print(f"OR-Tools disponible: {'✅' if OR_TOOLS_AVAILABLE else '❌'}")
    print(f"SPADE disponible: {'✅' if SPADE_AVAILABLE else '❌'}")
    print(f"OpenFire: {config.openfire_host}:{config.openfire_port}")
    print("=" * 60)
    
    if not SPADE_AVAILABLE:
        print("❌ Error: SPADE no está disponible")
        print("Instalar con: pip install spade")
        return
    
    try:
        # Crear y ejecutar GUI
        gui = GridTaxiGUI()
        gui.run()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Error en aplicación: {e}")

if __name__ == "__main__":
    main()
