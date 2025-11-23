import requests
import folium
from datetime import datetime, timedelta
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



def get_mapas_calculados(dados_reais=None):
    """
    Retorna um Dicionário de Listas estruturadas para salvar no Banco de Dados.
    Formato: {'rota1': [{'id_veiculo': 1, 'tipo': 'COLETA'...}, ...]}
    """
    if not dados_reais:
        print("Nenhum dado recebido do banco.")
        return None

    # 1. Executa o Solver
    rotas, matriz_tempo = resolver_vrp(dados_reais)
    
    if not rotas:
        print("Solver retornou vazio (nenhuma solução viável encontrada).")
        return None

    # --- PRINTS (RELATÓRIO VISUAL NO TERMINAL) ---
    print("\n" + "="*70)
    print(f"ROTAS OTIMIZADAS (DADOS DO BANCO) - Priorizando Custo/Eficiência")
    print("="*70)

    # Dados auxiliares
    capacidades = dados_reais['capacidade_veiculos']
    demandas = dados_reais['demanda_assentos']
    num_veiculos = dados_reais['num_veiculos']
    
    # IMPORTANTE: Lista com dicionários contendo os IDs reais (ID_SOLICITACAO, ID_ENDERECO, ID_PACIENTE)
    # Se sua função de busca não tem isso, precisamos adicionar.
    info_nos = dados_reais.get('info_nos', []) 
    ids_veiculos_reais = dados_reais.get('ids_veiculos_reais', []) # Lista de IDs dos carros [1, 2, 3...]

    # Estrutura final para retornar ao controller
    dados_para_salvar = {}

    rota_counter = 1

    for v_id in range(num_veiculos):
        cap_max = capacidades[v_id]
        nodes = rotas.get(v_id, [])
        
        # Se não tem IDs reais de veículos, inventamos sequencial para não quebrar
        id_veiculo_banco = ids_veiculos_reais[v_id] if v_id < len(ids_veiculos_reais) else (v_id + 1)

        lista_estruturada_rota = [] # A lista que vai pro banco
        nomes_passos = []
        pass_dia = 0    
        ocupacao_atual = 0 
        max_ocupacao = 0
        
        # Simula horário de saída (ex: 07:00 da manhã de hoje)
        hora_atual_segundos = 7 * 3600 # Começa as 07:00 em segundos
        
        # Itera sobre os nós da rota
        for i, node in enumerate(nodes):
            demanda_node = demandas[node]
            
            # --- Tenta pegar os dados reais do nó ---
            # info_nos deve ser uma lista onde o índice bate com o node do solver
            dados_node_original = info_nos[node] if node < len(info_nos) else {}
            
            # Recupera IDs ou usa None/Zeros se não tiver
            id_paciente = dados_node_original.get('id_paciente') # None se for base
            id_endereco = dados_node_original.get('id_endereco', 1) # Fallback 1
            id_solicitacao = dados_node_original.get('id_solicitacao') 
            
            # --- Cálculo de Tempo ---
            # Adiciona o tempo de viagem do nó anterior até este
            if i > 0:
                tempo_viagem = matriz_tempo[nodes[i-1]][node]
                hora_atual_segundos += tempo_viagem
            
            # Formata hora para HH:MM:SS
            hora_formatada = str(timedelta(seconds=hora_atual_segundos))

            # --- Define o Tipo de Parada e Strings do Relatório ---
            tipo_parada = "OUTROS"
            passo_str = ""

            if node == 0: # Depósito
                tipo_parada = "BASE" # Ajuste se seu ENUM não tiver BASE
                passo_str = "[BASE/UPA]"
            elif demanda_node > 0: # Coleta
                tipo_parada = "COLETA"
                passo_str = f"(Pega {dados_node_original.get('nome_paciente', f'P{node}')})"
                pass_dia += 1
                ocupacao_atual += 1 
            elif demanda_node < 0: # Entrega
                tipo_parada = "ENTREGA"
                passo_str = f"[HOSPITAL/DESTINO]"
                ocupacao_atual -= 1 

            if ocupacao_atual > max_ocupacao: max_ocupacao = ocupacao_atual

            # Adiciona strings para o print
            if passo_str:
                if "BASE" in passo_str: nomes_passos.append(passo_str)
                else: nomes_passos.append(f"{passo_str} [{ocupacao_atual}/{cap_max}]")

            # --- MONTA O OBJETO PARA O BANCO DE DADOS ---
            # Se for BASE e seu banco não aceita ID_PACIENTE nulo, cuidado.
            # Mas com o ALTER TABLE que passamos, deve aceitar None.
            parada_struct = {
                "id_veiculo": id_veiculo_banco,
                "id_paciente": id_paciente, # Pode ser None
                "id_endereco": id_endereco,
                "tipo": tipo_parada,
                "hora_estimada": hora_formatada,
                "id_solicitacao": id_solicitacao,
                "ordem": i + 1
            }
            lista_estruturada_rota.append(parada_struct)

        # --- IMPRIME RELATÓRIO DO VEÍCULO ---
        status = "(PARADO)" if len(nodes) <= 2 else f"(EM ROTA)" # Ajuste simples
        cor_status = "🔴" if "PARADO" in status else "🟢"
        tipo_veiculo_nome = " ÔNIBUS" if cap_max >= 10 else "CARRO"
        
        print(f"{cor_status} VEÍCULO {v_id} (ID DB: {id_veiculo_banco}) {status} - {tipo_veiculo_nome} (Assentos: {cap_max})")
        if len(nodes) > 1:
            print(f"   Passageiros Transportados: {pass_dia}")
            print(f"   Rota: {' -> '.join(nomes_passos)}")
        print("-" * 70)

        # Só adiciona no retorno se tiver rota real
        if len(nodes) > 2:
            chave_rota = f"rota{rota_counter}"
            dados_para_salvar[chave_rota] = lista_estruturada_rota
            rota_counter += 1

    print("="*70 + "\n")

    # Retorna APENAS os dados estruturados (dicionários) para o app.py salvar
    return dados_para_salvar