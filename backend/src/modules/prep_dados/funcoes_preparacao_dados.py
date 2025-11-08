import pandas as pd
from datetime import datetime
import requests
from dotenv import load_dotenv
import os

# Carrega a chave do arquivo .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Funções Auxiliares ---

def endereco_para_coordenadas(endereco: str):
    """
    Converte um endereço em coordenadas (latitude e longitude)
    usando a API Google Maps Geocoding.
    Retorna (lat, lon)
    """
    if not GOOGLE_API_KEY:
        print("Erro: GOOGLE_API_KEY não encontrada no .env")
        return None, None

    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": endereco, "key": GOOGLE_API_KEY}

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        # Verifica o status
        if data["status"] == "OK":
            resultado = data["results"][0]
            localizacao = resultado["geometry"]["location"]

            lat = round(localizacao["lat"], 14)
            lon = round(localizacao["lng"], 14)

            print(f"Endereço: {resultado['formatted_address']} -> Coords: ({lat}, {lon})")
            return lat, lon
        else:
            print(f"Erro de Geocoding: {data['status']} para o endereço: {endereco}")
            return None, None
    except Exception as e:
        print(f"Erro na requisição ao Google Maps: {e}")
        return None, None


def to_seconds_since_midnight(timestamp_str):
    """
    Converte uma string de data/hora (ex: '2025-10-08 10:00:00') 
    em segundos desde a meia-noite do mesmo dia.
    """
    if pd.isna(timestamp_str):
        return 0

    try:
        dt_object = pd.to_datetime(timestamp_str)
        time_object = dt_object.time()
        return time_object.hour * 3600 + time_object.minute * 60 + time_object.second
    except Exception:
        return 0

# --- Função Principal de Preparação ---

def preparar_dados(df_veiculos, df_pacientes, dia_operacao, upa_address):
    """
    Transforma os DataFrames de veículos e pacientes no dicionário de dados
    formatado para o solver OR-Tools (PDPTW).
    """

    print("Iniciando preparação dos dados...")
    dados = {}

    # 1. Geocodificar o Depósito (UPA)
    upa_lat, upa_lon = endereco_para_coordenadas(upa_address)
    if not upa_lat:
        raise ValueError(f"Não foi possível encontrar as coordenadas da UPA: {upa_address}")

    dados['deposito_coords'] = (upa_lat, upa_lon) # Salva como (lat, lon)
    dados['deposito'] = 0
    print(f"Coordenadas da UPA ({upa_address}): {dados['deposito_coords']}")

    # 2. Processar Veículos
    df_veiculos_disponiveis = df_veiculos[df_veiculos['NOME_STATUS'] == 'Disponível'].copy()

    dados['num_veiculos'] = len(df_veiculos_disponiveis)
    dados['capacidade_veiculos'] = df_veiculos_disponiveis['CAPACIDADE'].tolist()
    dados['veiculo_tem_maca'] = df_veiculos_disponiveis['MACA'].astype(bool).tolist()

    print(f"Veículos disponíveis: {dados['num_veiculos']}")

    # 3. Processar Pacientes
    df_pacientes['DATA_HORA_CONSULTA'] = pd.to_datetime(df_pacientes['DATA_HORA_CONSULTA'])
    df_pacientes_hoje = df_pacientes[df_pacientes['DATA_HORA_CONSULTA'].dt.date == pd.to_datetime(dia_operacao).date()].copy()
    print(f"Total de pacientes para {dia_operacao}: {len(df_pacientes_hoje)}")

    if len(df_pacientes_hoje) == 0:
        print("Nenhum paciente para o dia selecionado. Encerrando.")
        return None

    coletas_coords = []
    entregas_coords = []
    coletas_demandas = []
    entregas_demandas = []
    coletas_maca = []
    entregas_maca = []
    entregas_janelas = []

    print("Iniciando geocodificação dos pacientes...")
    for _, paciente in df_pacientes_hoje.iterrows():

        # Endereços
        addr_coleta = (
        f"{paciente['NOME_RUA']}, {paciente['NUMERO_ENDERECO']}, "
        f"{paciente['NOME_BAIRRO']}, {paciente['NOME_CIDADE']}, {paciente['CEP']}"
        )
        addr_entrega = (
            f"{paciente['NOME_RUA_LOCALATENDIMENTO']}, {paciente['NUMERO_ENDERECO_LOCALATENDIMENTO']}, "
            f"{paciente['NOME_BAIRRO_LOCALATENDIMENTO']}, {paciente['NOME_CIDADE_LOCALATENDIMENTO']}, {paciente['CEP_LOCALATENDIMENTO']}"
        )

        coord_coleta_lat, coord_coleta_lon = endereco_para_coordenadas(addr_coleta)
        coord_entrega_lat, coord_entrega_lon = endereco_para_coordenadas(addr_entrega)

        if not coord_coleta_lat or not coord_entrega_lat:
            print(f"Pulando Paciente ID {paciente['ID_PACIENTE']} por falha na geocodificação.")
            continue

        coletas_coords.append((coord_coleta_lat, coord_coleta_lon))
        entregas_coords.append((coord_entrega_lat, coord_entrega_lon))

        # Demanda
        demanda = 2 if paciente['ACOMPANHANTE'] else 1
        coletas_demandas.append(demanda)
        entregas_demandas.append(-demanda) 

        # Maca
        maca = bool(paciente['MACA'])
        coletas_maca.append(maca)
        entregas_maca.append(maca)

        # Janelas de Tempo
        t_max_chegada = to_seconds_since_midnight(paciente['DATA_HORA_MAX_CHEGADA'])
        t_consulta = to_seconds_since_midnight(paciente['DATA_HORA_CONSULTA'])
        entregas_janelas.append((min(t_max_chegada, t_consulta), max(t_max_chegada, t_consulta)))

    print("Geocodificação concluída.")

    # 4. Montar o Dicionário 'dados' Final (na ordem UPA -> Coletas -> Entregas)

    dados['coordenadas'] = [dados['deposito_coords']] + coletas_coords + entregas_coords
    dados['demanda_assentos'] = [0] + coletas_demandas + entregas_demandas
    dados['necessidade_maca'] = [False] + coletas_maca + entregas_maca

    janela_aberta = (0, 86400) # Janela de 24h
    coletas_janelas = [janela_aberta] * len(coletas_coords)
    dados['janelas_tempo'] = [janela_aberta] + coletas_janelas + entregas_janelas

    n_pacientes = len(coletas_coords)
    dados['coletas_entregas'] = [ [i + 1, i + 1 + n_pacientes] for i in range(n_pacientes) ]

    print("Dicionário de dados formatado com sucesso.")

    return dados