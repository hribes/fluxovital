import os
import json
import datetime
import re
import base64
import requests
import folium
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from mysql.connector import Error


try:
    from conexao_db import criar_conexao, ler_query_de_arquivo, executar_query_escrita
    from conversao_coordenadas import endereco_para_coordenadas
    from mapa_service import get_mapa_vazio, get_mapas_calculados, rota_real_osrm

except ImportError as e:
    print(f"ERRO DE IMPORTAÇÃO: {e}")
    print("Verifique se 'mapa_service.py', 'conexao_db.py' e 'conversao_coordenadas.py' estão na pasta.")
    exit()

# --- CONFIGURAÇÕES DO APP ---
API_KEY = os.getenv("GOOGLE_API_KEY")
app = Flask(__name__, template_folder=os.path.join(os.getcwd(), "frontend/desktop/pages"))

app.config['SECRET_KEY'] = 'chave_secreta_fluxovital_123'
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index_page'
cors = CORS(app, origins="http://127.0.0.1:5500", supports_credentials=True)


# --- CLASSES E FUNÇÕES AUXILIARES DE BANCO DE DADOS ---

class Usuario(UserMixin):
    def __init__(self, id, nome, nivel):
        self.id = id
        self.nome = nome
        self.nivel = nivel

def executar_query(query, params=None):
    conexao = None
    cursor = None
    resultados = []
    try:
        conexao = criar_conexao() 
        if conexao is None: return None
        cursor = conexao.cursor(dictionary=True)
        if params: cursor.execute(query, params)
        else: cursor.execute(query)
        resultados = cursor.fetchall()
    except Error as e: 
        print(f"Erro SQL: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conexao: conexao.close()
    return resultados

@login_manager.user_loader
def load_user(user_id):
    res = executar_query("SELECT ID_FUNCIONARIO, NOME_FUNCIONARIO, ID_NIVEL_ACESSO FROM Funcionario WHERE ID_FUNCIONARIO = %s", (user_id,))
    if res: return Usuario(res[0]['ID_FUNCIONARIO'], res[0]['NOME_FUNCIONARIO'], res[0]['ID_NIVEL_ACESSO'])
    return None


# --- ROTAS E MAPAS ---

@app.route('/rotas')
@login_required
def rotas_vazias():
    #Mapa da cidade de marilia vazio
    map_html = get_mapa_vazio()
    return render_template("visualizacao_rotas.html", map=map_html, tempo_total_min=0)

@app.route('/rota1')
@login_required
def visualizar_rota_1():
   #Rota do veiculo 1 - teste
    mapas = get_mapas_calculados()
    if not mapas or 'rota1' not in mapas:
        return "<h1>Não foi possível gerar a rota 1 (solução não encontrada).</h1>"
    return render_template("visualizacao_rotas.html", map=mapas['rota1'], tempo_total_min=0)

@app.route('/rota2')
@login_required
def visualizar_rota_2():
    #rota do veiculo 2 - teste
    mapas = get_mapas_calculados()
    if not mapas or 'rota2' not in mapas:
        return "<h1>Não foi possível gerar a rota 2 (solução não encontrada).</h1>"
    return render_template("visualizacao_rotas.html", map=mapas['rota2'], tempo_total_min=0)

@app.route('/api/rotas/visualizar', methods=['GET'])
@login_required
def visualizar_rota_salva():
    veiculo_id = request.args.get('veiculo')
    data_rota = request.args.get('data')
    
    query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_rota_salva.sql'))
    pontos_rota = executar_query(query, (int(veiculo_id), str(data_rota)))
    
    if not pontos_rota: return jsonify({"erro": "Rota não encontrada"}), 404

    secretaria = (-22.213200, -49.944700)
    m = folium.Map(location=secretaria, zoom_start=13)
    folium.Marker(secretaria, icon=folium.Icon(color="black", icon="home"), tooltip="Secretaria").add_to(m)
    
    coords_ordenadas = [secretaria]
    for p in pontos_rota:
        coord = (float(p['LATITUDE']), float(p['LONGITUDE']))
        coords_ordenadas.append(coord)
        cor = "green" if p['TIPO_PARADA'] == 'COLETA' else "red"
        folium.Marker(coord, icon=folium.Icon(color=cor), tooltip=f"{p['ORDEM']}. {p['NOME_PONTO']}").add_to(m)
    coords_ordenadas.append(secretaria)

    traçado, _ = rota_real_osrm(coords_ordenadas)
    
    if traçado:
        folium.PolyLine([(c[1], c[0]) for c in traçado], weight=5, color="blue", opacity=0.8).add_to(m)
    else:
        folium.PolyLine(coords_ordenadas, weight=2, color="blue", opacity=0.5, dash_array='5, 10').add_to(m)

    return jsonify({"mapa_html": m._repr_html_()})

@app.route('/api/rotas/filtros', methods=['GET'])
@login_required
def get_filtros_rotas():
    query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_filtros_rotas.sql'))
    return jsonify(executar_query(query) or [])


# --- ROTAS DA API (CADASTROS E CONSULTAS) ---

@app.route('/api/agendamentos', methods=['GET'])
@login_required
def get_agendamentos():
    try: pagina = int(request.args.get('pagina', 1)); pagina = 1 if pagina < 1 else pagina
    except: pagina = 1
    limite, offset = 30, (pagina - 1) * 30
    data, status, local = request.args.get('data'), request.args.get('status'), request.args.get('local')
    query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_agendamentos.sql'))
    params = []; where = []
    if data: where.append("DATE(sc.DATA_HORA_CONSULTA) = %s"); params.append(data)
    if status and status != '1': where.append("sc.ID_STATUS = %s"); params.append(status)
    if local and local != '1': where.append("sc.ID_LOCAL_ATENDIMENTO = %s"); params.append(local)
    if where: query += " WHERE " + " AND ".join(where)
    query += " ORDER BY sc.DATA_HORA_CONSULTA DESC LIMIT %s OFFSET %s;"
    params.extend([limite, offset])
    return jsonify(executar_query(query, tuple(params)) or [])

@app.route('/api/pacientes', methods=['GET', 'POST'])
@login_required
def handle_pacientes():
    if request.method == 'GET': return jsonify(executar_query("SELECT ID_PACIENTE, NOME_PACIENTE, ID_ENDERECO FROM Paciente ORDER BY NOME_PACIENTE;"))
    dados = request.get_json()
    if executar_query("SELECT 1 FROM Paciente WHERE CPF_PACIENTE = %s", (dados.get('cpf'),)): return jsonify({"erro": "CPF já existe"}), 409
    addr = f"{dados.get('rua')}, {dados.get('numero')}, {dados.get('bairro')}, {dados.get('cidade')}, {dados.get('estado')}, Brasil"
    lat, lon = endereco_para_coordenadas(addr)
    if lat is None: return jsonify({"erro": "Endereço inválido"}), 400
    
    cnx = criar_conexao(); cnx.autocommit = False; cursor = cnx.cursor()
    try:
        estado_uf_limpo = (dados.get('estado') or 'ER').upper()[:2]
        cep_bruto = dados.get('cep')
        cep_limpo = re.sub(r'\D', '', cep_bruto or '')
        cep_final = cep_limpo.ljust(8, '0')[:8]
        cursor.execute(
            "INSERT INTO Estado (NOME_ESTADO) VALUES (%s) ON DUPLICATE KEY UPDATE ID_ESTADO=LAST_INSERT_ID(ID_ESTADO)", (estado_uf_limpo,))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_estado = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_CIDADE=LAST_INSERT_ID(ID_CIDADE)",
                        (id_estado, dados.get('cidade')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_cidade = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_BAIRRO=LAST_INSERT_ID(ID_BAIRRO)",
                        (id_cidade, dados.get('bairro')))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_bairro = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE ID_RUA=LAST_INSERT_ID(ID_RUA)",
                        (id_bairro, dados.get('rua'), cep_final))
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_rua = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES (%s, %s, %s, %s, %s)",
                        (id_rua, dados.get('numero'), lat, lon, dados.get('complemento')))
        id_endereco = cursor.lastrowid
        query_paciente = """
            INSERT INTO Paciente (ID_ENDERECO, SEXO, NOME_PACIENTE, CPF_PACIENTE, SENHA, DATA_NASCIMENTO, TELEFONE)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params_paciente = (
            id_endereco, dados.get('sexo'), dados.get('nome'), dados.get('cpf'),
            dados.get('senha'), dados.get('data_nascimento'), dados.get('telefone')
        )
        cursor.execute(query_paciente, params_paciente)
        cnx.commit()
    except Exception as e: cnx.rollback(); return jsonify({"erro": str(e)}), 500
    finally: cursor.close(); cnx.close()
    return jsonify({"sucesso": True}), 201

@app.route('/api/cep/<string:cep_number>', methods=['GET'])
@login_required
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
            bairro = find_component(components, "sublocality_level_1") or find_component(components, "sublocality") or find_component(components, "political")
            cidade = find_component(components, "administrative_area_level_2")
            estado_uf = find_component(components, "administrative_area_level_1", 'short_name')
            return jsonify({
                "rua": rua, "bairro": bairro, "cidade": cidade, "estado": estado_uf
            })
        else:
            return jsonify({"erro": f"CEP não encontrado ({data['status']})"}), 404
    except Exception as e:
        print(f"Erro ao chamar API do Google: {e}")
        return jsonify({"erro": "Falha ao contatar o serviço de geocodificação."}), 500
    
@app.route('/api/filtros/niveisacesso', methods=['GET'])
@login_required
def get_niveis_acesso():
    query = "SELECT ID_NIVEL_ACESSO, NIVEL_ACESSO FROM NivelAcesso ORDER BY NIVEL_ACESSO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar níveis de acesso"}), 500
    return jsonify(resultados)

@app.route('/api/funcionarios', methods=['POST'])
@login_required  
def criar_funcionario():
    dados = request.get_json()
    try:
        cpf_novo = dados.get('cpf')
        telefone_novo = dados.get('telefone')
        if not cpf_novo:
            return jsonify({"erro": "CPF é obrigatório."}), 400
        if executar_query("SELECT 1 FROM Funcionario WHERE CPF_FUNCIONARIO = %s", (cpf_novo,)):
            return jsonify({"erro": f"Erro: O CPF '{cpf_novo}' já está cadastrado."}), 409
        if telefone_novo and executar_query("SELECT 1 FROM Funcionario WHERE TELEFONE = %s", (telefone_novo,)):
            return jsonify({"erro": f"Erro: O Telefone '{telefone_novo}' já está cadastrado."}), 409
    except Exception as e:
        return jsonify({"erro": "Erro ao verificar dados."}), 500
    try:
        query = """
            INSERT INTO Funcionario (ID_NIVEL_ACESSO, NOME_FUNCIONARIO, CPF_FUNCIONARIO, DATA_NASCIMENTO_FUNCIONARIO, TELEFONE, SENHA) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (dados.get('id_nivel_acesso'), dados.get('nome'), dados.get('cpf'), dados.get('data_nascimento'), dados.get('telefone'), '12345')
        sucesso = executar_query_escrita(query, params)
        if not sucesso: return jsonify({"erro": "Falha ao inserir dados"}), 500
        return jsonify({"sucesso": True, "mensagem": "Funcionário cadastrado!"}), 201
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    
@app.route('/api/locaisatendimento', methods=['POST'])
@login_required  
def criar_local_atendimento():
    dados = request.get_json()
    conexao = None; cursor = None
    try:
        nome_local = dados.get('nome')
        if not nome_local: return jsonify({"erro": "Nome do hospital é obrigatório."}), 400
        if executar_query("SELECT 1 FROM LocalAtendimento WHERE NOME_LOCAL_ATENDIMENTO = %s", (nome_local,)):
            return jsonify({"erro": f"Erro: O local '{nome_local}' já cadastrado."}), 409
        conexao = criar_conexao()
        conexao.autocommit = False
        cursor = conexao.cursor()
        lat, lon = dados.get('latitude'), dados.get('longitude')
        if lat is None or lon is None: return jsonify({"erro": "Coordenadas obrigatórias."}), 400
        
        estado_uf_limpo = (dados.get('estado') or 'ER').upper()[:2]
        cep_limpo = re.sub(r'\D', '', dados.get('cep') or '').ljust(8, '0')[:8]

        cursor.execute("INSERT INTO Estado (NOME_ESTADO) VALUES (%s) ON DUPLICATE KEY UPDATE ID_ESTADO=LAST_INSERT_ID(ID_ESTADO)", (estado_uf_limpo,))
        id_estado = cursor.lastrowid
        cursor.execute("INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_CIDADE=LAST_INSERT_ID(ID_CIDADE)", (id_estado, dados.get('cidade')))
        id_cidade = cursor.lastrowid
        cursor.execute("INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_BAIRRO=LAST_INSERT_ID(ID_BAIRRO)", (id_cidade, dados.get('bairro')))
        id_bairro = cursor.lastrowid
        cursor.execute("INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE ID_RUA=LAST_INSERT_ID(ID_RUA)", (id_bairro, dados.get('rua'), cep_limpo))
        id_rua = cursor.lastrowid
        cursor.execute("INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES (%s, %s, %s, %s, %s)", (id_rua, dados.get('numero'), lat, lon, dados.get('complemento')))
        id_endereco = cursor.lastrowid
        cursor.execute("INSERT INTO LocalAtendimento (ID_ENDERECO, NOME_LOCAL_ATENDIMENTO) VALUES (%s, %s)", (id_endereco, nome_local))
        conexao.commit()
        return jsonify({"sucesso": True, "mensagem": "Hospital cadastrado!"}), 201
    except Exception as e:
        if conexao: conexao.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexao: conexao.close()

