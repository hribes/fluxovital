import openrouteservice
from dotenv import load_dotenv
import os
import folium
import json

load_dotenv()
API_KEY = os.getenv("API_KEY")

chave = openrouteservice.Client(key=API_KEY)

matriz_coords = []
indice_coord_hospitais = []
indice_coord_residencias = []
i = 0
j = 0

"""
1- Pegar as coordenadas das casas
2- Pegar as coordenadas dos destinos - hospitais
3- Colocar casas + hospitais no formato matriz N X N 
4- Enviar para o ORS
5- Mostrar na tela a matriz com os TEMPOS (antes era distancia)
"""

#Coordenadas das residencias dos pacientes
coord_residencias = [
    [-50.09005190528351, -22.159595080264985],
    [-50.09277300543698, -22.152210923629422],
    [-50.09662021646666, -22.148760530381058],
    [-50.0878595931188, -22.15839956501419],
    [-50.09807707470197, -22.15438780219639]  
]

#Coordenadas hospitais
coord_hospitais = [
    [-50.09195132993289, -22.153164028151053],
    [-50.09680055090296, -22.154531012447393],
    [-50.09048182392179, -22.15832696162462]
]

#De casa N até hospital N - traçar as rotas
rotas_definidas = {
    1: 1,  
    2: 1,  
    3: 1,  
    4: 1,  
    5: 1  
}

#adiciona as coordenadas na lista
for coordenadas in coord_hospitais:
    matriz_coords.append(coordenadas) 
    indice_coord_hospitais.append(i)
    i+=1
    
#Coloca coordenadas das casas junto dos hospitais  
for coordenadas in coord_residencias:
    matriz_coords.append(coordenadas)
    indice_coord_residencias.append(i + j)
    j+=1
    
# for i in matriz_coords:
#     print(i)
    
        
# --- ALTERAÇÃO 1: Solicitar 'duration' (tempo) em vez de 'distance' ---
#Envia a matriz para o ORS
matriz = chave.distance_matrix(
    locations = matriz_coords,
    sources = indice_coord_residencias,
    destinations = indice_coord_hospitais,
    metrics = ['duration'],  # Alterado de 'distance' para 'duration'
    # 'units' foi removido, 'duration' é retornado em segundos por padrão
)

# --- ALTERAÇÃO 2: Atualizar o print para mostrar o tempo ---
# O resultado agora está em 'durations', não 'distances'
print("Matriz de tempo (em minutos): ")
if 'durations' in matriz:
    for i, linha_segundos in enumerate(matriz['durations']): #itera sobre uma lista e obtem o indice do item
        # Converte segundos para minutos para melhor legibilidade
        linha_minutos = [round(tempo / 60, 2) for tempo in linha_segundos]
        print(f"Casa {i+1} -> Tempos para hospitais (minutos): {linha_minutos}")
else:
    print("Erro ao obter a matriz de tempo:")
    print(matriz) # Mostra o erro, se houver
    
#Para adicionar as coordenadas no mapa
mapa = folium.Map(location=[coord_residencias[0][1], coord_residencias[0][0]], zoom_start=14)

# Adiciona os hospitais no mapa
for i, coord in enumerate(coord_hospitais):
    folium.Marker(
        location=[coord[1], coord[0]],  #latitude, longitude
        popup=f"Hospital {i+1}",
        icon=folium.Icon(color='red', icon='plus-sign')
    ).add_to(mapa)

# Adiciona as residências no mapa
for i, coord in enumerate(coord_residencias):
    folium.Marker(
        location=[coord[1], coord[0]],
        popup=f"Casa {i+1}",
        icon=folium.Icon(color='blue', icon='home')
    ).add_to(mapa)
   

origem = coord_residencias[0]    
destino = coord_hospitais[0]     


for casa, hospital in rotas_definidas.items():
    origem = coord_residencias[casa-1]
    destino = coord_hospitais[hospital-1]

    rota = chave.directions(
        coordinates=[origem, destino],
        profile='driving-car',
        preference='fastest',
        format='geojson'
    )
    
    #Retorno bonitinho do json
    # print(json.dumps(rota, indent=4)) 
    
    # --- ALTERAÇÃO 3: Extrair 'duration' (tempo) para o tooltip do mapa ---
    
    # O OpenRouteService retorna a duração em segundos no JSON
    duracao_s = rota['features'][0]['properties']['segments'][0]['duration']
    duracao_min = round(duracao_s / 60, 2) # Converte para minutos
    
    # Você ainda pode pegar a distância se quiser, apenas para exibir
    distancia_m = rota['features'][0]['properties']['segments'][0]['distance']
    distancia_km = round(distancia_m / 1000, 2) 

    # print(f"Duração em segundos: {duracao_s}, Duração em minutos: {duracao_min}")


    # Adiciona a rota ao mapa, agora com o tooltip de TEMPO
    folium.GeoJson(
        rota,
        # Corrigi o 'i+1' para usar 'casa' e 'hospital' do loop atual
        name=f"Rota Casa {casa} → Hospital {hospital}", 
        # Alterei o tooltip para mostrar o tempo (e mantive a distância por clareza)
        tooltip=f"Tempo: {duracao_min} min<br>Distância: {distancia_km} km",
    ).add_to(mapa)

# Salva o mapa com um novo nome para não sobrescrever o original
mapa.save("mapa_residencias_hospitais_TEMPO.html")
print("\nMapa 'mapa_residencias_hospitais_TEMPO.html' salvo com sucesso.")