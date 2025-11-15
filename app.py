import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector import Error
import json

# Importa as funções do 'conexao_db.py'
try:
    from conexao_db import criar_conexao, ler_query_de_arquivo, executar_query_escrita
except ImportError:
    print("ERRO: 'conexao_db.py' não encontrado ou faltando a função 'executar_query_escrita'.")
    print("Verifique se o 'conexao_db.py' está na mesma pasta do 'app.py' e se tem as três funções.")
    exit()

app = Flask(__name__)

# --- CORREÇÃO DO CORS ---
# Permite explicitamente que o seu "Live Server" (porta 5500)
# faça requisições para o seu backend (porta 5000).
cors = CORS(app, origins="http://127.0.0.1:5500")
# --- FIM DA CORREÇÃO ---


# --- Função de Execução de LEITURA (SELECT) ---
def executar_query(query, params=None):
    """
    Executa uma query de LEITURA (SELECT) no banco de dados 
    e retorna os resultados como uma lista de dicionários.
    """
    conexao = None
    cursor = None
    resultados = []
    try:
        conexao = criar_conexao() 
        if conexao is None:
            print("Falha ao criar conexão com o banco.")
            return None
        cursor = conexao.cursor(dictionary=True)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        resultados = cursor.fetchall()
    except Error as e:
        print(f"O erro '{e}' ocorreu ao executar a query de leitura")
        return None
    finally:
        if cursor:
            cursor.close()
        if conexao and conexao.is_connected():
            conexao.close()
    return resultados

# --- ROTA 1: Página de Consulta (GET Agendamentos) ---
@app.route('/api/agendamentos', methods=['GET'])
def get_agendamentos():
    try:
        pagina = int(request.args.get('pagina', 1))
        if pagina < 1: pagina = 1
    except ValueError:
        pagina = 1
    
    limite = 30
    offset = (pagina - 1) * limite
    
    data = request.args.get('data')
    status = request.args.get('status')
    local = request.args.get('local')
    veiculo = request.args.get('veiculo') 
    consulta = request.args.get('consulta')

    # Caminho para a query (assumindo que 'app.py' está na raiz 'fluxovital/')
    query_path = os.path.join('backend', 'src', 'modules', 'queries', 'get_agendamentos.sql')
    base_query = ler_query_de_arquivo(query_path)
    
    if not base_query:
        print(f"ERRO: Não foi possível ler o arquivo de query em: {query_path}")
        return jsonify({"erro": "Falha interna: Arquivo SQL 'get_agendamentos.sql' não encontrado."}), 500

    params = []
    where_conditions = []

    if data:
        where_conditions.append("DATE(sc.DATA_HORA_CONSULTA) = %s")
        params.append(data)
    # Filtra pelo NOME do status (Pendente/Concluido)
    if status and status != '1':
        where_conditions.append("sg.NOME_STATUS = %s")
        params.append(status)
    if local and local != '1':
        where_conditions.append("sc.ID_LOCAL_ATENDIMENTO = %s")
        params.append(local)
    if veiculo and veiculo != '1':
        where_conditions.append("tv.ID_TIPO_VEICULO = %s") 
        params.append(veiculo)
    if consulta and consulta != '1':
        where_conditions.append("sc.ID_TIPO_CONSULTA = %s")
        params.append(consulta)

    final_query = base_query
    if where_conditions:
        final_query += " WHERE " + " AND ".join(where_conditions)
    
    final_query += " ORDER BY sc.DATA_HORA_CONSULTA DESC LIMIT %s OFFSET %s;"
    params.extend([limite, offset]) # Adiciona paginação

    try:
        resultados = executar_query(final_query, tuple(params))
        if resultados is None:
            return jsonify({"erro": "Falha ao conectar ou buscar dados"}), 500
        return jsonify(resultados)
    except Exception as e:
        print(f"Erro no endpoint /api/agendamentos: {e}")
        return jsonify({"erro": str(e)}), 500

