from typing import Dict, List
from ortools.constraint_solver import pywrapcp
from src.agent.libs.environment import GridPosition, PassengerInfo, PassengerState, TaxiInfo, TaxiState
from src.config import config
from src.utils.logger import logger

class ConstraintSolver:
    """Solver de constraint programming para asignación óptima"""

    def __init__(self):
        self.max_pickup_distance = 15  # Distancia máxima para pickup
        self.wait_time_penalty = 2  # Penalización por tiempo de espera

    def solve_assignment(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """
        Resuelve el problema de asignación taxi-pasajero
        Retorna: {taxi_id: passenger_id}
        """
        
        logger.critical("Solving assignment with realistic constraints")
        logger.info(f"Available taxis: {len(taxis)}, Waiting passengers: {len(passengers)}")
        # print positions of taxis and passengers
        logger.info("Taxis positions: " + ", ".join([f"{t.taxi_id}: {t.position}" for t in taxis]))
        logger.info("Passengers positions: " + ", ".join([f"{p.passenger_id}: {p.pickup_position}" for p in passengers]))
        
        available_taxis = [t for t in taxis if t.state == TaxiState.IDLE]
        waiting_passengers = [
            p for p in passengers if p.state == PassengerState.WAITING
        ]
        if not available_taxis or not waiting_passengers:
            return {}
        logger.info(
            f"Solving assignment: {len(available_taxis)} taxis, {len(waiting_passengers)} passengers"
        )
        return self._greedy_fallback_realistic(
                available_taxis, waiting_passengers
            )
        
        #! SOVEROOO FIX THIS SHIT
        # try:
        #     return self._solve_with_ortools_realistic(
        #         available_taxis, waiting_passengers
        #     )
        # except Exception as e:
        #     logger.warning(f"OR-Tools failed, using fallback: {e}")
        #     return self._greedy_fallback_realistic(
        #         available_taxis, waiting_passengers
        #     )

    def _passenger_vulnerability(self, p: PassengerInfo) -> bool:
        return p.is_disabled or p.is_elderly or p.is_child or p.is_pregnant

    def _zone_demand_score(self, pos: GridPosition) -> int:
        # Ejemplo: zonas de alta demanda (puedes personalizar)
        # Aquí, las esquinas y el centro tienen más demanda
        center_x, center_y = config.grid_width // 2, config.grid_height // 2
        if abs(pos.x - center_x) <= 2 and abs(pos.y - center_y) <= 2:
            return 2  # Centro: alta demanda
        if (
            pos.x < 3
            or pos.x > config.grid_width - 4
            or pos.y < 3
            or pos.y > config.grid_height - 4
        ):
            return 1  # Esquinas: demanda media
        return 0  # Resto: baja demanda

    def _solve_with_ortools_realistic(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """
        Solver usando OR-Tools con restricciones realistas:
        - Prioridad absoluta a vulnerables
        - Maximizar ganancia por minuto/km
        - Prioridad a mayor tiempo de espera
        - Prioridad a zonas de alta demanda
        - Minimizar ETA
        """
        solver = pywrapcp.Solver("TaxiAssignmentRealistic")
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        assignment = {}
        for i in range(n_taxis):
            assignment[i] = {}
            for j in range(n_passengers):
                assignment[i][j] = solver.IntVar(0, 1, f"assign_{i}_{j}")
        # Restricción: cada taxi a máximo un pasajero
        for i in range(n_taxis):
            solver.Add(solver.Sum([assignment[i][j] for j in range(n_passengers)]) <= 1)
        # Restricción: cada pasajero a máximo un taxi
        for j in range(n_passengers):
            solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) <= 1)
        # Restricciones de capacidad y distancia
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    solver.Add(assignment[i][j] == 0)
        # Prioridad absoluta: vulnerables
        # for j in range(n_passengers):
        #     passenger = passengers[j]
        #     if self._passenger_vulnerability(passenger):
        #         solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) >= 1)
        # Función objetivo realista
        cost_terms = []
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                pickup_dist = taxi.position.manhattan_distance(
                    passenger.pickup_position
                )
                trip_dist = passenger.pickup_position.manhattan_distance(
                    passenger.dropoff_position
                )
                eta = pickup_dist / max(taxi.speed, 0.1)
                wait_penalty = -int(
                    passenger.wait_time
                )  # Más espera, menor penalización
                demand_score = self._zone_demand_score(passenger.dropoff_position)
                # Ganancia por km/min
                gain_per_km = passenger.price / max(trip_dist, 1)
                # Vulnerabilidad: gran prioridad negativa (OR-Tools minimiza)
                vulnerability = (
                    -10000 if self._passenger_vulnerability(passenger) else 0
                )
                # Costo total: combina criterios
                cost = (
                    pickup_dist * 5  # Minimizar ETA
                    - int(gain_per_km * 100)  # Maximizar ganancia/km
                    + eta * 2  # Minimizar ETA
                    - demand_score * 50  # Prioridad a zonas de demanda
                    + wait_penalty * 3  # Prioridad a más espera
                    + vulnerability  # Prioridad absoluta a vulnerables
                )
                cost_terms.append(assignment[i][j] * int(cost))
        objective = solver.Minimize(solver.Sum(cost_terms), 1)
        decision_builder = solver.Phase(
            [assignment[i][j] for i in range(n_taxis) for j in range(n_passengers)],
            solver.CHOOSE_FIRST_UNBOUND,
            solver.ASSIGN_MIN_VALUE,
        )
        solver.NewSearch(decision_builder, [objective])
        assignments = {}
        if solver.NextSolution():
            for i in range(n_taxis):
                for j in range(n_passengers):
                    if assignment[i][j].Value() == 1:
                        assignments[taxis[i].taxi_id] = passengers[j].passenger_id
                        logger.info(
                            f"OR-Tools assignment: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (dist: {taxis[i].position.manhattan_distance(passengers[j].pickup_position)}, price: {passengers[j].price}, vulnerable: {self._passenger_vulnerability(passengers[j])})"
                        )
        solver.EndSearch()
        return assignments

    def _greedy_fallback_realistic(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """
        Algoritmo greedy realista: vulnerables primero, luego ganancia/km, espera, demanda, ETA
        """
        assignments = {}
        assigned_passengers = set()

        def passenger_score(p, taxi):
            pickup_dist = taxi.position.manhattan_distance(p.pickup_position)
            trip_dist = p.pickup_position.manhattan_distance(p.dropoff_position)
            eta = pickup_dist / max(taxi.speed, 0.1)
            gain_per_km = p.price / max(trip_dist, 1)
            demand_score = self._zone_demand_score(p.dropoff_position)
            vulnerability = -10000 if self._passenger_vulnerability(p) else 0
            wait_penalty = -int(p.wait_time)
            # Menor score es mejor
            return (
                vulnerability,
                -gain_per_km,
                wait_penalty,
                -demand_score,
                eta,
                pickup_dist,
            )

        for taxi in taxis:
            best_p = None
            best_score = (float("inf"),) * 6
            for p in passengers:
                if p.state != PassengerState.WAITING:
                    continue
                if p.passenger_id in assigned_passengers:
                    continue
                if taxi.current_passengers >= taxi.capacity:
                    continue
                pickup_dist = taxi.position.manhattan_distance(p.pickup_position)
                if pickup_dist > self.max_pickup_distance:
                    continue
                score = passenger_score(p, taxi)
                if score < best_score:
                    best_score = score
                    best_p = p
            if best_p:
                assignments[taxi.taxi_id] = best_p.passenger_id
                assigned_passengers.add(best_p.passenger_id)
                logger.info(
                    f"Greedy assignment: {taxi.taxi_id} -> {best_p.passenger_id} (dist: {taxi.position.manhattan_distance(best_p.pickup_position)}, price: {best_p.price}, vulnerable: {self._passenger_vulnerability(best_p)})"
                )
        return assignments

    def _solve_with_ortools(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """Solver usando OR-Tools con prioridad a discapacitados y maximizar ganancia"""
        solver = pywrapcp.Solver("TaxiAssignment")
        n_taxis = len(taxis)
        n_passengers = len(passengers)
        assignment = {}
        for i in range(n_taxis):
            assignment[i] = {}
            for j in range(n_passengers):
                assignment[i][j] = solver.IntVar(0, 1, f"assign_{i}_{j}")
        # Restricción: cada taxi asignado a máximo un pasajero
        for i in range(n_taxis):
            solver.Add(solver.Sum([assignment[i][j] for j in range(n_passengers)]) <= 1)
        # Restricción: cada pasajero asignado a máximo un taxi
        for j in range(n_passengers):
            solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) <= 1)
        # Restricciones de capacidad y distancia
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                if taxi.current_passengers >= taxi.capacity:
                    solver.Add(assignment[i][j] == 0)
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    solver.Add(assignment[i][j] == 0)
        # Prioridad: discapacitados primero
        for j in range(n_passengers):
            passenger = passengers[j]
            if passenger.is_disabled:
                # Al menos un taxi debe intentar tomarlo si hay taxis libres
                solver.Add(solver.Sum([assignment[i][j] for i in range(n_taxis)]) >= 1)
        # Función objetivo: maximizar suma de precios (con gran peso a discapacitados), minimizar distancia
        cost_terms = []
        for i in range(n_taxis):
            for j in range(n_passengers):
                taxi = taxis[i]
                passenger = passengers[j]
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                # Penalización fuerte si no es discapacitado (para que discapacitados tengan prioridad)
                priority = 1000 if passenger.is_disabled else 0
                # Maximizar precio, pero prioridad a discapacitado
                # Como OR-Tools minimiza, restamos el precio (maximizar)
                cost = distance - int(passenger.price * 10) - priority
                cost_terms.append(assignment[i][j] * cost)
        objective = solver.Minimize(solver.Sum(cost_terms), 1)
        decision_builder = solver.Phase(
            [assignment[i][j] for i in range(n_taxis) for j in range(n_passengers)],
            solver.CHOOSE_FIRST_UNBOUND,
            solver.ASSIGN_MIN_VALUE,
        )
        solver.NewSearch(decision_builder, [objective])
        assignments = {}
        if solver.NextSolution():
            for i in range(n_taxis):
                for j in range(n_passengers):
                    if assignment[i][j].Value() == 1:
                        assignments[taxis[i].taxi_id] = passengers[j].passenger_id
                        logger.info(
                            f"OR-Tools assignment: {taxis[i].taxi_id} -> {passengers[j].passenger_id} (dist: {taxis[i].position.manhattan_distance(passengers[j].pickup_position)}, price: {passengers[j].price}, disabled: {passengers[j].is_disabled})"
                        )
        solver.EndSearch()
        return assignments

    def _greedy_fallback(
        self, taxis: List[TaxiInfo], passengers: List[PassengerInfo]
    ) -> Dict[str, str]:
        """Algoritmo greedy: prioridad discapacitado, luego precio, luego distancia"""
        assignments = {}
        assigned_taxis = set()

        # Ordenar pasajeros: discapacitados primero, luego mayor precio, luego menor distancia
        def passenger_priority(p, taxi):
            distance = taxi.position.manhattan_distance(p.pickup_position)
            return (-int(p.is_disabled), -p.price, distance)

        for taxi in taxis:
            best_passenger = None
            best_score = (1, 0, float("inf"))
            for passenger in passengers:
                if passenger.state != PassengerState.WAITING:
                    continue
                if passenger.passenger_id in assignments.values():
                    continue
                if taxi.current_passengers >= taxi.capacity:
                    continue
                distance = taxi.position.manhattan_distance(passenger.pickup_position)
                if distance > self.max_pickup_distance:
                    continue
                score = passenger_priority(passenger, taxi)
                if score < best_score:
                    best_score = score
                    best_passenger = passenger
            if best_passenger:
                assignments[taxi.taxi_id] = best_passenger.passenger_id
                logger.info(
                    f"Greedy assignment: {taxi.taxi_id} -> {best_passenger.passenger_id} (dist: {taxi.position.manhattan_distance(best_passenger.pickup_position)}, price: {best_passenger.price}, disabled: {best_passenger.is_disabled})"
                )
        return assignments
