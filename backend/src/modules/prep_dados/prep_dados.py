import pandas as pd
from conexao_db import criar_conexao, ler_query_de_arquivo

conexao = criar_conexao()
df_solicitacao_consulta = None
df_veiculo = None

if conexao is not None and conexao.is_connected():
    cursor = conexao.cursor()
    
    # Busca da Data e hora da chegada e também dos endereços de busca e entrega
    caminho_do_arquivo_sql_1 = r"C:\Users\heloi\OneDrive\Desktop\projeto-FluxoVital\backend\src\modules\queries\solicitacao_consulta.sql"
    query_solicitacao_consulta = ler_query_de_arquivo(caminho_do_arquivo_sql_1)
    
    cursor.execute(query_solicitacao_consulta)
    resultados_query_solicitacao_consulta = cursor.fetchall()
    
    if resultados_query_solicitacao_consulta:
        nomes_colunas = [i[0] for i in cursor.description]
        df_solicitacao_consulta = pd.DataFrame(resultados_query_solicitacao_consulta, columns=nomes_colunas)
    else:
        print("A consulta não retornou resultados da resultados_query_solicitacao_consulta.")

    # 
    caminho_do_arquivo_sql_2 = r"C:\Users\heloi\OneDrive\Desktop\projeto-FluxoVital\backend\src\modules\queries\veiculos.sql"
    query_veiculo = ler_query_de_arquivo(caminho_do_arquivo_sql_2)
    
    cursor.execute(query_veiculo)
    resultados_query_veiculo = cursor.fetchall()
    
    if resultados_query_veiculo:
        nomes_colunas = [i[0] for i in cursor.description]
        df_veiculo = pd.DataFrame(resultados_query_veiculo, columns=nomes_colunas)
    else:
        print("A consulta não retornou resultados da resultados_query_veiculo.")
    
    cursor.close()
    conexao.close()
    print("A conexão com o MySQL foi fechada.")
    
print(df_solicitacao_consulta)
print(df_veiculo)