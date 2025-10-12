import mysql.connector
from mysql.connector import Error

def criar_conexao():
    """ Cria uma conexão com o banco de dados MySQL """
    meu_host = "localhost"
    meu_usuario = "root"
    minha_senha = "Fec43867614."
    meu_banco_de_dados = "fluxovital"
    
    conexao = None
    try:
        conexao = mysql.connector.connect(
            host=meu_host,
            user=meu_usuario,
            password=minha_senha,
            database=meu_banco_de_dados
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

# --- INÍCIO DO PROGRAMA PRINCIPAL ---

conexao = criar_conexao()

# Exemplo de como usar a conexão (opcional)
if conexao is not None and conexao.is_connected():
    # Você pode criar um cursor para executar queries SQL
    cursor = conexao.cursor()
    cursor.execute("SELECT database();")
    record = cursor.fetchone()
    print("Você está conectado ao banco de dados: ", record)

    # Lembre-se de fechar a conexão e o cursor quando terminar
    cursor.close()
    conexao.close()
    print("A conexão com o MySQL foi fechada.")