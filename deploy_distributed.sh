#!/bin/bash
# Script para despliegue distribuido en múltiples hosts
# deploy_distributed.sh

set -e

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="taxi-dispatch"
DOCKER_IMAGE="taxi-dispatch:latest"
OPENFIRE_HOST="localhost"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --hosts HOST1,HOST2,HOST3    Comma-separated list of host IPs/names"
    echo "  -a, --agents TOTAL              Total number of agents to deploy"
    echo "  -u, --user USERNAME             SSH username (default: current user)"
    echo "  -k, --key PATH                  SSH private key path"
    echo "  -p, --port PORT                 SSH port (default: 22)"
    echo "  --openfire-host HOST            Openfire server host (default: localhost)"
    echo "  --skip-build                    Skip Docker image build"
    echo "  --dry-run                       Show what would be done without executing"
    echo "  --help                          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -h 192.168.1.10,192.168.1.11 -a 100"
    echo "  $0 -h host1,host2,host3 -a 200 -u deploy --openfire-host 192.168.1.5"
}

# Valores por defecto
HOSTS=""
TOTAL_AGENTS=""
SSH_USER="$(whoami)"
SSH_KEY="$HOME/.ssh/id_rsa"
SSH_PORT="22"
SKIP_BUILD=false
DRY_RUN=false

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--hosts)
            HOSTS="$2"
            shift 2
            ;;
        -a|--agents)
            TOTAL_AGENTS="$2"
            shift 2
            ;;
        -u|--user)
            SSH_USER="$2"
            shift 2
            ;;
        -k|--key)
            SSH_KEY="$2"
            shift 2
            ;;
        -p|--port)
            SSH_PORT="$2"
            shift 2
            ;;
        --openfire-host)
            OPENFIRE_HOST="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validar argumentos requeridos
if [[ -z "$HOSTS" ]]; then
    error "Hosts list is required (-h|--hosts)"
    usage
    exit 1
fi

if [[ -z "$TOTAL_AGENTS" ]]; then
    error "Total agents is required (-a|--agents)"
    usage
    exit 1
fi

# Convertir lista de hosts en array
IFS=',' read -ra HOST_ARRAY <<< "$HOSTS"

log "Starting distributed deployment"
log "Hosts: ${HOST_ARRAY[*]}"
log "Total agents: $TOTAL_AGENTS"
log "SSH User: $SSH_USER"
log "Openfire Host: $OPENFIRE_HOST"

if [[ "$DRY_RUN" == "true" ]]; then
    warn "DRY RUN MODE - No changes will be made"
fi

# Función para ejecutar comando SSH
ssh_exec() {
    local host=$1
    local command=$2
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "Would execute on $host: $command"
        return 0
    fi
    
    ssh -i "$SSH_KEY" -p "$SSH_PORT" -o StrictHostKeyChecking=no "$SSH_USER@$host" "$command"
}

# Función para copiar archivos via SCP
scp_copy() {
    local src=$1
    local host=$2
    local dest=$3
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "Would copy $src to $host:$dest"
        return 0
    fi
    
    scp -i "$SSH_KEY" -P "$SSH_PORT" -o StrictHostKeyChecking=no "$src" "$SSH_USER@$host:$dest"
}

# Función para verificar conectividad
check_connectivity() {
    local host=$1
    
    log "Checking connectivity to $host..."
    
    if ping -c 1 -W 3 "$host" > /dev/null 2>&1; then
        log "Ping to $host successful"
    else
        error "Cannot ping $host"
        return 1
    fi
    
    if ssh_exec "$host" "echo 'SSH connection test'" > /dev/null 2>&1; then
        log "SSH connection to $host successful"
    else
        error "Cannot establish SSH connection to $host"
        return 1
    fi
    
    return 0
}

# Función para preparar host remoto
prepare_host() {
    local host=$1
    
    log "Preparing host $host..."
    
    # Crear directorio del proyecto
    ssh_exec "$host" "mkdir -p ~/taxi-dispatch"
    
    # Instalar Docker si no está presente
    ssh_exec "$host" "which docker || (curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh)"
    
    # Instalar docker-compose si no está presente
    ssh_exec "$host" "which docker-compose || pip3 install docker-compose"
    
    # Verificar que Docker esté corriendo
    ssh_exec "$host" "sudo systemctl start docker && sudo systemctl enable docker"
    
    log "Host $host prepared successfully"
}

