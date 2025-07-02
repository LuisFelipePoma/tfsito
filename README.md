# TFS ### Arquitectura

1. **Environment Agent**: Agente central que mantiene información del entorno (aeropuertos, límites del espacio aéreo) y proporciona una interfaz web para monitoreo.

2. **Tower Agents**: Torres de control que:
   - Se registran con el Environment Agent
   - **Crean y gestionan aeronaves dinámicamente**
   - Registran aeronaves en OpenFire via API REST
   - Simulan el comportamiento de las aeronaves
   - Reportan posiciones al Environment Agent

3. **OpenFire Server**: Servidor XMPP que facilita la comunicación entre todos los agentes y donde se registran las aeronaves dinámicamente.

### Flujo del Sistema

1. **Inicio del Sistema**: 
   - Se inicia OpenFire XMPP Server
   - Se inicia Environment Agent (interfaz web disponible)
   - Se inician Torre Agents

2. **Registro de Torres**:
   - Cada Torre se registra con el Environment Agent
   - Environment Agent responde con información del entorno

3. **Creación Dinámica de Aeronaves**:
   - Cada Torre crea aeronaves automáticamente (cada 30 segundos)
   - Límite de 5 aeronaves por torre
   - Las aeronaves se registran en OpenFire via API REST
   - Se notifica al Environment Agent

4. **Simulación de Vuelo**:
   - Las Torres simulan el comportamiento de sus aeronaves
   - Se reportan posiciones cada 2 segundos al Environment Agent
   - Las aeronaves se mueven hacia objetivos aleatorios

5. **Monitoreo**:
   - La interfaz web muestra todas las aeronaves en tiempo real
   - Actualización automática cada 2 segundosffic Flow System with Intelligent Tower Operations

## Descripción del Sistema

Este sistema implementa una simulación de tráfico aéreo con agentes inteligentes que se comunican a través de XMPP (Openfire) para coordinar el control del espacio aéreo.

### Arquitectura

1. **Environment Agent**: Agente central que mantiene información del entorno (aeropuertos, límites del espacio aéreo) y proporciona una interfaz web para monitoreo.

2. **Tower Agents**: Torres de control que gestionan aeronaves en sus respectivos aeropuertos.

3. **Aircraft Agents**: Aeronaves que reportan su posición y reciben instrucciones de las torres.

4. **Openfire Server**: Servidor XMPP que facilita la comunicación entre todos los agentes.

### Uso Rápido

#### Iniciar el sistema completo
```bash
cd src
docker-compose up --build
```

#### Acceder a la interfaz web
- **URL**: http://localhost:8080
- Muestra mapa en tiempo real con aeronaves, torres y aeropuertos
- Actualización automática cada 2 segundos

#### Acceder a Openfire Admin
- **URL**: http://localhost:9090
- **Usuario**: admin
- **Contraseña**: admin

### Componentes

#### Environment Agent
- **Puerto Web**: 8080 (interfaz de monitoreo)
- **Puerto WebSocket**: 8765 (compatibilidad legacy)
- **Funciones**:
  - Mantiene información de aeropuertos y límites del espacio aéreo
  - Proporciona API REST para datos de aeronaves, torres y aeropuertos
  - Interfaz web con mapa en tiempo real
  - Comunicación XMPP con torres y aeronaves

#### Tower Agents
- **TWR_SABE**: Torre del Aeropuerto Jorge Newbery (Buenos Aires)
- **TWR_SAEZ**: Torre del Aeropuerto Ezeiza
- **TWR_SADP**: Torre de La Plata (opcional, con profile extended)
- **Funciones**:
  - Se registra con el Environment Agent
  - **Crea aeronaves dinámicamente** (máximo 5 por torre)
  - **Registra aeronaves en OpenFire** via API REST
  - **Simula comportamiento de aeronaves** (movimiento, reportes)
  - Envía reportes de posición al Environment Agent

#### Aeronaves (Creadas Dinámicamente)
- **Nombres**: SABE_XXX, SAEZ_XXX, SADP_XXX (donde XXX es un número aleatorio)
- **Funciones**:
  - Son **creadas y simuladas por las Torres**
  - **Registradas automáticamente en OpenFire**
  - Simulan vuelo con movimiento realista
  - Reportan posición cada 2 segundos via Torres
  - Se mueven hacia objetivos aleatorios

### API Endpoints

El Environment Agent expone los siguientes endpoints:

- `GET /api/aircraft` - Datos de todas las aeronaves
- `GET /api/towers` - Datos de todas las torres
- `GET /api/airports` - Información de aeropuertos

### Aeropuertos Configurados

- **SABE**: Jorge Newbery Airfield (Buenos Aires)
- **SAEZ**: Ezeiza International Airport
- **SADP**: La Plata Airport

## Deploy Manual (Método Anterior)

## Deploy OpenFire Service

```bash
docker pull sameersbn/openfire:3.10.3-19
```

```bash
docker run --name openfire -d --restart=always \
  --publish 9090:9090 --publish 5222:5222 --publish 7777:7777 \
  --volume /srv/docker/openfire:/var/lib/openfire \
  sameersbn/openfire:3.10.3-19
```

```bash
docker run --name openfire -d --restart=always  --publish 9090:9090 --publish 5222:5222 --publish 7777:7777  --volume /srv/docker/openfire:/var/lib/openfire sameersbn/openfire:3.10.3-19
```

Download Plugin for [`REST API (3.10)`](https://www.igniterealtime.org/projects/openfire/plugin-archive.jsp?plugin=restapi)


## Deploy Agents

### Deploy Tower
### Deploy Master

