# Sistema de Despacho de Taxis con Movimiento en Grilla

## Descripción
Sistema de despacho de taxis con movimiento cuadriculado desarrollado con GUI Tkinter. Los taxis se mueven únicamente en **direcciones cardinales** (arriba, abajo, izquierda, derecha) sobre una grilla, simulando el movimiento en una ciudad real.

## Características Principales

### 🏙️ Movimiento en Grilla Urbana
- **Movimiento cardinal únicamente**: Taxis se mueven solo arriba, izquierda, abajo, derecha
- **Sin movimiento diagonal**: Elimina la complejidad de movimiento libre
- **Grilla visual**: La interfaz muestra la grilla de movimiento
- **Posiciones alineadas**: Todos los elementos se alinean automáticamente a la grilla
- **Simplicidad urbana**: Simula el movimiento real en bloques de ciudad

### 🚕 Simulación de Taxis Simplificada
- **Movimiento libre (Free Roaming)**: Taxis se mueven por la grilla cuando no tienen asignación
- **Interpolación fluida**: Animaciones suaves entre posiciones de grilla
- **Estados dinámicos**: Disponible, ocupado, en movimiento
- **Capacidad configurable**: Diferentes capacidades de pasajeros
- **Retorno automático**: Tras dejar pasajeros, vuelven al modo de búsqueda libre

### 👥 Gestión de Clientes en Grilla
- **Destinos en grilla**: Cada cliente elige un destino alineado a la grilla
- **Posiciones de grilla**: Clientes aparecen en intersecciones de la grilla
- **Visualización clara**: Destinos y rutas claramente marcados
- **Prioridad por discapacidad**: Clientes con discapacidad tienen prioridad especial
- **Generación automática**: Sistema mantiene población mínima de clientes

### 🎯 Asignación Inteligente Simplificada
- **Asignación por distancia**: Considera la distancia en la grilla
- **Priorización automática**: Considera discapacidad y distancia
- **Asignación en tiempo real**: Evaluación continua de mejores coincidencias
- **Sistema simplificado**: Enfoque en la funcionalidad core

### 🖥️ Interfaz Visual Optimizada
- **Alto rendimiento**: ~60 FPS con animaciones fluidas sobre grilla
- **Grilla visible**: Muestra claramente la estructura de movimiento
- **Visualización clara**: Destinos, rutas y estados fáciles de entender
- **Información en tiempo real**: Tiempo de espera, multiplicador de rango para cada cliente
- **Interactividad**: Clic para agregar clientes manualmente
- **Controles de simulación**: Botón pause/resume
- **Estadísticas avanzadas**: Métricas de eficiencia, viajes completados, FPS
- **Grid visual**: Rejilla de referencia con coordenadas

## ✨ Nuevas Características (v2.0)

### 🆕 Comportamiento de Taxis Mejorado
- **Free Roaming**: Los taxis se mueven libremente por el mapa cuando no tienen asignación
- **Búsqueda activa**: Movimiento inteligente para encontrar pasajeros
- **Algoritmos de pathfinding**: Movimiento optimizado evitando concentraciones

### 🆕 Sistema de Clientes Dinámico
- **Destinos específicos**: Cada cliente tiene un destino único en el mapa (no solo esquinas)
- **Rango expansivo**: El área de búsqueda de taxis se incrementa si el cliente espera mucho
- **Visualización de estado**: Círculos que muestran el rango actual de búsqueda
- **Tiempo de espera visible**: Contador en tiempo real para cada cliente

### 🆕 Optimizaciones del Sistema
- **Código limpio**: Eliminado todo el código defensivo innecesario
- **Imports directos**: Sin verificaciones condicionales de disponibilidad
- **Lógica esencial**: Solo funcionalidad core para máximo rendimiento

## Instalación y Uso

### Requisitos
```bash
pip install -r requirements.txt
```