@app.route('/api/veiculos', methods=['GET', 'POST'])
@login_required
def handle_veiculos():
    if request.method == 'GET':
        status_id = request.args.get('status')
        query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_veiculos.sql'))
        if not query: return jsonify({"erro": "SQL não encontrado."}), 500
        params = []
        if status_id and status_id != 'all':
            query += " WHERE v.ID_STATUS = %s"
            params.append(status_id)
        query += " ORDER BY v.ID_VEICULO;"
        return jsonify(executar_query(query, tuple(params)) or [])
    elif request.method == 'POST':
        dados = request.get_json()
        try:
            placa_limpa = re.sub(r'[^A-Z0-9]', '', (dados.get('placa') or '').upper())
            if not placa_limpa: return jsonify({"erro": "Placa obrigatória."}), 400
            if executar_query("SELECT 1 FROM Veiculo WHERE PLACA = %s", (placa_limpa,)):
                return jsonify({"erro": "Placa já cadastrada."}), 409
            query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'insert_veiculo.sql'))
            params = (dados.get('id_tipo_veiculo'), dados.get('id_status'), dados.get('capacidade'), placa_limpa)
            if not executar_query_escrita(query, params): return jsonify({"erro": "Falha ao inserir."}), 500
            return jsonify({"sucesso": True, "mensagem": "Veículo cadastrado!"}), 201
        except Exception as e: return jsonify({"erro": str(e)}), 500

