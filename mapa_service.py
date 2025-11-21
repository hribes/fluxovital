import requests
import folium
from folium.features import DivIcon
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# --- DADOS ESTÁTICOS ---
secretaria_saude = (-22.213200, -49.944700) # Ponto 0

lista_pacientes = [
    (-22.217748, -49.950521), # P1
    (-22.225829, -49.932824), # P2
    (-22.186588, -49.949813), # P3
    (-22.203619, -49.972021), # P4
    (-22.202060, -49.939072), # P5
    (-22.164939, -49.969385), # P6
    (-22.230100, -49.960200), # P7
    (-22.195500, -49.925500), # P8
    (-22.210000, -49.980000)  # P9
]

# --- DEFINIÇÃO DOS LOCAIS FÍSICOS ---
hosp_A = (-22.213050, -49.945399)
hosp_B = (-22.219537, -49.928923)
hosp_C = (-22.209111, -49.957376)

NOMES_LOCAIS = {
    secretaria_saude: "[BASE]",
    hosp_A: "[HOSP. CLÍNICAS]",
    hosp_B: "[SANTA CASA]",
    hosp_C: "[HOSP. MATERNO]"
}

destinos_reais = [
    hosp_A, #P1
    hosp_B, #P2
    hosp_C, #P3
    hosp_A, #P4
    hosp_B, #P5
    hosp_C, #P6
    hosp_A, #P7 
    hosp_B, #P8 
    hosp_C, #P9
]

# --- OSRM E MATRIZ ---
def matriz_distancias_duracoes(pontos_todos):
    coords = ";".join([f"{lon},{lat}" for lat, lon in pontos_todos])
    url = f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=distance,duration"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None, None
        data = r.json()
        return data["distances"], data["durations"]
    except: return None, None

def rota_real_osrm(lista_coordenadas):
    if not lista_coordenadas or len(lista_coordenadas) < 2: return [], 0
    pontos_str = ";".join([f"{lon},{lat}" for lat, lon in lista_coordenadas])
    url = f"https://router.project-osrm.org/route/v1/driving/{pontos_str}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=6)
        if r.status_code != 200: return [], 0
        data = r.json()
        return data["routes"][0]["geometry"]["coordinates"], data["routes"][0]["duration"]
    except: return [], 0

# --- LÓGICA DO SOLVER (OR-TOOLS) ---
def resolver_vrp(veiculos, entregas, pontos_locais):
    _, dur_matrix_real = matriz_distancias_duracoes(pontos_locais)
    if not dur_matrix_real: return {}, None

    n_real = len(dur_matrix_real)
    n_total = n_real + 1
    dur_matrix = [row + [0] for row in dur_matrix_real]
    dur_matrix.append([0] * n_total)

    manager = pywrapcp.RoutingIndexManager(n_total, len(veiculos), [0]*len(veiculos), [n_real]*len(veiculos))
    routing = pywrapcp.RoutingModel(manager)

    def duration_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == n_real or to_node == n_real: return 0
        return int(dur_matrix[from_node][to_node])

    transit_idx = routing.RegisterTransitCallback(duration_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    # ---  LÓGICA DE CUSTO FIXO POR VEÍCULO ---
    for i, v in enumerate(veiculos):
        capacidade = v['capacidade']
        
        # Se for "ônibus" (capacidade alta), custo fixo alto
        if capacidade >= 10:
            custo_fixo = 100000 
        else:
            custo_fixo = 0 
            
        # Aplica o custo ao modelo
        routing.SetFixedCostOfVehicle(custo_fixo, i)

    #  Dimensão de Tempo
    routing.AddDimension(transit_idx, 3000, 100000, True, "Time")

    #  Dimensão de Capacidade
    demands = [0] * n_total
    for p, d in entregas.items(): 
        demands[p] = 1
        demands[d] = -1
    
    def demand_callback(from_index): return demands[manager.IndexToNode(from_index)]
    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, [v['capacidade'] for v in veiculos], True, "Capacity")

    #  Obrigação de Visita
    PENALIDADE_GIGANTE = 100000000 
    for p, d in entregas.items():
        p_idx, d_idx = manager.NodeToIndex(p), manager.NodeToIndex(d)
        routing.AddPickupAndDelivery(p_idx, d_idx)
        routing.solver().Add(routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx))
        routing.AddDisjunction([p_idx], PENALIDADE_GIGANTE)
        routing.AddDisjunction([d_idx], PENALIDADE_GIGANTE)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 30

    solution = routing.SolveWithParameters(search_params)
    rotas = {}
    if solution:
        for v_id in range(len(veiculos)):
            index = routing.Start(v_id)
            rota = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node != n_real: rota.append(node)
                index = solution.Value(routing.NextVar(index))
            rotas[veiculos[v_id]['id']] = rota
    return rotas, dur_matrix_real