# --- ROTAS 2: Filtros da Página de Consulta (Reusadas pelo Cadastro) ---

@app.route('/api/filtros/locais', methods=['GET'])
def get_filtros_locais():
    """ Busca todos os locais de atendimento """
    query = "SELECT ID_LOCAL_ATENDIMENTO, NOME_LOCAL_ATENDIMENTO FROM LocalAtendimento ORDER BY NOME_LOCAL_ATENDIMENTO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar locais"}), 500
    return jsonify(resultados)

@app.route('/api/filtros/tiposveiculo', methods=['GET'])
def get_filtros_tipos_veiculo():
    """ Busca todos os tipos de veículo """
    query = "SELECT ID_TIPO_VEICULO, NOME_TIPO_VEICULO FROM TipoVeiculo ORDER BY NOME_TIPO_VEICULO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de veículo"}), 500
    return jsonify(resultados)

@app.route('/api/filtros/tiposconsulta', methods=['GET'])
def get_filtros_tipos_consulta():
    """ Busca todos os tipos de consulta (necessário para o cadastro_consulta.html) """
    query = "SELECT ID_TIPO_CONSULTA, DESCRICO_CONSULTA FROM TipoConsulta ORDER BY DESCRICO_CONSULTA;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de consulta"}), 500
    return jsonify(resultados)

# --- ROTAS 3: Página de Cadastro (GET Pacientes) ---

@app.route('/api/pacientes', methods=['GET'])
def get_pacientes():
    """ Busca todos os pacientes (ID, Nome, EnderecoID) para o formulário de cadastro """
    query = "SELECT ID_PACIENTE, NOME_PACIENTE, ID_ENDERECO FROM Paciente ORDER BY NOME_PACIENTE;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar pacientes"}), 500
    return jsonify(resultados)

# --- ROTA 4: Página de Cadastro (POST Consulta) ---

@app.route('/api/consultas', methods=['POST'])
def criar_consulta():
    """ Cria uma nova SolicitacaoConsulta no banco """
    dados = request.get_json()
    try:
        id_paciente = dados.get('id_paciente')
        id_tipo_consulta = dados.get('id_tipo_consulta')
        id_local_atendimento = dados.get('id_local_atendimento')
        id_endereco_paciente = dados.get('id_endereco_paciente')
        
        id_status_pendente = 5 # ID 5 = 'Pendente' (baseado nos seus INSERTS)
        
        data_hora_consulta = dados.get('data_hora_consulta')
        data_hora_ida = dados.get('data_hora_ida')
        data_hora_retorno = dados.get('data_hora_retorno') or None # Aceita nulo
        
        # Converte booleano de string 'true'/'false' para 1/0
        acompanhante = 1 if dados.get('acompanhante') == 'true' else 0
        maca = 1 if dados.get('maca') == 'true' else 0
        
        info_adicionais = dados.get('info_adicionais') or None

        query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'insert_consulta.sql'))
        if not query:
             return jsonify({"erro": "Falha interna: Arquivo SQL 'insert_consulta.sql' não encontrado."}), 500

        params = (
            id_paciente, id_tipo_consulta, id_endereco_paciente, id_local_atendimento,
            id_status_pendente, data_hora_ida, data_hora_retorno, data_hora_consulta,
            acompanhante, maca, info_adicionais
        )
        
        # Usa a função de ESCRITA importada do conexao_db.py
        sucesso = executar_query_escrita(query, params)
        
        if not sucesso:
            return jsonify({"erro": "Falha ao inserir dados no banco"}), 500

        return jsonify({"sucesso": True, "mensagem": "Consulta cadastrada!"}), 201

    except Exception as e:
        print(f"Erro no endpoint /api/consultas: {e}")
        return jsonify({"erro": str(e)}), 500

# --- Bloco de Execução ---
if __name__ == '__main__':
    print("Iniciando servidor Flask (versão completa com CORS corrigido)...")
    app.run(debug=True, port=5000)