from datetime import datetime
from pprint import pprint # Para imprimir o dicionário de forma bonita
from funcoes_preparacao_dados import preparar_dados
from busca_bd import buscar_dados
import os


API_KEY = os.getenv('API_KEY') # Substitua pela sua chave do OpenRouteService
UPA_ENDERECO = "Av. Sampaio Vidal, 200, Marília, SP, 17500-022" # Endereço da Garagem
DIA_OPERACAO = os.getenv('DATA_SOLVER') # O dia que você quer otimizar

# 2. Simulação dos seus dados (copie e cole seus dados reais aqui)
# Usei io.StringIO para simular a leitura dos seus dados de texto
# veiculos_csv = """
# ID_VEICULO;NOME_TIPO_VEICULO;MACA;CAPACIDADE;NOME_STATUS
# 1;Ambulância;1;2;Disponível
# 2;Van Adaptada;1;8;Disponível
# 3;Carro de Passeio;0;4;Disponível
# 4.Micro-ônibus;0;15;Em Manutenção
# """

#pacientes_csv = """
#ID_PACIENTE;DATA_HORA_CONSULTA;DATA_HORA_MAX_CHEGADA;ACOMPANHANTE;MACA;NOME_RUA;NUMERO_ENDERECO;NOME_BAIRRO;NOME_CIDADE;CEP;NOME_LOCAL_ATENDIMENTO;NOME_RUA_LOCALATENDIMENTO;NUMERO_ENDERECO_LOCALATENDIMENTO;NOME_BAIRRO_LOCALATENDIMENTO;NOME_CIDADE_LOCALATENDIMENTO;CEP_LOCALATENDIMENTO
# 1;2025-10-08 10:00:00;2025-10-08 09:40:00;0;0;Rua Teodoro Sampaio;1100;Pinheiros;São Paulo;05406100;Hospital das Clínicas;Av. Dr. Enéas Carvalho de Aguiar;255;Cerqueira César;São Paulo;05403000
# 4;2025-10-08 16:00:00;2025-10-08 15:40:00;1;1;Rua Bahia;500;Centro;Marília;17501010;Santa Casa de Marília;Av. Vicente Ferreira;100;Cascata;Marília;17515900
# 2;2025-10-09 14:00:00;2025-10-09 13:40:00;0;0;Rua Barata Ribeiro;700;Copacabana;Rio de Janeiro;22051001;Copa D'Or;Rua Figueiredo de Magalhães;875;Copacabana;Rio de Janeiro;22031011
# 3;2025-10-10 08:00:00;2025-10-10 07:40:00;1;0;Rua Alagoas;1000;Savassi;Belo Horizonte;30130160;Hospital da Baleia;Rua Juramento;1464;Saudade;Belo Horizonte;30285000
# """

# Carrega os dados em DataFrames
#df_veiculos = pd.read_csv(io.StringIO(veiculos_csv), sep=';')
#df_pacientes = pd.read_csv(io.StringIO(pacientes_csv), sep=';')

df_pacientes, df_veiculos = buscar_dados()
print(df_pacientes)
print(df_veiculos)

# 3. Executar a função de preparação
try:
    dados_prontos = preparar_dados(df_veiculos, df_pacientes, DIA_OPERACAO, UPA_ENDERECO, API_KEY)
    
    if dados_prontos:
        print("\n--- DADOS PRONTOS PARA O OTIMIZADOR ---")
        pprint(dados_prontos)
        
        # PRÓXIMOS PASSOS:
        # 1. Chamar a função construir_matriz_tempo(dados_prontos)
        # 2. Chamar a função resolver_pdptw(dados_prontos)
        
except Exception as e:
    print(f"\nOcorreu um erro: {e}")