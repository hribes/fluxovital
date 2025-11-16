from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List, Dict, Tuple, Any

# =======================================================================
# DADOS GEOGRÁFICOS (Simulação para Folium)
# PONTOS: 17 coordenadas para os 17 nós da matriz. (Lat, Lon)
# =======================================================================
PONTOS: List[Tuple[float, float]] = [
    (-22.2177, -49.9450),  # 0: Depot/Base
    (-22.2200, -49.9500),  # 1
    (-22.2150, -49.9400),  # 2
    (-22.2250, -49.9480),  # 3
    (-22.2220, -49.9420),  # 4
    (-22.2100, -49.9520),  # 5
    (-22.2120, -49.9380),  # 6
    (-22.2050, -49.9450),  # 7
    (-22.2300, -49.9550),  # 8
    (-22.2080, -49.9480),  # 9
    (-22.2280, -49.9430),  # 10
    (-22.2180, -49.9350),  # 11
    (-22.2160, -49.9320),  # 12
    (-22.2230, -49.9370),  # 13
    (-22.2000, -49.9400),  # 14
    (-22.2350, -49.9500),  # 15
    (-22.2210, -49.9550),  # 16
]

# PACIENTES (Para marcadores de cores, assumindo que todos os nós exceto o 0 são clientes)
PACIENTES = PONTOS[1:] 

# =======================================================================
# FUNÇÃO DE DADOS (Seu modelo de dados)
# =======================================================================
def create_data_model():
    """Armazena os dados do problema de Roteamento."""
    data: Dict[str, Any] = {}
    data["distance_matrix"] = [
      [0, 548, 776, 696, 582, 274, 502, 194, 308, 194, 536, 502, 388, 354, 468, 776, 662],
      [548, 0, 684, 308, 194, 502, 730, 354, 696, 742, 1084, 594, 480, 674, 1016, 868, 1210],
      [776, 684, 0, 992, 878, 502, 274, 810, 468, 742, 400, 1278, 1164, 1130, 788, 1552, 754],
      [696, 308, 992, 0, 114, 650, 878, 502, 844, 890, 1232, 514, 628, 822, 1164, 560, 1358],
      [582, 194, 878, 114, 0, 536, 764, 388, 730, 776, 1118, 400, 514, 708, 1050, 674, 1244],
      [274, 502, 502, 650, 536, 0, 228, 308, 194, 240, 582, 776, 662, 628, 514, 1050, 708],
      [502, 730, 274, 878, 764, 228, 0, 536, 194, 468, 354, 1004, 890, 856, 514, 1278, 480],
      [194, 354, 810, 502, 388, 308, 536, 0, 342, 388, 730, 468, 354, 320, 662, 742, 856],
      [308, 696, 468, 844, 730, 194, 194, 342, 0, 274, 388, 810, 696, 662, 320, 1084, 514],
      [194, 742, 742, 890, 776, 240, 468, 388, 274, 0, 342, 536, 422, 388, 274, 810, 468],
      [536, 1084, 400, 1232, 1118, 582, 354, 730, 388, 342, 0, 878, 764, 730, 388, 1152, 354],
      [502, 594, 1278, 514, 400, 776, 1004, 468, 810, 536, 878, 0, 114, 308, 650, 274, 844],
      [388, 480, 1164, 628, 514, 662, 890, 354, 696, 422, 764, 114, 0, 194, 536, 388, 730],
      [354, 674, 1130, 822, 708, 628, 856, 320, 662, 388, 730, 308, 194, 0, 342, 422, 536],
      [468, 1016, 788, 1164, 1050, 514, 514, 662, 320, 274, 388, 650, 536, 342, 0, 764, 194],
      [776, 868, 1552, 560, 674, 1050, 1278, 742, 1084, 810, 1152, 274, 388, 422, 764, 0, 798],
      [662, 1210, 754, 1358, 1244, 708, 480, 856, 514, 468, 354, 844, 730, 536, 194, 798, 0],
    ]
    # Tempo em minutos
    data["time_matrix"] = [
        [0, 21, 29, 26, 22, 10, 19, 7, 12, 7, 20, 19, 15, 13, 17, 29, 25],
        [21, 0, 26, 12, 7, 19, 27, 13, 26, 28, 41, 22, 18, 25, 38, 33, 45],
        [29, 26, 0, 37, 33, 19, 10, 31, 17, 28, 15, 48, 44, 42, 30, 58, 28],
        [26, 12, 37, 0, 4, 24, 33, 19, 32, 33, 46, 19, 24, 31, 44, 21, 51],
        [22, 7, 33, 4, 0, 20, 29, 15, 27, 29, 42, 15, 19, 27, 40, 25, 47],
        [10, 19, 19, 24, 20, 0, 9, 12, 7, 9, 22, 29, 25, 24, 19, 39, 27],
        [19, 27, 10, 33, 29, 9, 0, 20, 7, 17, 13, 38, 34, 32, 19, 48, 18],
        [7, 13, 31, 19, 15, 12, 20, 0, 13, 15, 27, 17, 13, 12, 25, 28, 32],
        [12, 26, 17, 32, 27, 7, 7, 13, 0, 10, 15, 31, 26, 25, 12, 41, 19],
        [7, 28, 28, 33, 29, 9, 17, 15, 10, 0, 13, 20, 16, 15, 10, 31, 17],
        [20, 41, 15, 46, 42, 22, 13, 27, 15, 13, 0, 33, 29, 27, 15, 43, 13],
        [19, 22, 48, 19, 15, 29, 38, 17, 31, 20, 33, 0, 4, 12, 24, 10, 32],
        [15, 18, 44, 24, 19, 25, 34, 13, 26, 16, 29, 4, 0, 7, 19, 15, 27],
        [13, 25, 42, 31, 27, 24, 32, 12, 25, 15, 27, 12, 7, 0, 12, 16, 20],
        [17, 38, 30, 44, 40, 19, 19, 25, 12, 10, 15, 24, 19, 12, 0, 29, 7],
        [29, 33, 58, 21, 25, 39, 48, 28, 41, 31, 43, 10, 15, 16, 29, 0, 30],
        [25, 45, 28, 51, 47, 27, 18, 32, 19, 17, 13, 32, 27, 20, 7, 30, 0],
    ] 
    data["demands"] = [0, 1, 1, 2, 4, 2, 4, 8, 8, 1, 2, 1, 2, 4, 4, 8, 8]
    data["vehicle_capacities"] = [18, 21, 31]
    data["num_vehicles"] = 3
    data["depot"] = 0
    return data