### Ejecutar Sistema de Grilla
```bash
python demo_taxi_dispatch.py
```

### Tests Disponibles
```bash
# Test rápido de movimiento en grilla
python test_quick.py

# Test de calidad de movimiento
python test_movement_quality.py

# Test de sistema completo
python test_system_ready.py
```

### Controles
- **Clic izquierdo**: Agregar cliente en esa posición (se alinea automáticamente a la grilla)
- **Botón Pause**: Pausar/reanudar simulación
- **Cerrar ventana**: Terminar demostración

## Sistema de Grilla
- **Tamaño de celda**: 10.0 unidades
- **Área de movimiento**: -40 a +40 en ambos ejes (grilla 9x9)
- **Direcciones**: Solo arriba, abajo, izquierda, derecha
- **Alineación automática**: Todas las posiciones se ajustan a la grilla

## Archivos Principales

### Core del Sistema
- `demo_taxi_dispatch.py` - Demo principal con Tkinter
- `src/gui/taxi_tkinter_gui.py` - GUI principal de Tkinter
- `src/agent/agent.py` - Lógica de agentes de taxi
- `src/agent/client_agent.py` - Lógica de agentes de cliente

### Archivos de Configuración
- `src/config.py` - Configuración general
- `requirements.txt` - Dependencias del proyecto

## Mejoras Implementadas

### Optimizaciones de Rendimiento
- ✅ Migración completa a Tkinter (eliminado Pygame)
- ✅ Interpolación cúbica para movimiento suave
- ✅ Renderizado optimizado con Canvas
- ✅ Gestión eficiente de eventos
- ✅ Threading para simulaciones de fondo

### Funcionalidades Mejoradas
- ✅ **Recogida automática**: Los pasajeros desaparecen al ser recogidos
- ✅ **Generación continua**: Nuevos clientes aparecen automáticamente
- ✅ **Población mínima**: Sistema mantiene 6+ clientes siempre
- ✅ **Estadísticas en tiempo real**: FPS, contadores de entidades
- ✅ **Interfaz limpia**: Eliminación de archivos obsoletos

### Arquitectura
- **Separación de responsabilidades**: GUI independiente de lógica de negocio
- **Threading seguro**: Operaciones de GUI en hilo principal
- **Gestión de estado**: Estados de taxi y cliente bien definidos
- **Escalabilidad**: Fácil agregar más funcionalidades

### Limpieza de Código
- ✅ **Eliminación de código defensivo**: Removidas verificaciones innecesarias de importaciones
- ✅ **Simplificación de imports**: Imports directos sin try/except cuando no es necesario
- ✅ **Código más limpio**: Eliminados archivos duplicados y código redundante
- ✅ **Mejor mantenibilidad**: Estructura de código más simple y legible
- ✅ **Menos líneas de código**: Manteniendo la misma funcionalidad con menos complejidad

## Estructura del Proyecto
```
tfsito/
├── demo_taxi_dispatch.py          # Demo principal
├── src/
│   ├── gui/
│   │   └── taxi_tkinter_gui.py     # GUI principal (Tkinter)
│   ├── agent/
│   │   ├── agent.py                # Agente de taxi
│   │   ├── client_agent.py         # Agente de cliente
│   │   └── libs/
│   │       └── taxi_constraints.py # Restricciones OR-Tools
│   └── services/
│       └── openfire_api.py         # API para SPADE/XMPP
├── requirements.txt                # Dependencias
└── README.md                       # Este archivo
```

## Próximas Mejoras
- [ ] Integración con sistema de restricciones OR-Tools
- [ ] Métricas de rendimiento del sistema
- [ ] Mapas reales con coordenadas GPS
- [ ] Base de datos para persistencia
- [ ] API REST para integración externa

## Desarrollo
Desarrollado como parte del curso de Tópicos en Inteligencia Artificial, enfocado en sistemas multi-agente y optimización de interfaces de usuario.
