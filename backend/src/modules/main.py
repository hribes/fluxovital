import os
from dotenv import load_dotenv
from pprint import pprint
from prep_dados.busca_bd import buscar_dados
from prep_dados.funcoes_preparacao_dados import preparar_dados
from matriz.matriz_distancias import construir_matriz_tempo_distancia, desenhar_mapa_localizacoes

# --- Configurações ---
load_dotenv()

# Chave para o OpenRouteService (usada para matrizes)
# (A GOOGLE_API_KEY é carregada dentro de 'funcoes_preparacao_dados.py')
ORS_API_KEY = os.getenv("ORS_API_KEY") 

UPA_ENDERECO = "Av. Sampaio Vidal, 200, Marília, SP, 17500-022" # Endereço da Garagem
DIA_OPERACAO = '2025-10-08' # O dia que você quer otimizar

def executar_fluxo_completo(data_para_filtro):
    """
    Executa o fluxo completo:
    1. Busca dados no banco.
    2. Prepara e geocodifica os dados.
    3. Constrói a matriz de tempo/distância.
    4. Salva um mapa com os pontos.
    """

    if not ORS_API_KEY:
        print("Erro: ORS_API_KEY não definida no arquivo .env. Necessária para a matriz.")
        return

    # --- 1. Buscar Dados ---
    print("--- ETAPA 1: BUSCANDO DADOS DO BANCO ---")
    df_pacientes, df_veiculos = buscar_dados(data_para_filtro)

    if df_pacientes is None or df_veiculos is None:
        print("Falha ao buscar dados do banco. Encerrando.")
        return

    print("\nDados de pacientes e veículos carregados.")

    # --- 2. Preparar Dados ---
    try:
        print("\n--- ETAPA 2: PREPARANDO E GEOCODIFICANDO DADOS ---")
        dados_prontos = preparar_dados(df_veiculos, df_pacientes, DIA_OPERACAO, UPA_ENDERECO)

        if dados_prontos is None:
            print("Não há pacientes para processar. Encerrando.")
            return

    except Exception as e:
        print(f"\nOcorreu um erro na preparação dos dados: {e}")
        return

    # --- 3. Construir Matriz (A JUNÇÃO QUE VOCÊ QUERIA) ---
    print("\n--- ETAPA 3: CONSTRUINDO MATRIZ DE DISTÂNCIA/TEMPO ---")
    dados_com_matriz = construir_matriz_tempo_distancia(dados_prontos, ORS_API_KEY)

    if dados_com_matriz is None:
        print("Falha ao construir as matrizes. Encerrando.")
        return

    # --- 4. Visualizar Resultados e Mapa ---
    print("\n--- ETAPA 4: DADOS FINAIS PRONTOS PARA O SOLVER ---")
    # Imprime as chaves principais (sem a matriz gigante)
    chaves_para_mostrar = {k: v for k, v in dados_com_matriz.items() if 'matriz' not in k}
    pprint(chaves_para_mostrar)
    print(f"Matriz de tempo (shape): {len(dados_com_matriz['matriz_tempo'])}x{len(dados_com_matriz['matriz_tempo'][0])}")
    print(f"Matriz de distância (shape): {len(dados_com_matriz['matriz_distancia'])}x{len(dados_com_matriz['matriz_distancia'][0])}")

    desenhar_mapa_localizacoes(dados_com_matriz, "mapa_localizacoes_final.html")

    print("\n--- PRÓXIMOS PASSOS ---")
    print("O dicionário 'dados_com_matriz' está pronto.")
    print("Chame sua função de otimização: resolver_pdptw(dados_com_matriz)")


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    data_para_filtro = '2025-10-08' #ADicionar a Data do filtro
    executar_fluxo_completo(data_para_filtro)