@app.route('/api/veiculos/<string:placa>', methods=['GET'])
@login_required
def get_veiculo_by_placa(placa):
    placa_limpa = re.sub(r'[^A-Z0-9]', '', placa.upper())
    query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_veiculo_by_placa.sql'))
    resultado = executar_query(query, (placa_limpa,))
    return jsonify(resultado[0]) if resultado else (jsonify({"erro": "Não encontrado"}), 404)

@app.route('/api/veiculos/<string:placa>', methods=['PUT'])
@login_required
def update_veiculo_status(placa):
    dados = request.get_json()
    novo_status_id = dados.get('id_status')
    placa_limpa = re.sub(r'[^A-Z0-9]', '', placa.upper())
    query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'update_veiculo_status.sql'))
    if executar_query_escrita(query, (novo_status_id, placa_limpa)):
        return jsonify({"sucesso": True}), 200
    return jsonify({"erro": "Falha ao atualizar"}), 500

@app.route('/api/motoristas', methods=['GET', 'POST'])
@login_required
def handle_motoristas():
    if request.method == 'GET':
        categoria = request.args.get('categoria')
        query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'get_motoristas.sql'))
        params = []
        if categoria and categoria != 'all':
            query += " WHERE CATEGORIA_CNH = %s"
            params.append(categoria)
        query += " ORDER BY NOME_MOTORISTA;"
        resultados = executar_query(query, tuple(params)) or []
        for m in resultados:
            if m['FOTO_PERFIL']:
                foto_base64 = base64.b64encode(m['FOTO_PERFIL']).decode('utf-8')
                m['FOTO_PERFIL'] = f'data:image/jpeg;base64,{foto_base64}'
        return jsonify(resultados)
    elif request.method == 'POST':
        nome, cpf = request.form.get('nome'), request.form.get('cpf')
        categoria, foto = request.form.get('categoria_cnh'), request.files.get('foto')
        foto_bytes = foto.read() if foto else None
        if executar_query("SELECT 1 FROM Motorista WHERE CPF_MOTORISTA = %s", (cpf,)):
            return jsonify({"erro": "CPF já cadastrado"}), 409
        query = ler_query_de_arquivo(os.path.join('backend', 'src', 'modules', 'queries', 'insert_motorista.sql'))
        if executar_query_escrita(query, (nome, cpf, categoria, foto_bytes)):
            return jsonify({"sucesso": True}), 201
        return jsonify({"erro": "Erro ao salvar"}), 500

