# Sistema de Movimiento y Dinámicas Sociales para Agentes Ideológicos

## 🎯 Funcionalidades Implementadas

### 1. Sistema de Movimiento
- **Movimiento basado en fuerzas sociales**: Los agentes se mueven hacia agentes similares y se alejan de los diferentes
- **Restricciones de movimiento**: Solo pueden moverse a posiciones libres dentro de su rango
- **Exploración aleatoria**: Cuando no hay fuerzas sociales significativas, realizan movimiento aleatorio
- **Parámetros configurables**: 
  - `movement_range`: Distancia máxima de movimiento por paso (2.0)
  - `movement_interval`: Tiempo entre intentos de movimiento (1.5s)
  - `movement_probability`: Probabilidad de intentar moverse (0.3)

### 2. Reglas de Cambio de Ideología
- **Regla del 60%**: Un agente solo cambia de ideología si más del 60% de sus vecinos tienen una ideología diferente
- **Período de enfriamiento**: No puede cambiar ideología inmediatamente después de un cambio previo
- **Presión social**: El cambio se basa en la ideología dominante entre vecinos

### 3. Sistema de Comunidades Avanzado
- **Formación por compatibilidad**: Solo agentes con ideologías compatibles pueden formar comunidades
- **Límites de tamaño**: 
  - Mínimo: 3 miembros
  - Máximo: 50 miembros
- **División automática**: Las comunidades grandes pueden dividirse por radicalización
- **Detección de conflictos**: Identificación automática de tensiones entre comunidades

### 4. Dinámicas Sociales Complejas
- **Atracción/Repulsión**: 
  - `seek_similar_probability`: 0.7 (probabilidad de moverse hacia similares)
  - `avoid_different_probability`: 0.4 (probabilidad de alejarse de diferentes)
- **Radicalización**: Presión hacia posturas más extremas en comunidades grandes y uniformes
- **Segregación**: Tendencia natural a formar grupos homogéneos

## 🔧 Parámetros de Configuración

### Movimiento
```python
movement_range: float = 2.0              # Rango máximo de movimiento
movement_interval: float = 1.5           # Intervalo entre movimientos
movement_probability: float = 0.3        # Probabilidad de moverse
seek_similar_probability: float = 0.7    # Atracción a similares
avoid_different_probability: float = 0.4 # Repulsión de diferentes
```

### Ideología y Presión Social
```python
ideology_pressure_threshold: float = 0.6        # 60% para cambio de ideología
radicalization_threshold: float = 0.8           # Umbral de radicalización
community_compatibility_threshold: float = 0.75 # Compatibilidad para comunidades
conflict_threshold: float = 0.5                 # Umbral para conflictos
```

### Comunidades
```python
min_community_size: int = 3    # Tamaño mínimo de comunidad
max_community_size: int = 50   # Tamaño máximo de comunidad
```

## 🚀 Comportamientos Implementados

### 1. MovementBehaviour
- Ejecuta cada 1.5 segundos
- Calcula fuerzas sociales de atracción/repulsión
- Busca posiciones válidas dentro del rango
- Actualiza la posición en el registro global

### 2. IdeologyBroadcastBehaviour  
- Anuncia la ideología y posición periódicamente
- Mantiene actualizada la red de vecinos
- Permite descubrimiento dinámico de agentes

### 3. DecisionMakingBehaviour
- Evalúa cambios de ideología según la regla del 60%
- Considera el período de enfriamiento
- Registra historial de cambios ideológicos

### 4. CommunityManagementBehaviour
- Gestiona formación y disolución de comunidades
- Implementa reglas de compatibilidad
- Detecta conflictos entre grupos
- Maneja división de comunidades por sobrepoblación

## 📊 Métricas y Monitoreo

El sistema rastrea:
- **Posiciones** de todos los agentes en tiempo real
- **Cambios ideológicos** con historial temporal
- **Formación/disolución** de comunidades
- **Conflictos** entre grupos
- **Patrones de movimiento** y segregación

## 🎮 Integración con WebSockets

- Actualizaciones en tiempo real cada segundo
- Visualización de movimiento de agentes
- Monitoreo de dinámicas comunitarias
- Detección visual de conflictos y segregación

## 🧪 Modelos Inspirados

El sistema se basa en:
- **Modelo de Schelling**: Segregación social por preferencias
- **Modelo de Axelrod**: Difusión cultural entre agentes
- **Algoritmos Boids**: Comportamiento emergente de grupos
- **Redes sociales**: Dinámicas de polarización y eco chambers

## 📈 Comportamientos Emergentes Esperados

1. **Segregación espacial**: Formación de clusters ideológicos
2. **Polarización**: Radicalización en comunidades aisladas
3. **Conflictos territoriales**: Tensiones en fronteras entre grupos
4. **Migración ideológica**: Movimiento hacia áreas compatibles
5. **Fusión/división**: Dinámicas de comunidades según presiones sociales

Este sistema simula de manera realista las dinámicas sociales complejas donde la ideología, la proximidad física, y la presión social interactúan para crear patrones emergentes de comportamiento colectivo.

## ⏰ Sistema de Timing Preciso

### Movimiento cada 1.5 segundos exactos:

1. **PeriodicBehaviour**: Cada agente tiene un `MovementBehaviour` que se ejecuta automáticamente cada `config.movement_interval = 1.5` segundos
2. **Ciclo de Movimiento**:
   ```
   T+0.0s  → Agente calcula fuerzas sociales
   T+0.0s  → Agente intenta moverse
   T+0.0s  → Agente actualiza posición si es válida
   T+1.5s  → Siguiente ciclo de movimiento
   T+3.0s  → Siguiente ciclo de movimiento
   T+4.5s  → ...y así sucesivamente
   ```

3. **Logging de Movimientos**: 
   - `DEBUG`: Intentos de movimiento y cálculos
   - `INFO`: Movimientos exitosos con coordenadas
   - `ERROR`: Fallos en el sistema de movimiento

### Probabilidades de Movimiento Ajustadas:

- **70% probabilidad** de intentar movimiento cada 1.5s (era 30%)
- **80% probabilidad** de atracción hacia agentes similares (era 70%)
- **60% probabilidad** de repulsión de agentes diferentes (era 40%)
- **Umbral de fuerza reducido** para movimientos más sensibles (0.05 vs 0.1)
- **Distancia mínima** de movimiento (0.5 unidades) para evitar micro-movimientos

### Test de Verificación:

Ejecuta `python test_movement.py` para verificar que:
- Los agentes se mueven exactamente cada 1.5 segundos
- El sistema registra todos los movimientos con timestamps
- Las fuerzas sociales funcionan correctamente (atracción/repulsión)
