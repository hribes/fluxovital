import openrouteservice
import folium

def construir_matriz_tempo_distancia(dados, ors_api_key):
    """
    Usa o OpenRouteService para construir a matriz de tempo e distância
    a partir das coordenadas no dicionário 'dados'.
    """

    print("Construindo matrizes de tempo e distância com ORS...")

    client = openrouteservice.Client(key=ors_api_key)

    # Pega as coordenadas (lat, lon) do dicionário
    locations_lat_lon = dados['coordenadas']

    # IMPORTANTE: ORS espera (longitude, latitude), o oposto do Google/Folium
    locations_lon_lat = [[lon, lat] for lat, lon in locations_lat_lon]

    try:
        matriz = client.distance_matrix(
            locations=locations_lon_lat,
            metrics=['duration', 'distance'], # Pede tempo (segundos) e distância (metros)
            units='m' 
        )
 
        # Adiciona as matrizes ao dicionário 'dados'
        # O solver do OR-Tools espera inteiros, então convertemos
        dados['matriz_tempo'] = [[int(val) for val in row] for row in matriz['durations']]
        dados['matriz_distancia'] = [[int(val) for val in row] for row in matriz['distances']]

        print("Matrizes de tempo e distância construídas com sucesso.")
        return dados

    except Exception as e:
        print(f"Erro ao chamar a API do OpenRouteService: {e}")
        return None

def desenhar_mapa_localizacoes(dados, nome_arquivo="mapa_localizacoes.html"):
    """
    Desenha um mapa com a UPA (depósito), pontos de coleta e pontos de entrega.
    """

    print(f"Salvando mapa de localizações em '{nome_arquivo}'...")

    # (lat, lon)
    upa_coords = dados['deposito_coords']
    mapa = folium.Map(location=upa_coords, zoom_start=14)

    # Adiciona UPA
    folium.Marker(
        location=upa_coords,
        popup="UPA (Depósito)",
        icon=folium.Icon(color='red', icon='hospital-o', prefix='fa')
    ).add_to(mapa)
 
    n_pacientes = len(dados['coletas_entregas'])

    # Coordenadas de Coleta (índices 1 até n_pacientes)
    coletas_coords = dados['coordenadas'][1 : 1 + n_pacientes]

    # Coordenadas de Entrega (índices n_pacientes + 1 até o fim)
    entregas_coords = dados['coordenadas'][1 + n_pacientes : ]

    # Adiciona Coletas (Casas)
    for i, coord in enumerate(coletas_coords):
        folium.Marker(
            location=coord,
            popup=f"Coleta Paciente {i+1}",
            icon=folium.Icon(color='blue', icon='home')
        ).add_to(mapa)

    # Adiciona Entregas (Clínicas)
    for i, coord in enumerate(entregas_coords):
        folium.Marker(
            location=coord,
            popup=f"Entrega Paciente {i+1}",
            icon=folium.Icon(color='green', icon='plus-square', prefix='fa')
        ).add_to(mapa)

    mapa.save(nome_arquivo)