# Función para desplegar en un host
deploy_to_host() {
    local host=$1
    local agent_count=$2
    
    log "Deploying $agent_count agents to $host..."
    
    # Copiar archivos del proyecto
    log "Copying project files to $host..."
    scp_copy "$SCRIPT_DIR/src" "$host" "~/taxi-dispatch/"
    scp_copy "$SCRIPT_DIR/requirements.txt" "$host" "~/taxi-dispatch/"
    scp_copy "$SCRIPT_DIR/Dockerfile.agent" "$host" "~/taxi-dispatch/" 2>/dev/null || true
    
    # Crear archivo de configuración específico del host
    cat > "/tmp/host_config_$host.env" << EOF
OPENFIRE_HOST=$OPENFIRE_HOST
OPENFIRE_PORT=5222
HOST_ID=$host
AGENT_COUNT=$agent_count
EOF
    
    scp_copy "/tmp/host_config_$host.env" "$host" "~/taxi-dispatch/.env"
    rm "/tmp/host_config_$host.env"
    
    # Ejecutar despliegue en el host
    ssh_exec "$host" "cd ~/taxi-dispatch && python3 -m pip install -r requirements.txt"
    
    # Crear script de inicio para el host
    cat > "/tmp/start_agents_$host.sh" << 'EOF'
#!/bin/bash
cd ~/taxi-dispatch
export $(cat .env | xargs)
python3 src/main.py --host "$HOST_ID" --agent-count "$AGENT_COUNT" --openfire-host "$OPENFIRE_HOST" > agent_output.log 2>&1 &
echo $! > agent_process.pid
echo "Agents started with PID $(cat agent_process.pid)"
EOF
    
    scp_copy "/tmp/start_agents_$host.sh" "$host" "~/taxi-dispatch/start_agents.sh"
    rm "/tmp/start_agents_$host.sh"
    
    ssh_exec "$host" "chmod +x ~/taxi-dispatch/start_agents.sh"
    
    # Iniciar agentes
    ssh_exec "$host" "~/taxi-dispatch/start_agents.sh"
    
    log "Deployment to $host completed"
}

# Función para verificar despliegue
verify_deployment() {
    local host=$1
    
    log "Verifying deployment on $host..."
    
    # Verificar que el proceso esté corriendo
    if ssh_exec "$host" "test -f ~/taxi-dispatch/agent_process.pid && kill -0 \$(cat ~/taxi-dispatch/agent_process.pid) 2>/dev/null"; then
        log "Agents are running on $host"
        return 0
    else
        error "Agents are not running on $host"
        return 1
    fi
}

# Función principal de despliegue
main() {
    log "=== DISTRIBUTED DEPLOYMENT STARTED ==="
    
    # 1. Verificar conectividad a todos los hosts
    log "Step 1: Checking connectivity to all hosts..."
    for host in "${HOST_ARRAY[@]}"; do
        if ! check_connectivity "$host"; then
            error "Connectivity check failed for $host"
            exit 1
        fi
    done
    
    # 2. Calcular distribución de agentes
    log "Step 2: Calculating agent distribution..."
    host_count=${#HOST_ARRAY[@]}
    agents_per_host=$((TOTAL_AGENTS / host_count))
    remaining_agents=$((TOTAL_AGENTS % host_count))
    
    declare -A agent_distribution
    for i in "${!HOST_ARRAY[@]}"; do
        host="${HOST_ARRAY[$i]}"
        agents=$agents_per_host
        if [[ $i -lt $remaining_agents ]]; then
            agents=$((agents + 1))
        fi
        agent_distribution["$host"]=$agents
        log "Host $host will get $agents agents"
    done
    
    # 3. Preparar hosts
    log "Step 3: Preparing hosts..."
    for host in "${HOST_ARRAY[@]}"; do
        prepare_host "$host" &
    done
    wait  # Esperar que todas las preparaciones terminen
    
    # 4. Desplegar en cada host
    log "Step 4: Deploying agents to hosts..."
    for host in "${HOST_ARRAY[@]}"; do
        deploy_to_host "$host" "${agent_distribution[$host]}" &
    done
    wait  # Esperar que todos los despliegues terminen
    
    # 5. Verificar despliegues
    log "Step 5: Verifying deployments..."
    sleep 10  # Dar tiempo para que los agentes se inicialicen
    
    success_count=0
    for host in "${HOST_ARRAY[@]}"; do
        if verify_deployment "$host"; then
            success_count=$((success_count + 1))
        fi
    done
    
    # 6. Resumen
    log "=== DEPLOYMENT SUMMARY ==="
    log "Total hosts: ${#HOST_ARRAY[@]}"
    log "Successful deployments: $success_count"
    log "Total agents requested: $TOTAL_AGENTS"
    log "Agents distributed: $(IFS=+; echo "$((${agent_distribution[*]}))")"
    
    if [[ $success_count -eq ${#HOST_ARRAY[@]} ]]; then
        log "🎉 All deployments successful!"
        return 0
    else
        error "Some deployments failed!"
        return 1
    fi
}

# Función para mostrar logs de un host
show_logs() {
    local host=$1
    echo "=== Logs from $host ==="
    ssh_exec "$host" "tail -n 20 ~/taxi-dispatch/agent_output.log 2>/dev/null || echo 'No logs available'"
    echo ""
}

# Función de cleanup
cleanup_deployment() {
    log "Cleaning up deployments..."
    for host in "${HOST_ARRAY[@]}"; do
        log "Stopping agents on $host..."
        ssh_exec "$host" "test -f ~/taxi-dispatch/agent_process.pid && kill \$(cat ~/taxi-dispatch/agent_process.pid) 2>/dev/null || true"
        ssh_exec "$host" "rm -f ~/taxi-dispatch/agent_process.pid"
    done
    log "Cleanup completed"
}

# Manejar señales para cleanup
trap cleanup_deployment EXIT INT TERM

# Ejecutar función principal
if main; then
    log "=== DEPLOYMENT COMPLETED SUCCESSFULLY ==="
    
    # Mostrar logs de cada host
    log "Recent logs from each host:"
    for host in "${HOST_ARRAY[@]}"; do
        show_logs "$host"
    done
    
    log "To monitor deployments, run: python3 distribution_manager.py --hosts $HOSTS --total-agents $TOTAL_AGENTS --monitor-duration 30"
    
else
    error "=== DEPLOYMENT FAILED ==="
    exit 1
fi
