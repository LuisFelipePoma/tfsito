# Sistema de Despacho Inteligente de Taxis

## Descripción
Sistema de despacho de taxis con visualización en tiempo real desarrollado con GUI Tkinter para máxima fluidez y simplicidad visual.

## Características Principales

### 🚕 Simulación de Taxis Avanzada
- **Movimiento libre (Free Roaming)**: Taxis se mueven autónomamente cuando no tienen asignación
- **Interpolación fluida**: Animaciones suaves entre posiciones
- **Estados dinámicos**: Disponible, ocupado, en movimiento, buscando pasajeros
- **Capacidad configurable**: Diferentes capacidades de pasajeros (4-6)
- **Retorno automático**: Tras dejar pasajeros, vuelven al modo de búsqueda libre

### 👥 Gestión de Clientes Inteligente
- **Destinos personalizados**: Cada cliente elige un destino específico en el mapa
- **Rango de búsqueda dinámico**: Aumenta gradualmente si ningún taxi los recoge
- **Visualización de espera**: Muestra tiempo esperando y radio de búsqueda actual
- **Prioridad por discapacidad**: Clientes con discapacidad tienen prioridad especial
- **Generación automática**: Sistema mantiene población mínima de clientes

### 🎯 Asignación Inteligente con OR-Tools
- **Algoritmo de restricciones**: Usa OR-Tools CP-SAT para decisiones óptimas
- **Rango expansivo**: Clientes expanden su radio de búsqueda con el tiempo
- **Priorización automática**: Considera discapacidad, distancia y tiempo de espera
- **Asignación en tiempo real**: Evaluación continua de mejores coincidencias

### 🖥️ Interfaz Visual Avanzada
- **Alto rendimiento**: ~60 FPS con animaciones fluidas
- **Visualización completa**: Destinos de clientes, líneas de ruta, rangos de búsqueda
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

### Ejecutar Demostración
```bash
python demo_taxi_dispatch.py
```

### Controles
- **Clic izquierdo**: Agregar cliente en esa posición
- **Botón Pause**: Pausar/reanudar simulación
- **Cerrar ventana**: Terminar demostración

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
