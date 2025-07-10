from typing import Dict, List

# Importación condicional de OR-Tools
try:
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("WARNING: OR-Tools not available. Install with: pip install ortools")

from src.agent.libs.environment import GridPosition, PassengerInfo, PassengerState, TaxiInfo, TaxiState
from src.config import config
from src.utils.logger import logger

class ConstraintSolver:
    """Solver de constraint programming para asignación óptima"""

    def __init__(self):
        self.max_pickup_distance = 25  # Distancia máxima inicial
        # Pesos para la función objetivo simplificados
        self.distance_weight = 100      # Peso para minimizar distancia
        self.disability_priority = 1000 # Peso muy alto para discapacitados
        
    def solve_assignment(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """
        Resuelve el problema de asignación taxi-pasajero usando SOLO OR-Tools
        
        LÓGICA:
        1. Prioridad MÁXIMA a pasajeros discapacitados
        2. Si no hay discapacitados, asignar por cercanía (distancia mínima)
        3. Si no encuentra solución, aumenta distancia progresivamente
        4. NO HAY FALLBACK - Solo OR-Tools
        
        Retorna: {taxi_id: passenger_id}
        """
        
        # Verificar que OR-Tools esté disponible
        if not ORTOOLS_AVAILABLE:
            logger.error("❌ OR-Tools not available! Install with: pip install ortools")
            return {}
        
        logger.info(f"=== CONSTRAINT SOLVER START (OR-Tools Only) ===")
        logger.info(f"Available taxis: {len(taxis)}, Waiting passengers: {len(passengers)}")
        
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [p for p in passengers if p.state == PassengerState.WAITING]
        
        if not available_taxis or not waiting_passengers:
            logger.info("No available taxis or passengers")
            return {}
            
        logger.info(f"Solving assignment: {len(available_taxis)} taxis, {len(waiting_passengers)} passengers")
        
        # Intentar con distancia progresiva
        assignments = self._solve_with_progressive_distance(available_taxis, waiting_passengers)

        logger.info(f"Final assignments: {assignments}")
        return assignments

    def _passenger_is_disabled(self, p: PassengerInfo) -> bool:
        """Verifica si un pasajero es discapacitado"""
        return p.is_disabled

    def _solve_with_progressive_distance(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """
        Solver con distancia progresiva hasta encontrar solución
        """
        
        # Distancias a probar progresivamente
        distances_to_try = [25, 35, 50, 75, 100, 150, 999]
        
        for attempt, max_distance in enumerate(distances_to_try, 1):
            logger.info(f"🔍 Attempt {attempt}/{len(distances_to_try)}: max_distance = {max_distance}")
            
            assignments = self._solve_with_ortools(taxis, passengers, max_distance)
            
            if assignments:
                logger.info(f"✅ SUCCESS with distance {max_distance}: {len(assignments)} assignments")
                return assignments
            else:
                logger.warning(f"❌ No solution with distance {max_distance}")
        
        # Si llegamos aquí, OR-Tools no pudo encontrar solución
        logger.error("🚨 OR-Tools failed to find any solution - no assignments possible")
        return {}

    def _solve_with_ortools(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo], max_distance: int
    ) -> Dict[str, str]:
        """
        Solver principal usando OR-Tools con función objetivo simplificada
        """
            
        try:
            solver = pywrapcp.Solver("TaxiAssignment")
            n_taxis = len(taxis)
            n_passengers = len(passengers)
            
            if n_taxis == 0 or n_passengers == 0:
                return {}
            
            # Variables de decisión: assignment[i][j] = 1 si taxi i asignado a pasajero j
            assignment = {}
            all_vars = []
            
            for i in range(n_taxis):
                assignment[i] = {}
                for j in range(n_passengers):
                    var = solver.IntVar(0, 1, f"assign_{i}_{j}")
                    assignment[i][j] = var
                    all_vars.append(var)
            
            # RESTRICCIONES DE EXCLUSIVIDAD ESTRICTA
            
            # Restricción 1: cada taxi a EXACTAMENTE un pasajero o ninguno (máximo 1)
            for i in range(n_taxis):
                taxi_sum = solver.Sum([assignment[i][j] for j in range(n_passengers)])
                solver.Add(taxi_sum <= 1)
                logger.debug(f"Constraint: Taxi {i} can be assigned to at most 1 passenger")
            
            # Restricción 2: cada pasajero a EXACTAMENTE un taxi o ninguno (máximo 1)
            for j in range(n_passengers):
                passenger_sum = solver.Sum([assignment[i][j] for i in range(n_taxis)])
                solver.Add(passenger_sum <= 1)
                logger.debug(f"Constraint: Passenger {j} can be assigned to at most 1 taxi")
            
            # Restricción 3: no asignar pasajeros ya asignados a otros taxis
            for j, passenger in enumerate(passengers):
                if passenger.assigned_taxi_id:
                    # Si el pasajero ya tiene un taxi asignado, no permitir nuevas asignaciones
                    for i in range(n_taxis):
                        taxi = taxis[i]
                        if taxi.taxi_id != passenger.assigned_taxi_id:
                            solver.Add(assignment[i][j] == 0)
                            logger.debug(f"Blocking assignment: Passenger {passenger.passenger_id} already assigned to {passenger.assigned_taxi_id}")
            
            # Restricción 4: distancia y capacidad
            feasible_count = 0
            for i in range(n_taxis):
                for j in range(n_passengers):
                    taxi = taxis[i]
                    passenger = passengers[j]
                    
                    distance = taxi.position.manhattan_distance(passenger.pickup_position)
                    
                    # Si está muy lejos, taxi lleno, o pasajero ya asignado, no permitir asignación
                    if (distance > max_distance or 
                        taxi.current_passengers >= taxi.capacity or
                        passenger.assigned_taxi_id is not None):
                        solver.Add(assignment[i][j] == 0)
                    else:
                        feasible_count += 1
            
            if feasible_count == 0:
                logger.warning(f"No feasible assignments with distance {max_distance}")
                return {}
            
            logger.info(f"Feasible assignments: {feasible_count}")
            
            # FUNCIÓN OBJETIVO: Minimizar costo total (solo si tenemos asignaciones factibles)
            cost_terms = []
            
            for i in range(n_taxis):
                for j in range(n_passengers):
                    taxi = taxis[i]
                    passenger = passengers[j]
                    distance = taxi.position.manhattan_distance(passenger.pickup_position)
                    
                    # Solo agregar costo si la asignación es factible
                    if distance <= max_distance and taxi.current_passengers < taxi.capacity:
                        # Costo base por distancia
                        distance_cost = distance * self.distance_weight
                        
                        # Gran descuento para pasajeros discapacitados (prioridad máxima)
                        disability_bonus = 0
                        if self._passenger_is_disabled(passenger):
                            disability_bonus = -self.disability_priority  # Descuento enorme
                            logger.debug(f"Disabled passenger {passenger.passenger_id}: applying priority bonus")
                        
                        total_cost = distance_cost + disability_bonus
                        cost_terms.append(assignment[i][j] * total_cost)
            
            # Configurar búsqueda con estrategia más simple
            if cost_terms:
                objective = solver.Minimize(solver.Sum(cost_terms), 1)
                # Usar estrategia de búsqueda más determinística
                db = solver.Phase(
                    all_vars,
                    solver.CHOOSE_MIN_SIZE_LOWEST_MIN,  # Estrategia más determinística
                    solver.ASSIGN_MIN_VALUE,
                )
                solver.NewSearch(db, [objective])
            else:
                logger.warning("No cost terms, using basic search")
                # Búsqueda básica sin objetivo
                db = solver.Phase(
                    all_vars,
                    solver.CHOOSE_MIN_SIZE_LOWEST_MIN,
                    solver.ASSIGN_MIN_VALUE,
                )
                solver.NewSearch(db)
            
            # Extraer solución
            assignments = {}
            
            # Intentar obtener múltiples soluciones si la primera falla
            solutions_found = 0
            max_solutions = 3
            
            while solver.NextSolution() and solutions_found < max_solutions:
                solutions_found += 1
                logger.info(f"✅ OR-Tools solution #{solutions_found} found:")
                
                # Extraer asignaciones
                extracted_count = 0
                temp_assignments = {}
                assigned_passengers = set()  # Para verificar exclusividad
                assigned_taxis = set()  # Para verificar exclusividad
                
                for i in range(n_taxis):
                    for j in range(n_passengers):
                        try:
                            var_value = assignment[i][j].Value()
                            
                            if var_value == 1:
                                taxi = taxis[i]
                                passenger = passengers[j]
                                
                                # Verificar exclusividad ESTRICTA
                                if passenger.passenger_id in assigned_passengers:
                                    logger.error(f"❌ CRITICAL ERROR: DUPLICATE PASSENGER ASSIGNMENT: {passenger.passenger_id}")
                                    logger.error(f"   This violates the exclusivity constraint!")
                                    continue
                                if taxi.taxi_id in assigned_taxis:
                                    logger.error(f"❌ CRITICAL ERROR: DUPLICATE TAXI ASSIGNMENT: {taxi.taxi_id}")
                                    logger.error(f"   This violates the exclusivity constraint!")
                                    continue
                                
                                # Verificar que el pasajero no esté ya asignado a otro taxi
                                if passenger.assigned_taxi_id and passenger.assigned_taxi_id != taxi.taxi_id:
                                    logger.error(f"❌ ASSIGNMENT CONFLICT: Passenger {passenger.passenger_id} already assigned to {passenger.assigned_taxi_id}, trying to assign to {taxi.taxi_id}")
                                    continue
                                
                                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                                
                                # ✅ ASIGNACIÓN VÁLIDA Y EXCLUSIVA
                                temp_assignments[taxi.taxi_id] = passenger.passenger_id
                                assigned_passengers.add(passenger.passenger_id)
                                assigned_taxis.add(taxi.taxi_id)
                                extracted_count += 1
                                
                                passenger_type = "DISABLED" if self._passenger_is_disabled(passenger) else "NORMAL"
                                priority_flag = "🔥 PRIORITY" if self._passenger_is_disabled(passenger) else ""
                                
                                logger.info(
                                    f"  ✅ EXCLUSIVE ASSIGNMENT: Taxi {taxi.taxi_id} -> Passenger {passenger.passenger_id} [{passenger_type}] "
                                    f"distance={distance} {priority_flag}"
                                )
                        except Exception as e:
                            logger.error(f"Error extracting variable assign_{i}_{j}: {e}")
                
                logger.info(f"Extracted {extracted_count} assignments from solution #{solutions_found}")
                
                # Si encontramos asignaciones válidas, validar exclusividad final
                if extracted_count > 0:
                    # Validación final de exclusividad
                    taxis_in_assignments = list(temp_assignments.keys())
                    passengers_in_assignments = list(temp_assignments.values())
                    
                    if len(taxis_in_assignments) != len(set(taxis_in_assignments)):
                        logger.error("❌ FINAL VALIDATION FAILED: Duplicate taxis in assignments!")
                        continue
                        
                    if len(passengers_in_assignments) != len(set(passengers_in_assignments)):
                        logger.error("❌ FINAL VALIDATION FAILED: Duplicate passengers in assignments!")
                        continue
                    
                    logger.info(f"✅ FINAL VALIDATION PASSED: {extracted_count} exclusive assignments confirmed")
                    assignments = temp_assignments
                    break
                else:
                    logger.warning(f"Solution #{solutions_found} extracted 0 assignments, trying next...")
            
            if solutions_found == 0:
                logger.warning("❌ No OR-Tools solution found")
            elif len(assignments) == 0:
                logger.warning(f"❌ OR-Tools found {solutions_found} solutions but extracted 0 assignments!")
            
            solver.EndSearch()
            return assignments
            
        except Exception as e:
            logger.error(f"OR-Tools solver error: {e}")
            return {}


