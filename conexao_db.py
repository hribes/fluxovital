import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# 1. Carrega as variáveis de ambiente.
#    Como o 'app.py' está na raiz (junto com o .env),
#    o load_dotenv() vai encontrar o arquivo corretamente.
load_dotenv()

def criar_conexao():
    """ Cria uma conexão com o banco de dados MySQL """
    
    conexao = None
    try:
        conexao = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        # Removido o print de "sucesso" para não poluir o terminal
    except Error as e:
        print(f"O erro '{e}' ocorreu ao tentar conectar no banco")

    return conexao

def ler_query_de_arquivo(caminho_completo_arquivo):
    """
    Lê o conteúdo de um arquivo SQL e o retorna como uma string.
    Recebe o 'caminho_completo_arquivo' direto do app.py
    """
    try:
        with open(caminho_completo_arquivo, 'r', encoding='utf-8') as arquivo:
            query = arquivo.read()
        return query
    except FileNotFoundError:
        print("="*50)
        print(f"ERRO DE ARQUIVO: Arquivo SQL não encontrado.")
        print(f"Tentamos buscar em: {caminho_completo_arquivo}")
        print("Verifique se o caminho no app.py está correto.")
        print("="*50)
        return None
    except Exception as e:
        print(f"Erro ao ler arquivo SQL: {e}")
        return None


def executar_query_escrita(query, params=None):
    """
    Executa uma query de ESCRITA (INSERT, UPDATE, DELETE)
    e faz o 'commit' da transação.
    Retorna True em sucesso, False em falha.
    """
    conexao = None
    cursor = None
    
    try:
        conexao = criar_conexao()
        if conexao is None:
            return False
            
        cursor = conexao.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        conexao.commit() # Confirma a transação
        return True
        
    except Error as e:
        print(f"O erro '{e}' ocorreu ao executar a query de escrita")
        return False
    finally:
        if cursor:
            cursor.close()
        if conexao and conexao.is_connected():
            conexao.close()