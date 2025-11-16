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