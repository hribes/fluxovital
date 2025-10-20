import requests
from dotenv import load_dotenv
import os

# Carrega a chave do arquivo .env
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

def endereco_para_coordenadas(endereco: str):
    """
    Converte um endereço em coordenadas (latitude e longitude)
    usando a API Google Maps Geocoding.
    """
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": endereco, "key": API_KEY}

    response = requests.get(base_url, params=params)
    data = response.json()

    # Verifica o status
    if data["status"] == "OK":
        resultado = data["results"][0]
        localizacao = resultado["geometry"]["location"]

        lat = round(localizacao["lat"], 14)
        lon = round(localizacao["lng"], 14)

        print(f"Endereço: {resultado['formatted_address']}")
        print(f"Coordenadas: ({lat}, {lon})")
        return lat, lon
    else:
        print(f"Erro: {data['status']}")
        return None, None


# Exemplo de uso
if __name__ == "__main__":
    endereco = "Rua Major Eliziario de Camargo, 325, Marília, São Paulo, Brasil"
    endereco_para_coordenadas(endereco)


# [Rua / Avenida], [Número], [Bairro], [Cidade], [Estado], [País]










# import openrouteservice
# from dotenv import load_dotenv
# import os
# import requests
# import json

# load_dotenv()
# API_KEY = os.getenv("API_KEY")

# chave = openrouteservice.Client(key=API_KEY)

# # Endpoint de geocodificação do ORS
# url = "https://api.openrouteservice.org/geocode/search"

# # Endereço de exemplo
# endereco = "Rua das Acacias, 753, Oriente, Brasil"

# # Centro do estado de São Paulo (aproximado)
# centro_sp = [-46.6333, -23.5505]  # [lon, lat]
# raio_metros = 350000  # 350 km

# # Parâmetros da requisição
# params = {
#     "api_key": API_KEY,
#     "text": endereco,
#     "boundary.country": "BR",
#     "boundary.circle.lon": centro_sp[0],
#     "boundary.circle.lat": centro_sp[1],
#     "boundary.circle.radius": raio_metros
# }

# # Faz a requisição
# response = requests.get(url, params=params)

# # Trata o retorno
# if response.status_code == 200:
#     resultado = response.json()
#     if resultado["features"]:
#         for feature in resultado["features"]:
#             props = feature["properties"]
#             geom = feature["geometry"]
            
#             # Extrai longitude e latitude
#             lon, lat = geom["coordinates"]
            
#             # Arredonda para 7 casas decimais
#             lon = round(lon, 14)
#             lat = round(lat, 14)
            
#             print(f"📍 Local: {props['label']}")
#             print(f"   Coordenadas: [{lon}, {lat}]")
#             print(f"   Confiança: {props.get('confidence', 'N/A')}")
#             print("------")
#     else:
#                 print("Nenhum resultado encontrado dentro da área.")
# else:
#     print(f"Erro {response.status_code}: {response.text}")
    
#     #-22.156941200633728, -50.08982601697348
