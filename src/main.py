
# main.py — Sistema de Taxis Inteligente
# Este archivo es el punto de entrada del sistema de taxis.
# Aquí debe implementarse la lógica para lanzar la GUI y permitir elegir entre modo Local o Red.

import sys
from taxi_dispatch_gui import launch_taxi_gui

if __name__ == "__main__":
    # Lanza la GUI central, la cual debe permitir elegir el modo de operación (local/red)
    launch_taxi_gui()
