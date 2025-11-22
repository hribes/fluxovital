import os
from dotenv import load_dotenv
import pandas as pd
from conexao_db import criar_conexao, ler_query_de_arquivo

def buscar_dados(data_para_filtro):
    load_dotenv()
    print("Tentando criar conexão...")
    conexao = criar_conexao()
    df_solicitacao_consulta = None
    df_veiculo = None

    # --- Ponto de verificação da conexão ---
    if conexao is None:
        print("Erro: Conexão retornou None.")
        return None, None 

    if not conexao.is_connected():
        print("Erro: A conexão foi criada, mas não está conectada.")
        return None, None 
 
    print("Conexão bem-sucedida. Executando queries...")

    try: 
        cursor = conexao.cursor()

        # ---------------------------------------
        # --- Query 1: Solicitação Consultas ---
        # ---------------------------------------
        caminho_do_arquivo_sql_1 = os.getenv("CAMINHO_SQL_SOLICITACAOCONSULTAS")
        if not caminho_do_arquivo_sql_1:
            print("Erro: Variável CAMINHO_SQL_SOLICITACAOCONSULTAS não definida.")
            return None, None

        print(f"Lendo query de: {caminho_do_arquivo_sql_1}")
        query_solicitacao_consulta = ler_query_de_arquivo(caminho_do_arquivo_sql_1)

        print(f"Executando query de Consultas para a data: {data_para_filtro}")
        
        # CORREÇÃO: Passar a tupla de parâmetros (note a vírgula após data_para_filtro)
        cursor.execute(query_solicitacao_consulta, (data_para_filtro,))
        
        resultados_query_solicitacao = cursor.fetchall()

        if resultados_query_solicitacao:
            colunas_solicitacao = [i[0] for i in cursor.description]
            df_solicitacao_consulta = pd.DataFrame(resultados_query_solicitacao, columns=colunas_solicitacao)
            print(f"Query Consultas retornou {len(df_solicitacao_consulta)} linhas.")
        else:
            print("A consulta de CONSULTAS não retornou resultados.")

        # --------------------------
        # --- Query 2: Veículos ---
        # --------------------------
        caminho_do_arquivo_sql_2 = os.getenv("CAMINHO_SQL_VEICULOS")
        if not caminho_do_arquivo_sql_2:
            print("Erro: Variável CAMINHO_SQL_VEICULOS não definida.")
            # Retorna o que já conseguimos pegar
            return df_solicitacao_consulta, None 

        print(f"Lendo query de: {caminho_do_arquivo_sql_2}")
        query_veiculo = ler_query_de_arquivo(caminho_do_arquivo_sql_2)

        print(f"Executando query de Veículos...")
        
        # CORREÇÃO: Executar a variável query_veiculo, não a query_solicitacao_consulta novamente
        # Assumindo que a query de veículos NÃO precisa de filtro de data. 
        # Se precisar, adicione o parâmetro: cursor.execute(query_veiculo, (data_para_filtro,))
        cursor.execute(query_veiculo) 
        
        resultados_query_veiculo = cursor.fetchall()

        if resultados_query_veiculo:
            colunas_veiculo = [i[0] for i in cursor.description]
            df_veiculo = pd.DataFrame(resultados_query_veiculo, columns=colunas_veiculo)
            print(f"Query Veículos retornou {len(df_veiculo)} linhas.")
        else:
            print("A consulta de VEÍCULOS não retornou resultados.")

        cursor.close()

    except Exception as e:
        print(f"Ocorreu um erro durante a execução das queries: {e}")
        # Retorna o que tiver conseguido até o momento do erro
        return df_solicitacao_consulta, df_veiculo

    finally:
        if conexao.is_connected():
            conexao.close()
            print("A conexão com o MySQL foi fechada.")

    return df_solicitacao_consulta, df_veiculo