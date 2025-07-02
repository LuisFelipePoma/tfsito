#!/bin/bash
# Script de inicio para TFS ITO

echo "=== TFS ITO - Traffic Flow System ==="
echo "Iniciando sistema de control de tráfico aéreo..."

# Función para mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCIÓN]"
    echo "Opciones:"
    echo "  start       - Iniciar sistema completo"
    echo "  env         - Solo Environment Agent"
    echo "  towers      - Environment + Torres"
    echo "  stop        - Detener sistema"
    echo "  clean       - Limpiar contenedores y volúmenes"
    echo "  logs        - Mostrar logs"
    echo "  status      - Mostrar estado de contenedores"
    echo "  help        - Mostrar esta ayuda"
}

# Función para iniciar sistema completo
start_full() {
    echo "Iniciando sistema completo..."
    docker-compose up --build -d
    echo "Sistema iniciado. Interfaces disponibles:"
    echo "  - Interfaz web: http://localhost:8080"
    echo "  - Openfire admin: http://localhost:9090 (admin/admin)"
}

# Función para iniciar solo Environment Agent
start_env() {
    echo "Iniciando solo Environment Agent..."
    docker-compose up --build env_agent openfire -d
    echo "Environment Agent iniciado: http://localhost:8080"
}

# Función para iniciar Environment + Torres
start_towers() {
    echo "Iniciando Environment Agent y Torres..."
    docker-compose up --build env_agent openfire tower_agent_sabe tower_agent_saez -d
    echo "Environment y Torres iniciados: http://localhost:8080"
}

# Función para detener sistema
stop_system() {
    echo "Deteniendo sistema..."
    docker-compose down
    echo "Sistema detenido."
}

# Función para limpiar sistema
clean_system() {
    echo "Limpiando sistema..."
    docker-compose down -v --remove-orphans
    docker system prune -f
    echo "Sistema limpiado."
}

# Función para mostrar logs
show_logs() {
    echo "Mostrando logs del sistema..."
    docker-compose logs -f
}

# Función para mostrar estado
show_status() {
    echo "Estado de contenedores:"
    docker-compose ps
    echo ""
    echo "Uso de recursos:"
    docker stats --no-stream
}

# Procesar argumentos
case "$1" in
    start)
        start_full
        ;;
    env)
        start_env
        ;;
    towers)
        start_towers
        ;;
    stop)
        stop_system
        ;;
    clean)
        clean_system
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Opción no reconocida: $1"
        show_help
        exit 1
        ;;
esac
