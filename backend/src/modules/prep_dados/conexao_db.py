import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

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
        print("Conexão com o banco de dados MySQL bem-sucedida!")
    except Error as e:
        print(f"O erro '{e}' ocorreu")

    return conexao

def ler_query_de_arquivo(caminho_arquivo):
    """Lê o conteúdo de um arquivo SQL e o retorna como uma string."""
    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        query = arquivo.read()
    return query