def get_routes(data, manager, routing, solution) -> List[List[int]]:
    """Extrai todas as rotas da solução e retorna como uma lista de listas de índices de nó."""
    all_routes = []
    for vehicle_id in range(data["num_vehicles"]):
        if not routing.IsVehicleUsed(solution, vehicle_id):
            continue
            
        route = []
        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))  # Adiciona o depósito final
        all_routes.append(route)
    return all_routes


def resolver_rota() -> Tuple[List[List[int]], List[List[int]], List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Resolve o problema CVRP usando OR-Tools e extrai as rotas, 
    o tempo de viagem e os dados geográficos.
    """
    data = create_data_model()

    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )

    routing = pywrapcp.RoutingModel(manager)

    # ------------------
    # CALLBACKS
    # ------------------
    def distance_callback(from_index, to_index):
        """Retorna a distância entre dois nós."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Restrição de Capacidade
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0, 
        data["vehicle_capacities"],
        True, 
        "Capacity",
    )
    
    # Restrição de Tempo
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["time_matrix"][from_node][to_node]
    
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # Adicionamos o tempo como restrição, mas NÃO como custo de otimização principal
    # Se quisermos minimizar o tempo, usaríamos time_callback_index em SetArcCostEvaluatorOfAllVehicles
    routing.AddDimension(
        time_callback_index,
        10, # Tempo de espera máximo (minutos)
        3000, # Max tempo de rota (ajustado de 180 para um valor mais realista em um problema grande)
        False,
        "Time"
    )

    # ------------------
    # BUSCA DA SOLUÇÃO
    # ------------------
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(3) # Tempo limite reduzido para 3s para desempenho

    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        # Retorna: (Lista de Rotas, Matriz de Tempo, Coordenadas, Clientes)
        return get_routes(data, manager, routing, solution), data["time_matrix"], PONTOS, PACIENTES
    else:
        print("Aviso: Nenhuma solução encontrada pelo OR-Tools.")
        return None
        
# Opcionalmente, se você quiser a função de impressão para debug:
def print_solution(data, manager, routing, solution):
    """Prints solution on console - útil para debug."""
    print(f"Objective: {solution.ObjectiveValue()}")
    total_distance = 0
    total_load = 0
    
    for vehicle_id in range(data["num_vehicles"]):
        if not routing.IsVehicleUsed(solution, vehicle_id):
            continue
        index = routing.Start(vehicle_id)
        plan_output = f"Rota para Veiculo {vehicle_id} (Capacidade: {data['vehicle_capacities'][vehicle_id]}):\n"
        route_distance = 0
        route_load = 0
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data["demands"][node_index]
            plan_output += f" {node_index} (Demanda: {data['demands'][node_index]}) -> "
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        plan_output += f" {manager.IndexToNode(index)} (Depósito)\n"
        plan_output += f"Distância do percurso: {route_distance}m\n"
        print(plan_output)
        total_distance += route_distance
        total_load += route_load
    print(f"\nDistância total de todas as rotas: {total_distance}m")
    
# Não precisamos do __main__ aqui, pois ele será importado pelo FastAPI