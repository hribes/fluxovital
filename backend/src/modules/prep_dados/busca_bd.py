import os
from dotenv import load_dotenv
import pandas as pd
from prep_dados.conexao_db import criar_conexao, ler_query_de_arquivo

def buscar_dados():
    load_dotenv()
    print("Tentando criar conexão...")
    conexao = criar_conexao()
    df_solicitacao_consulta = None
    df_veiculo = None

    # --- Ponto de verificação da conexão ---
    if conexao is None:
        print("Erro: A função criar_conexao() retornou None. Verifique suas variáveis de ambiente (.env) e se o banco está online.")
        return None, None 

    if not conexao.is_connected():
        print("Erro: A conexão foi criada, mas não está conectada.")
        return None, None 
 
    print("Conexão bem-sucedida. Executando queries...")

    try: 
        cursor = conexao.cursor()

        # --- Query 1: Solicitação Consultas ---
        caminho_do_arquivo_sql_1 = os.getenv("CAMINHO_SQL_SOLICITACAOCONSULTAS")
        if not caminho_do_arquivo_sql_1:
            print("Erro: Variável de ambiente CAMINHO_SQL_SOLICITACAOCONSULTAS não encontrada no .env")
            return None, None

        print(f"Lendo query de: {caminho_do_arquivo_sql_1}")
        query_solicitacao_consulta = ler_query_de_arquivo(caminho_do_arquivo_sql_1)

        cursor.execute(query_solicitacao_consulta)
        resultados_query_solicitacao_consulta = cursor.fetchall()

        if resultados_query_solicitacao_consulta:
            nomes_colunas = [i[0] for i in cursor.description]
            df_solicitacao_consulta = pd.DataFrame(resultados_query_solicitacao_consulta, columns=nomes_colunas)
            print(f"Query 1 retornou {len(df_solicitacao_consulta)} linhas.")
        else:
            print("A consulta 1 (SOLICITACAOCONSULTAS) não retornou resultados.")

            # --- Query 2: Veículos ---
        caminho_do_arquivo_sql_2 = os.getenv("CAMINHO_SQL_VEICULOS")
        if not caminho_do_arquivo_sql_2:
            print("Erro: Variável de ambiente CAMINHO_SQL_VEICULOS não encontrada no .env")
            return df_solicitacao_consulta, None 

        print(f"Lendo query de: {caminho_do_arquivo_sql_2}")
        query_veiculo = ler_query_de_arquivo(caminho_do_arquivo_sql_2)

        cursor.execute(query_veiculo)
        resultados_query_veiculo = cursor.fetchall()

        if resultados_query_veiculo:
            nomes_colunas = [i[0] for i in cursor.description]
            df_veiculo = pd.DataFrame(resultados_query_veiculo, columns=nomes_colunas)
            print(f"Query 2 retornou {len(df_veiculo)} linhas.")
        else:
            print("A consulta 2 (VEICULOS) não retornou resultados.")

        cursor.close()

    except Exception as e:
        print(f"Ocorreu um erro durante a execução das queries: {e}")
        return df_solicitacao_consulta, df_veiculo

    finally:
        if conexao.is_connected():
            conexao.close()
            print("A conexão com o MySQL foi fechada.")

    return df_solicitacao_consulta, df_veiculo

# --- Exemplo de como chamar (agora no main.py) ---
# if __name__ == "__main__":
#     df_solicitacao, df_veiculo_retornado = buscar_dados()
#     if df_solicitacao is not None:
#         print("\n--- Resultados da Solicitação ---")
#         print(df_solicitacao.head())
#     if df_veiculo_retornado is not None:
#         print("\n--- Resultados do Veículo ---")
#         print(df_veiculo_retornado.head())