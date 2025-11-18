# app.py

from flask import Flask, render_template, send_from_directory
import folium
import requests
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import os

# 1. INICIALIZAÇÃO DO FLASK
app = Flask(__name__, template_folder="frontend/desktop/pages")


# 2. ROTAS ESTÁTICAS CUSTOMIZADAS
@app.route('/styles/<path:filename>')
def custom_styles_static(filename):
    directory = os.path.join(os.getcwd(), 'frontend', 'desktop', 'styles')
    return send_from_directory(directory, filename)

@app.route('/assets/<path:filename>')
def custom_assets_static(filename):
    directory = os.path.join(os.getcwd(), 'frontend', 'desktop', 'assets')
    return send_from_directory(directory, filename)

@app.route('/services/<path:filename>')
def custom_services_static(filename):
    directory = os.path.join(os.getcwd(), 'frontend', 'desktop', 'services')
    return send_from_directory(directory, filename)


# DADOS
pacientes = [
    (-22.217748, -49.950521), 
    (-22.225829, -49.932824), 
    (-22.186588, -49.949813), 
    (-22.203619, -49.972021), 
    (-22.202060097362207, -49.939072758426455),
    (-22.164939380761968, -49.96938552881704)
]

hospitais = [
    (-22.213050, -49.945399),
    (-22.219537, -49.928923), 
]

pontos = pacientes + hospitais


# FUNÇÕES DE LÓGICA (ORTOOLS, OSRM)

def matriz_distancias_duracoes():
    coords = ";".join([f"{lon},{lat}" for lat, lon in pontos])
    url = f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=distance,duration"
    r = requests.get(url)
    if r.status_code != 200:
        print("Erro na OSRM TABLE:", r.text)
        return None, None
    data = r.json()
    return data["distances"], data["durations"]


def resolver_rota():
    dist, dur = matriz_distancias_duracoes()
    if dist is None or dur is None:
        return None

    entregas = {
        0: 6, 
        1: 7, 
        2: 6, 
        3: 7,
        4: 6,
        5: 7
        
        } 
    

    #Define a qnt de veiculos na rota
    manager = pywrapcp.RoutingIndexManager(len(dist), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def cb(from_index, to_index):
        f = manager.IndexToNode(from_index)
        t = manager.IndexToNode(to_index)
        return int(dist[f][t])
    transit_idx = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    # Pickups / deliveries
    for p, h in entregas.items():
        p_i = manager.NodeToIndex(p)
        h_i = manager.NodeToIndex(h)
        routing.AddPickupAndDelivery(p_i, h_i)
        routing.solver().Add(routing.VehicleVar(p_i) == routing.VehicleVar(h_i))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.seconds = 5

    sol = routing.SolveWithParameters(params)
    if not sol:
        return None

    rota = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        rota.append(manager.IndexToNode(index))
        index = sol.Value(routing.NextVar(index))

    return rota, dur


def rota_real_osrm(lista_coordenadas):
    pontos_str = ";".join([f"{lon},{lat}" for lat, lon in lista_coordenadas])
    url = f"https://router.project-osrm.org/route/v1/driving/{pontos_str}?overview=full&geometries=geojson"
    r = requests.get(url)
    if r.status_code != 200:
        print("Erro OSRM:", r.text)
        return []
    data = r.json()
    return data["routes"][0]["geometry"]["coordinates"]


#Rotas
@app.route("/")
def index_page():
    return render_template("index.html")

@app.route("/home")
def home_page():
    return render_template("home.html")

@app.route("/cadastrar/consulta")
def cadastrar_consulta():
    return render_template("cadastro_consulta.html")

@app.route("/cadastrar/paciente")
def cadastrar_paciente():
    return render_template("cadastro_paciente.html")

@app.route("/cadastrar/hospital")
def cadastrar_hospital():
    return render_template("cadastro_hospital.html")

@app.route("/cadastrar/funcionario")
def cadastrar_funcionario():
    return render_template("cadastro_funcionarios.html")

@app.route("/cadastrar/motorista")
def cadastrar_motorista():
    return render_template("cadastro_motorista.html")

@app.route("/cadastrar/veiculo")
def cadastrar_veiculo():
    return render_template("cadastro_veiculo.html")

@app.route("/agendamentos")
def consultar_paciente():
    return render_template("consulta_pacientes.html")

@app.route("/atribuir/motorista")
def atribuir_motorista():
    map_html, tempo_total_min = gerar_mapa()
    if map_html is None:
        return "<h1>Sem solução</h1>"

    return render_template(
        "atribuicao_motoristas.html",
        map=map_html,
        tempo_total_min=tempo_total_min
    )

@app.route("/visualizar/motorista")
def consultar_motoristas():
    return render_template("consulta_motorista.html")

@app.route("/visualizar/veiculo")
def consultar_veiculos():
    return render_template("consulta_veiculos.html")

@app.route("/veiculo/rotas")
def consultar_veiculos_rotas():
    return render_template("consulta_veiculos.c.rotas.html")


@app.route("/rotas")
def rotas_page():
    map_html, tempo_total_min = gerar_mapa()
    if map_html is None:
        return "<h1>Sem solução</h1>"

    return render_template(
        "visualizacao_rotas.html",
        map=map_html,
        tempo_total_min=tempo_total_min
    )


#Função para gerar o mapa
def gerar_mapa():
    resultado = resolver_rota()
    if resultado is None:
        return "<h1>Sem solução</h1>"
    rota, dur = resultado

    coords = [pontos[n] for n in rota]

    # pegar caminho real via ruas
    caminho_osrm = rota_real_osrm(coords)
    caminho_osrm = [(latlon[1], latlon[0])
                    for latlon in caminho_osrm] 
    

    m = folium.Map(location=(-22.2177, -49.9450), zoom_start=13)

    for i, (lat, lon) in enumerate(pontos):
        if i < 6:
            folium.Marker([lat, lon], icon=folium.Icon(
                color="green"), tooltip=f"P{i+1}").add_to(m)
        else:
            folium.Marker([lat, lon], icon=folium.Icon(
                color="red"), tooltip=f"H{i-3}").add_to(m)
            
    for ordem, ponto_index in enumerate(rota):
        lat, lon = pontos[ponto_index]
        tempo_seg = 0
        if ordem < len(rota) - 1:
            prox = rota[ordem + 1]
            tempo_seg = dur[ponto_index][prox]
        tempo_min = int(tempo_seg / 60)

        folium.map.Marker(
            [lat, lon],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size: 16px;
                    font-weight: bold;
                    color: black;
                    background: white;
                    border: 2px solid black;
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    text-align: center;
                ">{ordem} ({tempo_min} min)</div>
                """
            )
        ).add_to(m)

    # Desenhar a rota real
    folium.PolyLine(caminho_osrm, weight=6, color="blue").add_to(m)

    # Calcular tempo total estimado do percurso
    tempo_total_segundos = 0
    for i in range(len(rota) - 1):
        tempo_total_segundos += dur[rota[i]][rota[i+1]]

    tempo_total_min = int(tempo_total_segundos / 60)
    print(f"Tempo total estimado do percurso: {tempo_total_min} min")

    return m._repr_html_(), tempo_total_min



if __name__ == "__main__":
    app.run(debug=True)