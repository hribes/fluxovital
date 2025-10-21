import os
import folium
from dotenv import load_dotenv
import openrouteservice

load_dotenv()
API_KEY = os.getenv("API_KEY")  # Carrega a chave API

#Passa ao contrario 
coordenadas = [
   [-50.09005190528351, -22.159595080264985],
    [-50.09277300543698, -22.152210923629422],
    [-50.09662021646666, -22.148760530381058],
    [-50.0878595931188, -22.15839956501419],
    [-50.09807707470197, -22.15438780219639] 
]   

# Folium → mapa
#Coloca normal
pontos = [
    {"nome": "Casa 1", "coords": [-22.159595080264985, -50.09005190528351]},
    {"nome": "Casa 2", "coords": [-22.152210923629422, -50.09277300543698]},
    {"nome": "Hospital", "coords": [-22.152944365127116, -50.09306453604891]},
    {"nome": "Casa 3 ", "coords": [-22.15438780219639, -50.09807707470197] }
]

mapa = folium.Map(location=[-22.1530, -50.0910], zoom_start=15)

# Adiciona marcadores no mapa
for ponto in pontos:
    folium.Marker(
        location=ponto["coords"], 
        popup=ponto["nome"],
        icon=folium.Icon(color="blue" if "Casa" in ponto["nome"] else "red")
    ).add_to(mapa)

# Cria um arquivo html com o mapa!
mapa.save("mapa_oriente.html")

#Traça a rota no mapa

