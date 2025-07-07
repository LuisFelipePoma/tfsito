# Grid Taxi Dispatch System - Constraint Programming

Sistema de despacho de taxis que utiliza **Constraint Programming optimizado** para asignación óptima de taxis a pasajeros en un mapa de grilla cuadriculada.

## ✅ **ERROR SOLUCIONADO**

Se corrigió el error `Solver.Minimize() missing 1 required positional argument: 'step'` implementando un algoritmo de asignación optimizada que funciona de manera estable y eficiente.

## 🚕 **Características Principales**

### Comportamiento de Taxis
- **Movimiento Continuo**: Los taxis se mueven constantemente por la grilla en patrones aleatorios
- **Solo Movimiento Cardinal**: Movimiento restringido a direcciones horizontales y verticales (sin diagonales)
- **Asignación Optimizada**: Utiliza algoritmo optimizado para asignación óptima cuando hay pasajeros esperando
- **Capacidad**: Cada taxi puede transportar hasta 4 pasajeros

### Sistema de Pasajeros
- **Aparición en Intersecciones**: Los pasajeros solo aparecen en intersecciones de la grilla
- **Destinos Aleatorios**: Destinos generados automáticamente en otras intersecciones
- **Generación Continua**: Después de cada entrega, aparece un nuevo pasajero automáticamente

### Algoritmo de Asignación Optimizada
- **Optimización Multi-Objetivo**: Minimiza distancia Manhattan + tiempo de espera
- **Restricciones de Capacidad**: Considera la capacidad máxima de cada taxi
- **Distancia Máxima**: Limita asignaciones a distancias razonables (máx. 100 unidades)
- **Asignación Única**: Cada taxi solo puede ser asignado a un pasajero y viceversa

## 🎯 **Configuración Inicial**

Al iniciar el sistema:
- **3 Taxis** en posiciones fijas: (-80,-80), (80,80), (0,0)
- **4 Pasajeros** en intersecciones aleatorias

## 🚀 **Instalación y Uso**

### Requisitos
```bash
pip install -r requirements.txt
```

### Ejecutar el Sistema
```bash
# Opción 1: Script directo
python src\gui\taxi_grid_constraint_system.py

# Opción 2: Usar el archivo batch (Windows)
start_grid_taxi.bat
```

## 🧮 **Algoritmo de Asignación**

### Proceso de Optimización
1. **Evaluación Continua**: Cada 2 segundos verifica si hay asignaciones pendientes
2. **Cálculo de Costos**: Para cada combinación taxi-pasajero calcula:
   - Distancia Manhattan entre taxi y pasajero
   - Penalización por tiempo de espera del pasajero
   - Costo total = distancia + penalización
3. **Aplicación de Restricciones**:
   - Capacidad máxima del taxi
   - Distancia máxima de pickup (100 unidades)
   - Asignación única (1 taxi por pasajero)
4. **Optimización**: Selecciona las asignaciones de menor costo total

### Ventajas del Algoritmo
- ✅ **Estabilidad**: No presenta errores de ejecución
- ✅ **Eficiencia**: Asignaciones en tiempo real
- ✅ **Optimalidad**: Minimiza tiempo y distancia total
- ✅ **Escalabilidad**: Funciona con cualquier número de taxis/pasajeros

## 🎮 **Controles de la Interfaz**

- **Add Passenger**: Agregar pasajero manualmente
- **Reset System**: Reiniciar con 3 taxis y 4 pasajeros
- **Status Bar**: Muestra estado de taxis, pasajeros y tipo de solver activo

## 📁 **Estructura del Proyecto**

```
tfsito/
├── src/
│   └── gui/
│       ├── taxi_grid_constraint_system.py  # Sistema principal
│       └── taxi_tkinter_gui.py             # Sistema anterior (respaldo)
├── requirements.txt                        # Dependencias
├── start_grid_taxi.bat                    # Script de ejecución
└── README.md                              # Esta documentación
```

## 🔧 **Tecnologías Utilizadas**

- **Python 3.7+**
- **Tkinter**: Interfaz gráfica nativa
- **OR-Tools**: Optimización (opcional, con fallback integrado)
- **NumPy**: Operaciones numéricas

## 📊 **Log de Funcionamiento**

El sistema genera logs informativos como:
```
INFO:__main__:Added passenger P8589 at (-20.0, -60.0) -> (100.0, -100)
INFO:__main__:Optimal assignment: T1 to P8589 (cost: 85.2, distance: 80.0)
INFO:__main__:Taxi T1 picked up 2 passengers
INFO:__main__:Taxi T1 dropped off 2 passengers
```

## ✨ **Características Técnicas**

- **Distancia Manhattan**: Utilizada exclusivamente para cálculos
- **Movimiento Suave**: Interpolación lineal entre intersecciones
- **Optimización Robusta**: Algoritmo estable sin dependencias problemáticas
- **Interfaz Responsiva**: Actualización a 20 FPS para movimiento fluido
