# 🚕 Sistema de Taxis con Constraint Programming

Sistema inteligente de despacho de taxis que utiliza **Constraint Programming** (OR-Tools) para asignación óptima y **SPADE/OpenFire** para comunicación entre agentes.

## 🎯 Características Principales

- **Constraint Programming**: Asignación óptima de taxis usando OR-Tools
- **Sistema Multi-Agente**: Comunicación SPADE/XMPP con OpenFire
- **Prioridades Realistas**: Pasajeros vulnerables (discapacidad, embarazo, adulto mayor)
- **Optimización Inteligente**: Considera distancia, tiempo de espera, ganancia/km
- **Interfaz Gráfica**: Visualización en tiempo real con Tkinter

## 🚀 Instalación Rápida

### 1. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2. Iniciar OpenFire (opcional)
```bash
docker run -d -p 9090:9090 -p 5222:5222 --name openfire gizmotronic/openfire
```

### 3. Ejecutar Sistema
```bash
python run_taxi_system.py
```

## 📁 Estructura del Proyecto

```
tfsito/
├── src/
│   ├── main.py                 # Punto de entrada principal
│   ├── taxi_dispatch_system.py # Lógica de agentes y constraint programming
│   ├── taxi_dispatch_gui.py    # Interfaz gráfica
│   ├── config.py              # Configuración del sistema
│   └── services/
│       └── openfire_api.py    # API de OpenFire
├── run_taxi_system.py         # Script de inicio
├── requirements.txt           # Dependencias
└── README.md                 # Este archivo
```

## 🔧 Configuración

El sistema se puede configurar editando `src/config.py`:

- **Grid**: Tamaño de la grilla (por defecto 20x20)
- **Taxis**: Número de taxis (por defecto 3)
- **OpenFire**: Host y puerto del servidor XMPP
- **Algoritmo**: Parámetros del constraint solver

## 🎮 Uso

1. **Inicio**: Ejecuta `python run_taxi_system.py`
2. **Visualización**: La GUI muestra taxis (diamantes) y pasajeros (cuadrados)
3. **Estados**:
   - **🟡 Taxi IDLE**: Patrullando (dorado)
   - **🟠 Taxi OCUPADO**: Recogiendo/transportando (naranja)
   - **🔵 Pasajero**: Esperando taxi (azul)
   - **🔴 Destino**: Punto de entrega (rojo)

## ⚡ Algoritmo de Asignación

El sistema usa **Constraint Programming** con las siguientes prioridades:

1. **Prioridad Absoluta**: Pasajeros vulnerables
2. **Ganancia/Km**: Maximizar eficiencia económica
3. **Tiempo de Espera**: Atender a quien más tiempo lleva esperando
4. **Distancia**: Minimizar tiempo de recogida (ETA)
5. **Zonas de Demanda**: Priorizar áreas de alta demanda

## 🐛 Solución de Problemas

### Los taxis no recogen pasajeros
- Verifica que OpenFire esté corriendo
- Revisa los logs en consola para errores de conexión SPADE
- Asegúrate de que las dependencias estén instaladas

### Error de SPADE
- En Windows, puede requerir Visual Studio Build Tools
- Alternativa: `conda install spade-platform`
- O usar Docker para evitar problemas de dependencias

### Error de OR-Tools
```bash
pip install --upgrade ortools
```

## 📊 Métricas del Sistema

- **Taxis Activos**: Número de taxis conectados
- **Pasajeros Esperando**: Cola de asignación
- **Eficiencia**: Tiempo promedio de recogida
- **Asignaciones**: Total de viajes completados

## 🔬 Tecnologías Utilizadas

- **Python 3.8+**: Lenguaje base
- **OR-Tools**: Constraint Programming
- **SPADE**: Framework de agentes multi-agente
- **OpenFire**: Servidor XMPP
- **Tkinter**: Interfaz gráfica
- **asyncio**: Programación asíncrona

---

**Desarrollado para demostrar la aplicación de Constraint Programming en sistemas de transporte inteligente.**
