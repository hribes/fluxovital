import pandas as pd
import openrouteservice
from datetime import datetime
import requests
from dotenv import load_dotenv
import os

# Carrega a chave do arquivo .env
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Funções Auxiliares --
    

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

def to_seconds_since_midnight(timestamp_str):
    """
    Converte uma string de data/hora (ex: '2025-10-08 10:00:00') 
    em segundos desde a meia-noite do mesmo dia.
    """
    if pd.isna(timestamp_str):
        return 0
    
    # Converte a string para um objeto datetime
    dt_object = pd.to_datetime(timestamp_str)
    
    # Extrai o objeto time
    time_object = dt_object.time()
    
    # Calcula o total de segundos
    return time_object.hour * 3600 + time_object.minute * 60 + time_object.second

# --- Função Principal de Preparação ---

def preparar_dados(df_veiculos, df_pacientes, dia_operacao, upa_address, ors_api_key):
    """
    Transforma os DataFrames de veículos e pacientes no dicionário de dados
    formatado para o solver OR-Tools (PDPTW).
    """
    
    print("Iniciando preparação dos dados...")
    dados = {}
    
    # 1. Inicializar o cliente OpenRouteService
    client = openrouteservice.Client(key=ors_api_key)

    # 2. Geocodificar o Depósito (UPA)
    upa_coords = endereco_para_coordenadas(upa_address)
    if not upa_coords[0]:
        raise ValueError(f"Não foi possível encontrar as coordenadas da UPA: {upa_address}")
    
    dados['deposito_coords'] = upa_coords
    dados['deposito'] = 0
    print(f"Coordenadas da UPA ({upa_address}): {upa_coords}")

    # 3. Processar Veículos
    # Filtra apenas veículos "Disponível"
    df_veiculos_disponiveis = df_veiculos[df_veiculos['NOME_STATUS'] == 'Disponível'].copy()
    
    dados['num_veiculos'] = len(df_veiculos_disponiveis)
    dados['capacidade_veiculos'] = df_veiculos_disponiveis['CAPACIDADE'].tolist()
    # Converte 0/1 para False/True
    dados['veiculo_tem_maca'] = df_veiculos_disponiveis['MACA'].astype(bool).tolist()

    print(f"Veículos disponíveis: {dados['num_veiculos']}")
    print(f"Capacidades: {dados['capacidade_veiculos']}")
    print(f"Maca disponível: {dados['veiculo_tem_maca']}")

    # 4. Processar Pacientes (o passo mais complexo)
    
    # Converte a coluna para datetime para poder filtrar pela data
    df_pacientes['DATA_HORA_CONSULTA'] = pd.to_datetime(df_pacientes['DATA_HORA_CONSULTA'])
    
    # Filtra os pacientes apenas para o dia da operação
    df_pacientes_hoje = df_pacientes[df_pacientes['DATA_HORA_CONSULTA'].dt.date == pd.to_datetime(dia_operacao).date()].copy()
    print(f"Total de pacientes para {dia_operacao}: {len(df_pacientes_hoje)}")
    
    if len(df_pacientes_hoje) == 0:
        print("Nenhum paciente para o dia selecionado. Encerrando.")
        return None

    # Listas temporárias para armazenar os dados na ordem correta
    coletas_coords = []
    entregas_coords = []
    coletas_demandas = []
    entregas_demandas = []
    coletas_maca = []
    entregas_maca = []
    entregas_janelas = []
    
    print("Iniciando geocodificação dos pacientes...")
    for _, paciente in df_pacientes_hoje.iterrows():
        
        # --- Endereços ---
        # Monta o endereço de COLETA (Casa)
        addr_coleta = (
            f"{paciente['NOME_RUA']}, {paciente['NUMERO_ENDERECO']}, "
            f"{paciente['NOME_BAIRRO']}, {paciente['NOME_CIDADE']}, {paciente['CEP']}"
        )
        # Monta o endereço de ENTREGA (Clínica)
        addr_entrega = (
            f"{paciente['NOME_RUA_LOCALATENDIMENTO']}, {paciente['NUMERO_ENDERECO_LOCALATENDIMENTO']}, "
            f"{paciente['NOME_BAIRRO_LOCALATENDIMENTO']}, {paciente['NOME_CIDADE_LOCALATENDIMENTO']}, {paciente['CEP_LOCALATENDIMENTO']}"
        )
        
        # Geocodifica
        coord_coleta = endereco_para_coordenadas(addr_coleta)
        coord_entrega = endereco_para_coordenadas(addr_entrega)

        # Se não encontrar coordenadas, pula este paciente
        if not coord_coleta[0] or not coord_entrega[0]:
            print(f"Pulando Paciente ID {paciente['ID_PACIENTE']} por falha na geocodificação.")
            continue
            
        coletas_coords.append(coord_coleta)
        entregas_coords.append(coord_entrega)

        # --- Demanda ---
        # 1 (paciente) + 1 (se tiver acompanhante)
        demanda = 2 if paciente['ACOMPANHANTE'] else 1
        coletas_demandas.append(demanda)
        entregas_demandas.append(-demanda) # Demanda negativa na entrega

        # --- Maca ---
        maca = bool(paciente['MACA'])
        coletas_maca.append(maca)
        entregas_maca.append(maca)

        # --- Janelas de Tempo (em segundos) ---
        t_max_chegada = to_seconds_since_midnight(paciente['DATA_HORA_MAX_CHEGADA'])
        t_consulta = to_seconds_since_midnight(paciente['DATA_HORA_CONSULTA'])
        
        # Garante que a janela seja válida (ex: [34800, 36000])
        entregas_janelas.append((min(t_max_chegada, t_consulta), max(t_max_chegada, t_consulta)))

    print("Geocodificação concluída.")

    # 5. Montar o Dicionário 'dados' Final (na ordem UPA -> Coletas -> Entregas)
    
    # Coordenadas: [UPA, ...Coletas..., ...Entregas...]
    dados['coordenadas'] = [dados['deposito_coords']] + coletas_coords + entregas_coords
    
    # Demandas: [0, ...Demandas Coleta..., ...Demandas Entrega...]
    dados['demanda_assentos'] = [0] + coletas_demandas + entregas_demandas
    
    # Necessidade de Maca
    dados['necessidade_maca'] = [False] + coletas_maca + entregas_maca

    # Janelas de Tempo: [Janela UPA, ...Janelas Coleta (abertas)..., ...Janelas Entrega (restritas)...]
    janela_aberta = (0, 86400) # Janela de 24h
    coletas_janelas = [janela_aberta] * len(coletas_coords)
    dados['janelas_tempo'] = [janela_aberta] + coletas_janelas + entregas_janelas
    
    # Pares de Coleta e Entrega
    n_pacientes = len(coletas_coords)
    # Índices: Coleta 1 está em [1], Entrega 1 está em [1 + n_pacientes]
    #           Coleta 2 está em [2], Entrega 2 está em [2 + n_pacientes] ...
    dados['coletas_entregas'] = [ [i + 1, i + 1 + n_pacientes] for i in range(n_pacientes) ]
    
    print("Dicionário de dados formatado com sucesso.")
    
    return dados