@app.route('/api/filtros/categoriascnh', methods=['GET'])
@login_required
def get_filtros_cnh():
    return jsonify(executar_query("SELECT DISTINCT CATEGORIA_CNH FROM Motorista WHERE CATEGORIA_CNH IS NOT NULL ORDER BY CATEGORIA_CNH;") or [])

@app.route('/api/filtros/tiposveiculo', methods=['GET'])
@login_required 
def get_filtros_tipos_veiculo():
    query = "SELECT ID_TIPO_VEICULO, NOME_TIPO_VEICULO FROM TipoVeiculo ORDER BY NOME_TIPO_VEICULO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de veículo"}), 500
    return jsonify(resultados)

# --- LOGIN E LOGOUT ---

@app.route('/api/login', methods=['POST'])
def realizar_login():
    dados = request.get_json()
    tipo, cpf, senha_texto = dados.get('tipo'), dados.get('cpf'), dados.get('senha')
    if not cpf or not senha_texto: return jsonify({"erro": "Preencha CPF e Senha."}), 400
    cpf_limpo = re.sub(r'\D', '', cpf)
    
    if tipo == '1': # Funcionário
        res = executar_query("SELECT ID_FUNCIONARIO, NOME_FUNCIONARIO, ID_NIVEL_ACESSO, SENHA FROM Funcionario WHERE CPF_FUNCIONARIO = %s", (cpf_limpo,))
        if res:
            user_db = res[0]
            senha_valida = False
            try: senha_valida = bcrypt.check_password_hash(user_db['SENHA'], senha_texto)
            except: senha_valida = (user_db['SENHA'] == senha_texto) # Fallback para senha em texto plano (apenas dev)
            
            if senha_valida:
                user_obj = Usuario(user_db['ID_FUNCIONARIO'], user_db['NOME_FUNCIONARIO'], user_db['ID_NIVEL_ACESSO'])
                login_user(user_obj, remember=True)
                return jsonify({"sucesso": True, "mensagem": "Login realizado!", "usuario": {"NOME_FUNCIONARIO": user_obj.nome}}), 200
            return jsonify({"erro": "Senha incorreta."}), 401
        return jsonify({"erro": "CPF não encontrado."}), 401
    return jsonify({"erro": "Tipo de usuário não suportado."}), 400

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"sucesso": True})

