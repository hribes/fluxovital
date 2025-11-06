from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def create_data_model():
    """Armazena os dados do problema."""
    data = {}
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

    """Nesse ponto, temos uma lista onde indicamos quantas unidades de carga o veiuclo precisa coletar (ou entregar)"""
    data["demands"] = [0, 1, 1, 2, 4, 2, 4, 8, 8, 1, 2, 1, 2, 4, 4, 8, 8]
    
    #Soma de Demanda não pode exceder a soma das capacidades por veiculo.
    #Capacidade do veiculo
    data["vehicle_capacities"] = [18, 21, 31]
    
    #Qnt de veiculos na frota
    data["num_vehicles"] = 3
    
    #Definição do ponto de origem em relação a matriz
    data["depot"] = 0
    return data


def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    print(f"Objective: {solution.ObjectiveValue()}")
    total_distance = 0
    total_load = 0
    
    for vehicle_id in range(data["num_vehicles"]):
        if not routing.IsVehicleUsed(solution, vehicle_id):
            continue
        index = routing.Start(vehicle_id)
        plan_output = f"Rota para Veiculo {vehicle_id}:\n"
        route_distance = 0
        route_load = 0
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data["demands"][node_index]
            plan_output += f" {node_index} Load({route_load}) -> "
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        plan_output += f" {manager.IndexToNode(index)} Carregar ({route_load})\n"
        plan_output += f"Distância do percurso: {route_distance}m\n"
        plan_output += f"Carga da rota: {route_load}\n"
        print(plan_output)
        total_distance += route_distance
        total_load += route_load
    print(f"Distância total de todas as rotas: {total_distance}m")
    print(f"Carga total de todas as rotas: {total_load}")


def main():
    """Solve the CVRP problem."""
    # Instantiate the data problem.
    data = create_data_model()

    # Create the routing index manager.
    
    #(nós, veiculos, origem)
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )

    # Create Routing Model.
    
    """
    RoutingModel define todas as restrições (como capacidade, janelas de tempo, distância máxima, etc)
    Ele encontra a melhor solução, as rotas mais baratas para todos os veiculos!
    """
    routing = pywrapcp.RoutingModel(manager)


    # Create and register a transit callback.
    """Callback - função de retorno, ou seja uma função que o solver vai chamar automaticamente toda vez que ele precisar de uma informação."""
    
    def distance_callback(from_index, to_index):
        """Retorna a distância entre dois nós"""
        #Converte a variavel de roteamento index para a matriz de distância NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Defina o custo de cada arco.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Adicione restrição de capacidade.
    def demand_callback(from_index):
        """Retorna a demanda do nó."""
        # Converter a variável de roteamento Index para NodeIndex da demanda.
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  
        data["vehicle_capacities"],  # capacidades máximas do veículo
        True,  # iniciar cumulativo para zero
        "Capacity",
    )

    # Definindo a primeira heurística de solução
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(30)

    # Resolva o problema.
    solution = routing.SolveWithParameters(search_parameters)

    # Imprimir solução no console.
    if solution:
        print_solution(data, manager, routing, solution)
        """
        Data - Matriz de distância
        Manager - Gerenciador de índices "mapa" que mostra onde estão os clientes e o deposito
        Routing - É o "planejador de rotas" que usa esse mapa para decidir qual caminho cada veiculo deve seguir
        Solution - Procura a melhor solução possivel para o VRP
        """


if __name__ == "__main__":
    main()
# [END program]