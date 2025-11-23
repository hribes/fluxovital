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
        lat = "-22.208059052666716"
        lon = "-49.95410858756813"
        return lat, lon

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
import pandas as pd

def preparar_dados(df_veiculos, df_pacientes, dia_operacao, upa_address):
    """
    Prepara os dados para o OR-Tools e cria a lista de tradução (info_nos)
    para salvar no banco de dados com os IDs corretos.
    """
    print("Iniciando preparação dos dados...")
    dados = {}

    # ---------------------------------------------------------
    # 1. Configuração da Base (UPA/Garagem)
    # ---------------------------------------------------------
    # ID do endereço da UPA no seu banco de dados (Ajuste se não for 2)
    ID_BASE_DB = 1
    
    # Coordenadas fixas da UPA (Mais rápido que geocodificar toda vez)
    # Se quiser pegar do banco, precisaria vir numa query separada ou parâmetro
    upa_lat, upa_lon = -22.216300, -49.950300 
    
    dados['deposito_coords'] = (upa_lat, upa_lon)
    dados['deposito'] = 0
    
    # Inicia a lista de tradução (Nó 0 = Base)
    info_base = {
        'id_paciente': None, 
        'id_endereco': ID_BASE_DB, 
        'id_solicitacao': None,
        'tipo': 'BASE',
        'nome': 'Garagem Central'
    }

    # ---------------------------------------------------------
    # 2. Processar Veículos
    # ---------------------------------------------------------
    # Filtra apenas disponíveis (caso o SQL já não tenha feito)
    df_veiculos_disponiveis = df_veiculos[df_veiculos['ID_VEICULO'].notnull()].copy() # Ajuste conforme seu DF
    
    dados['num_veiculos'] = len(df_veiculos_disponiveis)
    dados['capacidade_veiculos'] = df_veiculos_disponiveis['CAPACIDADE'].tolist()
    
    # IMPORTANTE: Salva os IDs reais dos veículos para usar no save
    dados['ids_veiculos_reais'] = df_veiculos_disponiveis['ID_VEICULO'].tolist()

    print(f"Veículos disponíveis: {dados['num_veiculos']}")

    # ---------------------------------------------------------
    # 3. Processar Pacientes (Usando coordenadas do SQL)
    # ---------------------------------------------------------
    # O SQL já filtra a data, mas mantivemos a conversão por segurança
    if df_pacientes is None or df_pacientes.empty:
        print("Nenhum paciente encontrado.")
        return None

    coletas_coords = []
    entregas_coords = []
    coletas_demandas = []
    entregas_demandas = []
    
    # Listas temporárias para as informações de banco
    info_coletas = []
    info_entregas = []

    print(f"Processando {len(df_pacientes)} solicitações...")

    for index, row in df_pacientes.iterrows():
        # --- A. COLETA (Origem) ---
        # Pega Lat/Lon direto do banco (muito mais rápido que geocodificar)
        try:
            lat_c = float(row['LAT_COLETA'])
            lon_c = float(row['LON_COLETA'])
            lat_e = float(row['LAT_ENTREGA'])
            lon_e = float(row['LON_ENTREGA'])
        except (ValueError, TypeError):
            print(f"ERRO: Coordenadas inválidas para solicitação {row['ID_SOLICITACAO_CONSULTA']}")
            continue

        coletas_coords.append((lat_c, lon_c))
        
        # Cria o dicionário com IDs para o banco
        info_coletas.append({
            'id_paciente': int(row['ID_PACIENTE']),
            'id_endereco': int(row['ID_END_COLETA']),     # ID DA CASA
            'id_solicitacao': int(row['ID_SOLICITACAO_CONSULTA']),
            'tipo': 'COLETA',
            'nome': row['NOME_PACIENTE']
        })

        # --- B. ENTREGA (Destino) ---
        entregas_coords.append((lat_e, lon_e))
        
        info_entregas.append({
            'id_paciente': int(row['ID_PACIENTE']),
            'id_endereco': int(row['ID_END_ENTREGA']),    # ID DO HOSPITAL
            'id_solicitacao': int(row['ID_SOLICITACAO_CONSULTA']),
            'tipo': 'ENTREGA',
            'nome': 'Destino Saúde' # Ou row['NOME_LOCAL_ATENDIMENTO'] se tiver no DF
        })

        # Demanda (Lógica original mantida)
        demanda = 2 if row['ACOMPANHANTE'] else 1
        coletas_demandas.append(demanda)
        entregas_demandas.append(-demanda)

    # ---------------------------------------------------------
    # 4. Montagem Final
    # ---------------------------------------------------------
    # A ordem PRECISA ser: [Base] + [Todas Coletas] + [Todas Entregas]
    
    dados['coordenadas'] = [dados['deposito_coords']] + coletas_coords + entregas_coords
    dados['demanda_assentos'] = [0] + coletas_demandas + entregas_demandas
    
    # Monta a lista INFO_NOS na mesma ordem exata das coordenadas
    dados['info_nos'] = [info_base] + info_coletas + info_entregas
    
    # Configura pares Pickup & Delivery
    n_pacientes = len(coletas_coords)
    dados['coletas_entregas'] = [ [i + 1, i + 1 + n_pacientes] for i in range(n_pacientes) ]

    print("Dicionário de dados formatado com sucesso (IDs incluídos).")
    return dados