# --- ROTAS DE PÁGINAS (TEMPLATES) ---

@app.route("/")
def index_page(): return render_template("index.html")

@app.route("/home")
@login_required
def home_page(): return render_template("home.html")

@app.route("/cadastrar/consulta")
@login_required
def cadastrar_consulta(): return render_template("cadastro_consulta.html")

@app.route("/cadastrar/paciente")
@login_required
def cadastrar_paciente(): return render_template("cadastro_paciente.html")

@app.route("/cadastrar/hospital")
@login_required
def cadastrar_hospital(): return render_template("cadastro_hospital.html")

@app.route("/cadastrar/funcionario")
@login_required
def cadastrar_funcionario(): return render_template("cadastro_funcionarios.html")

@app.route("/cadastrar/motorista")
@login_required
def cadastrar_motorista(): return render_template("cadastro_motorista.html")

@app.route("/cadastrar/veiculo")
@login_required
def cadastrar_veiculo(): return render_template("cadastro_veiculo.html")

@app.route("/agendamentos")
@login_required
def consultar_paciente(): return render_template("consulta_pacientes.html")
    
@app.route("/visualizar/motorista")
@login_required
def consultar_motoristas(): return render_template("consulta_motorista.html")

@app.route("/visualizar/veiculo")
@login_required
def consultar_veiculos(): return render_template("consulta_veiculos.html")

@app.route("/veiculo/rotas")
@login_required
def consultar_veiculos_rotas(): return render_template("consulta_veiculos.c.rotas.html")

@app.route("/atribuir/motorista")
@login_required
def atribuir_motorista():
    map_html = get_mapa_vazio()
    if map_html is None:
        return "<h1>Sem solução</h1>"

    return render_template(
        "atribuicao_motoristas.html",
        map=map_html
    )


# --- ROTAS DE ESTÁTICOS ---
@app.route('/styles/<path:filename>')
def custom_styles_static(filename): return send_from_directory(os.path.join(os.getcwd(), 'frontend/desktop/styles'), filename)
@app.route('/assets/<path:filename>')
def custom_assets_static(filename): return send_from_directory(os.path.join(os.getcwd(), 'frontend/desktop/assets'), filename)
@app.route('/services/<path:filename>')
def custom_services_static(filename): return send_from_directory(os.path.join(os.getcwd(), 'frontend/desktop/services'), filename)

if __name__ == '__main__':
    print("Iniciando servidor Flask (FluxoVital)...")
    app.run(debug=True, port=5000)


