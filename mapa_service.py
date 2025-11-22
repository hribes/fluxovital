import requests
import folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# --- OSRM (Visual) ---
def rota_real_osrm(lista_coordenadas):
    if not lista_coordenadas or len(lista_coordenadas) < 2: return [], 0
    pontos_str = ";".join([f"{lon},{lat}" for lat, lon in lista_coordenadas])
    url = f"https://router.project-osrm.org/route/v1/driving/{pontos_str}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data["routes"][0]["geometry"]["coordinates"], data["routes"][0]["duration"]
    except: pass
    return [], 0

# --- LÓGICA DO SOLVER (Adaptada para Dicionário) ---
def resolver_vrp(dados_db):
    matriz_tempo = dados_db.get('matriz_tempo')
    if not matriz_tempo: return {}, None

    manager = pywrapcp.RoutingIndexManager(len(matriz_tempo), dados_db['num_veiculos'], dados_db['deposito'])
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        return matriz_tempo[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)
    
    # Dimensão de Tempo (Limite 12h)
    routing.AddDimension(transit_idx, 3000, 43200, True, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")

    # Dimensão de Capacidade
    def demand_callback(from_index):
        return dados_db['demanda_assentos'][manager.IndexToNode(from_index)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, dados_db['capacidade_veiculos'], True, "Capacity")

    for p, d in dados_db['coletas_entregas']:
        p_idx, d_idx = manager.NodeToIndex(p), manager.NodeToIndex(d)
        routing.AddPickupAndDelivery(p_idx, d_idx)
        routing.solver().Add(routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx))
        routing.solver().Add(time_dimension.CumulVar(p_idx) <= time_dimension.CumulVar(d_idx))

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_params)
    rotas = {}
    
    if solution:
        for v_id in range(dados_db['num_veiculos']):
            index = routing.Start(v_id)
            rota = []
            while not routing.IsEnd(index):
                rota.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))
            rota.append(manager.IndexToNode(index))
            if len(rota) > 2: rotas[v_id] = rota
            
    return rotas, matriz_tempo

# --- DESENHO DO MAPA ---
def desenhar_mapa_veiculo(rota_indices, dados_db, cor_veiculo, titulo):
    coords = dados_db['coordenadas']
    m = folium.Map(location=coords[0], zoom_start=13)
    
    # Desenha Linha
    geo_rota = [coords[i] for i in rota_indices]
    for i in range(len(geo_rota)-1):
        path, _ = rota_real_osrm([geo_rota[i], geo_rota[i+1]])
        if path: folium.PolyLine([(c[1], c[0]) for c in path], weight=5, color=cor_veiculo).add_to(m)
        else: folium.PolyLine([geo_rota[i], geo_rota[i+1]], weight=3, color=cor_veiculo, dash_array='5,5').add_to(m)

    # Marcadores
    for i, node in enumerate(rota_indices):
        demanda = dados_db['demanda_assentos'][node]
        if node == 0: cor, icone = "black", "home"
        elif demanda > 0: cor, icone = "green", "user" # Coleta
        elif demanda < 0: cor, icone = "red", "plus-square" # Entrega
        else: cor, icone = "gray", "info-sign"
        
        folium.Marker(coords[node], icon=folium.Icon(color=cor, icon=icone, prefix='fa'), tooltip=f"{i}. Ponto {node}").add_to(m)

    return m._repr_html_()

def get_mapa_vazio():
    return folium.Map(location=[-22.213200, -49.944700], zoom_start=13)._repr_html_()

# --- FUNÇÃO PRINCIPAL (MANTIDA PARA O FRONTEND) ---
def get_mapas_calculados(dados_reais=None):
    """
    Recebe os dados do banco, calcula a rota, IMPRIME O RELATÓRIO 
    (igual ao original) e gera os mapas.
    """
    if not dados_reais:
        print("Nenhum dado recebido do banco.")
        return None

    # 1. Executa o Solver
    rotas, matriz_tempo = resolver_vrp(dados_reais)
    
    if not rotas:
        print("Solver retornou vazio (nenhuma solução viável encontrada).")
        return None

    # --- REINSERINDO OS PRINTS (RELATÓRIO) ADAPTADOS PARA O BANCO ---
    print("\n" + "="*70)
    print(f"ROTAS OTIMIZADAS (DADOS DO BANCO) - Priorizando Custo/Eficiência")
    print("="*70)

    # Recupera dados para o relatório
    capacidades = dados_reais['capacidade_veiculos']
    demandas = dados_reais['demanda_assentos']
    num_veiculos = dados_reais['num_veiculos']

    # Itera sobre TODOS os veículos possíveis (não só os usados)
    for v_id in range(num_veiculos):
        cap_max = capacidades[v_id]
        nodes = rotas.get(v_id, []) # Pega a rota se existir, senão lista vazia
        
        nomes_passos = []
        pass_dia = 0    
        ocupacao_atual = 0 
        max_ocupacao = 0
        
        # Cálculo de tempo
        tempo_rota_segundos = 0
        if matriz_tempo and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                origem = nodes[i]
                destino = nodes[i+1]
                tempo_rota_segundos += matriz_tempo[origem][destino]
        
        tempo_rota_min = int(tempo_rota_segundos / 60)

        # Lógica de Strings (Adaptada para não usar nomes estáticos)
        for node in nodes:
            passo_str = ""
            demanda_node = demandas[node]

            if node == 0: # Depósito
                passo_str = "[BASE/UPA]"
            elif demanda_node > 0: # Coleta (Demanda Positiva)
                passo_str = f"(Pega P{node})" # P{node} é o ID do nó na matriz
                pass_dia += 1
                ocupacao_atual += 1 
            elif demanda_node < 0: # Entrega (Demanda Negativa)
                passo_str = f"[HOSPITAL/DESTINO]"
                ocupacao_atual -= 1 

            if ocupacao_atual > max_ocupacao:
                max_ocupacao = ocupacao_atual

            if passo_str:
                if "BASE" in passo_str: 
                    nomes_passos.append(passo_str)
                else: 
                    # Mostra a ocupação atual vs capacidade do veículo
                    nomes_passos.append(f"{passo_str} [{ocupacao_atual}/{cap_max}]")

        status = "(PARADO)" if len(nomes_passos) <= 1 else f"(EM ROTA - {tempo_rota_min} min)"
        cor_status = "🔴" if "PARADO" in status else "🟢"
        
        # Define tipo por capacidade (Lógica original mantida)
        tipo_veiculo = " ÔNIBUS" if cap_max >= 10 else "CARRO"
        
        print(f"{cor_status} VEÍCULO {v_id} {status} - {tipo_veiculo} (Assentos: {cap_max})")
        if len(nodes) > 1:
            print(f"   Passageiros Transportados: {pass_dia}")
            print(f"   Rota: {' -> '.join(nomes_passos)}")
        print("-" * 70)
    
    print("="*70 + "\n")

    # --- GERAÇÃO DOS MAPAS (LINK COM O FRONTEND) ---
    mapas = {}
    cores = ['blue', 'purple', 'orange', 'darkred', 'green']
    
    i = 1 
    for v_id, caminho in rotas.items():
        chave_frontend = f"rota{i}" 
        cor = cores[v_id % len(cores)]
        
        titulo = f"Rota Otimizada - Veículo ID {v_id} (Visualizando em {chave_frontend})"
        
        html_mapa = desenhar_mapa_veiculo(caminho, dados_reais, cor, titulo)
        mapas[chave_frontend] = html_mapa
        
        i += 1 

    return mapas