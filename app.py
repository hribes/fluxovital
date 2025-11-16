import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector import Error
import json

# Importa as funções do 'conexao_db.py'
try:
    from conexao_db import criar_conexao, ler_query_de_arquivo, executar_query_escrita
    # Importa sua função de conversão (o .py deve estar na mesma pasta)
    from conversao_coordenadas import endereco_para_coordenadas
except ImportError as e:
    print(f"ERRO DE IMPORTAÇÃO: {e}")
    print("Verifique se 'conexao_db.py' e 'conversao_coordenadas.py' estão na mesma pasta do 'app.py'")
    exit()

# --- IMPORTAÇÕES PARA A ROTA DE CEP ---
import requests
import re # ⚡ NOVA IMPORTAÇÃO para limpar o CEP ⚡
API_KEY = os.getenv("GOOGLE_API_KEY") # Pega a chave para a nova rota de CEP
# --- FIM DAS IMPORTAÇÕES ---

app = Flask(__name__)

# --- CORREÇÃO DO CORS ---
cors = CORS(app, origins="http://127.0.0.1:5500")
# --- FIM DA CORREÇÃO ---


# --- Função de Execução de LEITURA (SELECT) ---
def executar_query(query, params=None):
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
    
    # --- FILTROS SIMPLIFICADOS ---
    data = request.args.get('data')
    status = request.args.get('status')
    local = request.args.get('local')

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
    
    if status and status != '1':
        where_conditions.append("sc.ID_STATUS = %s")
        params.append(status)

    if local and local != '1':
        where_conditions.append("sc.ID_LOCAL_ATENDIMENTO = %s")
        params.append(local)
    
    final_query = base_query
    if where_conditions:
        final_query += " WHERE " + " AND ".join(where_conditions)
    
    final_query += " ORDER BY sc.DATA_HORA_CONSULTA DESC LIMIT %s OFFSET %s;"
    params.extend([limite, offset]) 

    try:
        resultados = executar_query(final_query, tuple(params))
        if resultados is None:
            return jsonify({"erro": "Falha ao conectar ou buscar dados"}), 500
        return jsonify(resultados)
    except Exception as e:
        print(f"Erro no endpoint /api/agendamentos: {e}")
        return jsonify({"erro": str(e)}), 500

# --- ROTAS 2: Filtros (Reusadas pelo Cadastro) ---

@app.route('/api/filtros/locais', methods=['GET'])
def get_filtros_locais():
    query = "SELECT ID_LOCAL_ATENDIMENTO, NOME_LOCAL_ATENDIMENTO FROM LocalAtendimento ORDER BY NOME_LOCAL_ATENDIMENTO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar locais"}), 500
    return jsonify(resultados)

@app.route('/api/filtros/tiposveiculo', methods=['GET'])
def get_filtros_tipos_veiculo():
    query = "SELECT ID_TIPO_VEICULO, NOME_TIPO_VEICULO FROM TipoVeiculo ORDER BY NOME_TIPO_VEICULO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de veículo"}), 500
    return jsonify(resultados)

@app.route('/api/filtros/tiposconsulta', methods=['GET'])
def get_filtros_tipos_consulta():
    query = "SELECT ID_TIPO_CONSULTA, DESCRICO_CONSULTA FROM TipoConsulta ORDER BY DESCRICO_CONSULTA;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de consulta"}), 500
    return jsonify(resultados)

# --- ROTAS 3: Página de Cadastro (GET Pacientes) ---

@app.route('/api/pacientes', methods=['GET'])
def get_pacientes():
    query = "SELECT ID_PACIENTE, NOME_PACIENTE, ID_ENDERECO FROM Paciente ORDER BY NOME_PACIENTE;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar pacientes"}), 500
    return jsonify(resultados)

# --- ROTA 4: Página de Cadastro (POST Consulta) ---

@app.route('/api/consultas', methods=['POST'])
def criar_consulta():
    dados = request.get_json()
    try:
        id_paciente = dados.get('id_paciente')
        id_tipo_consulta = dados.get('id_tipo_consulta')
        id_local_atendimento = dados.get('id_local_atendimento')
        id_endereco_paciente = dados.get('id_endereco_paciente')
        id_status_pendente = 5 
        data_hora_consulta = dados.get('data_hora_consulta')
        data_hora_ida = dados.get('data_hora_ida')
        data_hora_retorno = dados.get('data_hora_retorno') or None 
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
        
        sucesso = executar_query_escrita(query, params)
        
        if not sucesso:
            return jsonify({"erro": "Falha ao inserir dados no banco"}), 500

        return jsonify({"sucesso": True, "mensagem": "Consulta cadastrada!"}), 201

    except Exception as e:
        print(f"Erro no endpoint /api/consultas: {e}")
        return jsonify({"erro": str(e)}), 500