# --- VISUALIZAÇÃO HTML ---
def desenhar_mapa_veiculo(rota_indices, pontos_globais, cor_veiculo, titulo):
    m = folium.Map(location=secretaria_saude, zoom_start=13)
    title_html = f'''<h3 align="center" style="font-size:16px"><b>{titulo}</b></h3>'''
    m.get_root().html.add_child(folium.Element(title_html))

    if not rota_indices: return m._repr_html_()

    coords_rota = [pontos_globais[i] for i in rota_indices]
    for i in range(len(coords_rota) - 1):
        trecho = [coords_rota[i], coords_rota[i+1]]
        caminho_geo, _ = rota_real_osrm(trecho)
        if caminho_geo:
            linha = [(c[1], c[0]) for c in caminho_geo]
            folium.PolyLine(linha, weight=5, color=cor_veiculo, opacity=0.8).add_to(m)
        else:
            folium.PolyLine(trecho, weight=3, color=cor_veiculo, dash_array='5,5').add_to(m)

    qtd_pacs_estatico = 9 
    for i, node in enumerate(rota_indices):
        lat, lon = pontos_globais[node]
        cor, icone, tooltip = "gray", "info-sign", f"Passo {i}"
        if node == 0: cor, icone, tooltip = "black", "home", "Secretaria"
        elif 1 <= node <= qtd_pacs_estatico: cor, icone, tooltip = "green", "user", f"Pega P{node}"
        else: cor, icone, tooltip = "red", "plus", "Hospital"

        folium.Marker([lat, lon], icon=folium.Icon(color=cor, icon=icone, prefix='fa'), tooltip=f"{i+1}. {tooltip}").add_to(m)
    return m._repr_html_()

def get_mapa_vazio():
    m = folium.Map(location=secretaria_saude, zoom_start=13)
    return m._repr_html_()

# --- FUNÇÃO PRINCIPAL ---
def get_mapas_calculados(data_rota=None):
    if data_rota:
        print(f"\nDATA RECEBIDA: {data_rota}")
        pass
        return None 
    else:
        # --- VEICULOS ---
        veiculos = [
            {'id': 1, 'capacidade': 4}, 
            {'id': 2, 'capacidade': 3},
            {'id': 3, 'capacidade': 2},
            {'id': 4, 'capacidade': 30} 
        ]
        
        pontos = [secretaria_saude] + lista_pacientes + destinos_reais
        entregas = {i+1: i+1+len(lista_pacientes) for i in range(len(lista_pacientes))}

    # CÁLCULO
    rotas, matriz_duracoes = resolver_vrp(veiculos, entregas, pontos)
    mapas = {}
    
    if not rotas:
        print("Nenhuma solução encontrada.")
        return None


    print("\n" + "="*70)
    print(f"ROTAS OTIMIZADAS - Priorizando Custo/Eficiência")
    print("="*70)

    qtd_pacs = len(lista_pacientes)

    for v_info in veiculos:
        vid = v_info['id']
        cap_max = v_info['capacidade']
        nodes = rotas.get(vid, [])
        
        nomes_passos = []
        pass_dia = 0    
        ocupacao_atual = 0 
        max_ocupacao = 0
        
        # Cálculo de tempo
        tempo_rota_segundos = 0
        if matriz_duracoes and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                origem = nodes[i]
                destino = nodes[i+1]
                if origem < len(matriz_duracoes) and destino < len(matriz_duracoes):
                    tempo_rota_segundos += matriz_duracoes[origem][destino]
        
        tempo_rota_min = int(tempo_rota_segundos / 60)

        for node in nodes:
            passo_str = ""
            if node == 0:
                passo_str = NOMES_LOCAIS.get(secretaria_saude, "[BASE]")
            elif 1 <= node <= qtd_pacs:
                passo_str = f"(Pega P{node})"
                pass_dia += 1
                ocupacao_atual += 1 
            else:
                if node < len(pontos):
                    coord_atual = pontos[node]
                    nome_hosp = NOMES_LOCAIS.get(coord_atual, "[DESTINO]")
                else: nome_hosp = "[DESTINO]"
                passo_str = nome_hosp
                ocupacao_atual -= 1 

            if ocupacao_atual > max_ocupacao:
                max_ocupacao = ocupacao_atual

            if passo_str:
                if "BASE" in passo_str: nomes_passos.append(passo_str)
                else: nomes_passos.append(f"{passo_str} [{ocupacao_atual}/{cap_max}]")

        status = "(PARADO)" if len(nomes_passos) <= 1 else f"(EM ROTA - {tempo_rota_min} min)"
        cor_status = "🔴" if "PARADO" in status else "🟢"
        
        # Exibe qual veículo é o "Grande"
        tipo_veiculo = " ÔNIBUS" if cap_max >= 10 else "CARRO"
        
        print(f"{cor_status} VEÍCULO {vid} {status} - {tipo_veiculo} (Assentos: {cap_max})")
        print(f"   Passageiros Transportados: {pass_dia}")
        print(f"   Rota: {' -> '.join(nomes_passos)}")
        print("-" * 70)
    print("="*70 + "\n")

    # 4. MAPAS HTML (Gera apenas para os carros pequenos neste exemplo)
    if 1 in rotas: mapas['rota1'] = desenhar_mapa_veiculo(rotas[1], pontos, "blue", "Rota V1")
    if 2 in rotas: mapas['rota2'] = desenhar_mapa_veiculo(rotas[2], pontos, "purple", "Rota V2")

    return mapas