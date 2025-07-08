# 🚕 SISTEMA DE TAXIS DISTRIBUIDO
# ================================

## ✅ CUMPLIMIENTO DE REQUISITOS ACADÉMICOS

Este sistema cumple con el requisito:
> **"El sistema debe ser desplegado de manera distribuida en por lo menos 2 Hosts remotos"**

### 📊 ARQUITECTURA DISTRIBUIDA

- **Total de Hosts**: 4
- **Hosts Remotos**: 3 (excluye coordinador)
- **Capacidad Total**: 400 agentes

### 🏗️ CONFIGURACIÓN DE HOSTS

#### COORDINATOR
- **IP**: `192.168.1.100`
- **Tipo**: `coordinator`
- **Capacidad**: 50 agentes
- **Descripción**: Host Central - Coordinador del sistema

#### TAXI_HOST_1
- **IP**: `192.168.1.101`
- **Tipo**: `taxi_host`
- **Capacidad**: 100 agentes
- **Descripción**: Host Remoto 1 - Agentes Taxi

#### PASSENGER_HOST_1
- **IP**: `192.168.1.102`
- **Tipo**: `passenger_host`
- **Capacidad**: 150 agentes
- **Descripción**: Host Remoto 2 - Agentes Pasajero

#### TAXI_HOST_2
- **IP**: `192.168.1.103`
- **Tipo**: `taxi_host`
- **Capacidad**: 100 agentes
- **Descripción**: Host Remoto 3 - Agentes Taxi Adicional (Opcional)

### 🔧 CONFIGURACIÓN OPENFIRE

```bash
# Ejecutar OpenFire
docker run --name openfire -d --restart=always \
  --publish 9090:9090 --publish 5222:5222 --publish 7777:7777 \
  --volume /srv/docker/openfire:/var/lib/openfire \
  sameersbn/openfire:3.10.3-19

# Credenciales
Usuario Admin: admin
Contraseña: 123
Secret Key: jNw5zFIsgCfnk75M
```

### 🚀 DESPLIEGUE PASO A PASO

#### 1. Preparar OpenFire (Host Principal)
Ejecutar el comando Docker arriba y configurar en http://localhost:9090

#### 2. Copiar Proyecto a Cada Host
```bash
# En cada host remoto
mkdir -p /opt/taxi_system
# Copiar todos los archivos del proyecto
```

#### 3. Ejecutar en Cada Host

##### Host 1: COORDINATOR
```bash
cd /opt/taxi_system
cp config/coordinator.env .env
python src/distributed_multi_host_system.py --type coordinator
```

##### Host 2: TAXI_HOST_1
```bash
cd /opt/taxi_system
cp config/taxi_host_1.env .env
python src/distributed_multi_host_system.py --type taxi_host
```

##### Host 3: PASSENGER_HOST_1
```bash
cd /opt/taxi_system
cp config/passenger_host_1.env .env
python src/distributed_multi_host_system.py --type passenger_host
```

##### Host 4: TAXI_HOST_2
```bash
cd /opt/taxi_system
cp config/taxi_host_2.env .env
python src/distributed_multi_host_system.py --type taxi_host
```

### 🔍 VERIFICACIÓN

```bash
# Verificar configuración
python verify_distributed_setup.py

# Monitorear logs
tail -f taxi_system.log
```

### 📁 ARCHIVOS IMPORTANTES

- `config/*.env` - Configuraciones por host
- `src/distributed_multi_host_system.py` - Sistema principal
- `deploy_distributed_auto.*` - Scripts de despliegue
- `docker-compose-distributed-final.yml` - Docker Swarm
- `verify_distributed_setup.py` - Verificador

### 🎯 CUMPLE REQUISITOS

✅ Despliegue distribuido en al menos 2 hosts remotos  
✅ Soporte para gran cantidad de agentes  
✅ Uso de programación restrictiva (OR-Tools)  
✅ Sistema multi-agente (SPADE)  
✅ Comunicación distribuida (OpenFire/XMPP)

### 📝 NOTAS ADICIONALES

- Modificar IPs en archivos `config/*.env` según tu red
- Asegurar conectividad entre hosts
- Verificar puertos abiertos: 9090, 5222, 7777
- El sistema puede escalar a más hosts agregando configuraciones