# --- ROTA 5: Cadastro de Paciente (POST Paciente) ---
@app.route('/api/pacientes', methods=['POST'])
def criar_paciente():
    dados = request.get_json()
    
    # 1. Verificação de Duplicidade (CPF/Telefone)
    try:
        cpf_novo = dados.get('cpf')
        telefone_novo = dados.get('telefone')

        if not cpf_novo:
             return jsonify({"erro": "CPF é obrigatório."}), 400

        cpf_check_query = "SELECT 1 FROM Paciente WHERE CPF_PACIENTE = %s"
        cpf_result = executar_query(cpf_check_query, (cpf_novo,))
        if cpf_result:
            return jsonify({"erro": f"Erro: O CPF '{cpf_novo}' já está cadastrado."}), 409 

        if telefone_novo: 
            tel_check_query = "SELECT 1 FROM Paciente WHERE TELEFONE = %s"
            tel_result = executar_query(tel_check_query, (telefone_novo,))
            if tel_result:
                return jsonify({"erro": f"Erro: O Telefone '{telefone_novo}' já está cadastrado."}), 409
    
    except Exception as e:
        print(f"Erro durante a pré-verificação: {e}")
        return jsonify({"erro": "Erro ao verificar dados. Tente novamente."}), 500
    
    # 2. Continua para o cadastro...
    conexao = None
    cursor = None
    try:
        # Geocoding
        endereco_completo = (
            f"{dados.get('rua')}, {dados.get('numero')}, "
            f"{dados.get('bairro')}, {dados.get('cidade')}, "
            f"{dados.get('estado')}, Brasil"
        )
        print(f"Buscando coordenadas para: {endereco_completo}")
        lat, lon = endereco_para_coordenadas(endereco_completo)
        
        if lat is None or lon is None:
            return jsonify({"erro": "Endereço não encontrado ou inválido. Verifique os dados e tente novamente."}), 400

        # Transação do Banco
        conexao = criar_conexao()
        if not conexao:
            raise Exception("Falha ao conectar no banco de dados")
        
        conexao.autocommit = False 
        cursor = conexao.cursor()

        estado_uf_limpo = (dados.get('estado') or 'ER').upper()[:2]
        
        # --- ⚡ CORREÇÃO DO CEP ⚡ ---
        # Limpa o CEP de hífens (ex: 17500-021 -> 17500021)
        cep_bruto = dados.get('cep')
        cep_limpo = re.sub(r'\D', '', cep_bruto or '')
        # Garante que tenha 8 dígitos, se não, preenche com 0 (necessário para CHAR(8))
        cep_final = cep_limpo.ljust(8, '0')[:8] 
        
        
        cursor.execute("INSERT INTO Estado (NOME_ESTADO) VALUES (%s) ON DUPLICATE KEY UPDATE ID_ESTADO=LAST_INSERT_ID(ID_ESTADO)", (estado_uf_limpo,))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_estado = cursor.fetchone()[0]

        cursor.execute("INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_CIDADE=LAST_INSERT_ID(ID_CIDADE)", (id_estado, dados.get('cidade')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_cidade = cursor.fetchone()[0]

        cursor.execute("INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_BAIRRO=LAST_INSERT_ID(ID_BAIRRO)", (id_cidade, dados.get('bairro')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_bairro = cursor.fetchone()[0]

        # 2d. Rua (Usa o cep_final limpo)
        cursor.execute("INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE ID_RUA=LAST_INSERT_ID(ID_RUA)", 
                       (id_bairro, dados.get('rua'), cep_final))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_rua = cursor.fetchone()[0]
        
        cursor.execute("INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES (%s, %s, %s, %s, %s)",
                       (id_rua, dados.get('numero'), lat, lon, dados.get('complemento')))
        id_endereco = cursor.lastrowid
        
        # Criar o Paciente
        query_paciente = """
            INSERT INTO Paciente (ID_ENDERECO, SEXO, NOME_PACIENTE, CPF_PACIENTE, SENHA, DATA_NASCIMENTO, TELEFONE)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params_paciente = (
            id_endereco, 
            dados.get('sexo'), 
            dados.get('nome'), 
            dados.get('cpf'),
            dados.get('senha'), 
            dados.get('data_nascimento'), 
            dados.get('telefone')
        )
        cursor.execute(query_paciente, params_paciente)
        
        conexao.commit()
        
        return jsonify({"sucesso": True, "mensagem": "Paciente cadastrado com sucesso!"}), 201

    except Error as e:
        if conexao:
            conexao.rollback()
        print(f"Erro na transação de paciente (Erro DB): {e}")
        return jsonify({"erro": f"Erro de banco de dados: {e.msg}"}), 500
    except Exception as e:
        if conexao:
            conexao.rollback()
        print(f"Erro na transação de paciente (Erro App): {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexao:
            conexao.close()

# --- ROTA 6: Busca de Endereço por CEP ---
@app.route('/api/cep/<string:cep_number>', methods=['GET'])
def get_cep_data(cep_number):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": cep_number, "key": API_KEY, "region": "BR"}
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data["status"] == "OK":
            components = data["results"][0]["address_components"]
            
            def find_component(comp_list, comp_type, name_type='long_name'):
                for comp in comp_list:
                    if comp_type in comp["types"]:
                        return comp.get(name_type, "") 
                return ""

            rua = find_component(components, "route")
            bairro = find_component(components, "sublocality_level_1")
            cidade = find_component(components, "administrative_area_level_2")
            estado_uf = find_component(components, "administrative_area_level_1", 'short_name') 
            
            if not bairro:
                bairro = find_component(components, "sublocality")
            if not bairro: 
                bairro = find_component(components, "political")

            return jsonify({
                "rua": rua,
                "bairro": bairro,
                "cidade": cidade,
                "estado": estado_uf
            })
        else:
            return jsonify({"erro": f"CEP não encontrado ({data['status']})"}), 404
            
    except Exception as e:
        print(f"Erro ao chamar API do Google: {e}")
        return jsonify({"erro": "Falha ao contatar o serviço de geocodificação."}), 500


# --- ROTA 7: Filtro de Nível de Acesso ---
@app.route('/api/filtros/niveisacesso', methods=['GET'])
def get_niveis_acesso():
    query = "SELECT ID_NIVEL_ACESSO, NIVEL_ACESSO FROM NivelAcesso ORDER BY NIVEL_ACESSO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar níveis de acesso"}), 500
    return jsonify(resultados)


# --- ROTA 8: Cadastro de Funcionário (POST) ---
@app.route('/api/funcionarios', methods=['POST'])
def criar_funcionario():
    dados = request.get_json()
    
    # 1. Verificação de Duplicidade (CPF/Telefone)
    try:
        cpf_novo = dados.get('cpf')
        telefone_novo = dados.get('telefone')

        if not cpf_novo:
             return jsonify({"erro": "CPF é obrigatório."}), 400

        cpf_check_query = "SELECT 1 FROM Funcionario WHERE CPF_FUNCIONARIO = %s"
        cpf_result = executar_query(cpf_check_query, (cpf_novo,))
        if cpf_result:
            return jsonify({"erro": f"Erro: O CPF '{cpf_novo}' já está cadastrado para um funcionário."}), 409 
        
        if telefone_novo: 
            tel_check_query = "SELECT 1 FROM Funcionario WHERE TELEFONE = %s"
            tel_result = executar_query(tel_check_query, (telefone_novo,))
            if tel_result:
                return jsonify({"erro": f"Erro: O Telefone '{telefone_novo}' já está cadastrado para um funcionário."}), 409
    
    except Exception as e:
        print(f"Erro durante a pré-verificação do funcionário: {e}")
        return jsonify({"erro": "Erro ao verificar dados. Tente novamente."}), 500
    
    # 2. Inserção no banco
    try:
        query = """
            INSERT INTO Funcionario (
                ID_NIVEL_ACESSO, NOME_FUNCIONARIO, CPF_FUNCIONARIO, 
                DATA_NASCIMENTO_FUNCIONARIO, TELEFONE
            ) VALUES (%s, %s, %s, %s, %s)
        """
        params = (
            dados.get('id_nivel_acesso'),
            dados.get('nome'),
            dados.get('cpf'),
            dados.get('data_nascimento'),
            dados.get('telefone')
        )
        
        sucesso = executar_query_escrita(query, params)
        
        if not sucesso:
            return jsonify({"erro": "Falha ao inserir dados no banco"}), 500

        return jsonify({"sucesso": True, "mensagem": "Funcionário cadastrado!"}), 201

    except Error as e:
        print(f"Erro no cadastro de funcionário (Erro DB): {e}")
        return jsonify({"erro": f"Erro de banco de dados: {e.msg}"}), 500
    except Exception as e:
        print(f"Erro no endpoint /api/funcionarios: {e}")
        return jsonify({"erro": str(e)}), 500


# --- ROTA 9: Cadastro de Hospital (POST) ---
@app.route('/api/locaisatendimento', methods=['POST'])
def criar_local_atendimento():
    dados = request.get_json()
    conexao = None
    cursor = None
    
    try:
        # 1. Verificação de Duplicidade (Nome do Local)
        nome_local = dados.get('nome')
        if not nome_local:
            return jsonify({"erro": "Nome do hospital é obrigatório."}), 400
            
        local_check_query = "SELECT 1 FROM LocalAtendimento WHERE NOME_LOCAL_ATENDIMENTO = %s"
        local_result = executar_query(local_check_query, (nome_local,))
        if local_result:
            return jsonify({"erro": f"Erro: O local '{nome_local}' já está cadastrado."}), 409

        # 2. TRANSAÇÃO DO BANCO
        conexao = criar_conexao()
        if not conexao:
            raise Exception("Falha ao conectar no banco de dados")
        
        conexao.autocommit = False 
        cursor = conexao.cursor()

        lat = dados.get('latitude')
        lon = dados.get('longitude')
        if lat is None or lon is None:
            return jsonify({"erro": "Coordenadas (Latitude/Longitude) são obrigatórias."}), 400

        estado_uf_limpo = (dados.get('estado') or 'ER').upper()[:2]
        
        # --- ⚡ CORREÇÃO DO CEP ⚡ ---
        cep_bruto = dados.get('cep')
        cep_limpo = re.sub(r'\D', '', cep_bruto or '')
        cep_final = cep_limpo.ljust(8, '0')[:8]
        
        # 2a. Estado
        cursor.execute("INSERT INTO Estado (NOME_ESTADO) VALUES (%s) ON DUPLICATE KEY UPDATE ID_ESTADO=LAST_INSERT_ID(ID_ESTADO)", (estado_uf_limpo,))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_estado = cursor.fetchone()[0]

        # 2b. Cidade
        cursor.execute("INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_CIDADE=LAST_INSERT_ID(ID_CIDADE)", (id_estado, dados.get('cidade')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_cidade = cursor.fetchone()[0]

        # 2c. Bairro
        cursor.execute("INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_BAIRRO=LAST_INSERT_ID(ID_BAIRRO)", (id_cidade, dados.get('bairro')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_bairro = cursor.fetchone()[0]

        # 2d. Rua (Usa o cep_final limpo)
        cursor.execute("INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE ID_RUA=LAST_INSERT_ID(ID_RUA)", 
                       (id_bairro, dados.get('rua'), cep_final))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_rua = cursor.fetchone()[0]
        
        # 2e. Endereco
        cursor.execute("INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES (%s, %s, %s, %s, %s)",
                       (id_rua, dados.get('numero'), lat, lon, dados.get('complemento')))
        id_endereco = cursor.lastrowid
        
        # 3. Criar o LocalAtendimento
        query_local = "INSERT INTO LocalAtendimento (ID_ENDERECO, NOME_LOCAL_ATENDIMENTO) VALUES (%s, %s)"
        params_local = (id_endereco, nome_local)
        
        cursor.execute(query_local, params_local)
        
        # 4. Salvar a transação
        conexao.commit()
        
        return jsonify({"sucesso": True, "mensagem": "Hospital cadastrado com sucesso!"}), 201

    except Error as e:
        if conexao:
            conexao.rollback()
        print(f"Erro na transação de local (Erro DB): {e}")
        return jsonify({"erro": f"Erro de banco de dados: {e.msg}"}), 500
    except Exception as e:
        if conexao:
            conexao.rollback()
        print(f"Erro na transação de local (Erro App): {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexao:
            conexao.close()


# --- Bloco de Execução ---
if __name__ == '__main__':
    print("Iniciando servidor Flask (com correção de CEP)...")
    app.run(debug=True, port=5000)