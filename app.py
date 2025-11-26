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
from folium import DivIcon
import mysql.connector


try:
    from conexao_db import criar_conexao, ler_query_de_arquivo, executar_query_escrita
    from backend.src.modules.prep_dados.funcoes_preparacao_dados import preparar_dados, endereco_para_coordenadas
    from backend.src.modules.prep_dados.busca_bd import buscar_dados
    from backend.src.modules.prep_dados.matriz_distancias import construir_matriz_tempo_distancia
    from mapa_service import get_mapas_calculados, rota_real_osrm

except ImportError as e:
    print(f"ERRO DE IMPORTAÇÃO: {e}")
    print("Verifique se 'mapa_service.py', 'conexao_db.py' e 'conversao_coordenadas.py' estão na pasta.")
    exit()

# --- CONFIGURAÇÕES DO APP ---
API_KEY = os.getenv("GOOGLE_API_KEY")
app = Flask(__name__, template_folder=os.path.join(os.getcwd(), "frontend/desktop/pages"))

UPA_ENDERECO = "Av. Sampaio Vidal, 200, Marília, SP, 17500-022"
ORS_API_KEY = os.getenv("ORS_API_KEY") 

# --- HELPER PARA PEGAR DADOS ---
def obter_dados_reais_hoje():
    # Defina a data 
    data_hoje = os.getenv('DATA_SOLVER')
    
    df_pacientes, df_veiculos = buscar_dados(data_hoje)
    if df_pacientes is None or df_veiculos is None: return None
    
    dados_prep = preparar_dados(df_veiculos, df_pacientes, data_hoje, UPA_ENDERECO)
    if not dados_prep: return None
    
    dados_completos = construir_matriz_tempo_distancia(dados_prep, ORS_API_KEY)
    return dados_completos

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

 

def salvar_resultado_otimizacao(mapas_calculados, data_da_rota):
    """
    Itera sobre o resultado do OR-Tools e salva na tabela Parada
    usando a função executar_query_escrita do seu conexao_db.py
    """
    print(">>> Iniciando gravação no banco de dados...")
    
    sucesso_total = True

    # 1. Limpar rotas anteriores para essa data (Opcional, evita duplicidade em testes)
    sql_limpeza = "DELETE FROM Parada WHERE DATA_ROTA = %s"
    if not executar_query_escrita(sql_limpeza, (data_da_rota,)):
        print("Aviso: Não foi possível limpar rotas antigas ou não existiam rotas.")

    # Iterar sobre os veículos (Chave: ID ou Indice do Veículo, Valor: Lista de Paradas)
    # Ajuste 'items()' conforme a estrutura exata do seu objeto 'mapas'
    for id_veiculo_str, lista_paradas in mapas_calculados.items():
        
        # Se a chave for string "rota1", precisamos pegar o ID real do veículo.
        # Supondo que dentro de cada parada tenha o 'id_veiculo':
        
        ordem = 1
        
        for parada in lista_paradas:
            # Recupera os dados do dicionário da parada
            # IMPORTANTE: O seu get_mapas_calculados() precisa fornecer esses IDs
            id_veiculo = parada.get('id_veiculo') 
            id_paciente = parada.get('id_paciente') # Deve ser None se for Base
            id_endereco = parada.get('id_endereco')
            tipo_parada = parada.get('tipo') # 'COLETA', 'ENTREGA', etc
            hora_estimada = parada.get('hora_estimada', '00:00:00') # Padrão se não tiver
            id_solicitacao = parada.get('id_solicitacao')

            # Tratamento para Base (Se for saída/chegada da garagem)
            # Se id_paciente for None, o MySQL gravará NULL (se a tabela permitir)
            
            sql_insert = """
                INSERT INTO Parada 
                (ID_VEICULO, ID_PACIENTE, ID_ENDERECO, TIPO_PARADA, DATA_ROTA, HORA_PARADA, ORDEM)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params_insert = (id_veiculo, id_paciente, id_endereco, tipo_parada, data_da_rota, hora_estimada, ordem)
            
            # Usa sua função pronta para inserir
            if executar_query_escrita(sql_insert, params_insert):
                pass # Sucesso
            else:
                print(f"Erro ao inserir parada {ordem} do veículo {id_veiculo}")
                sucesso_total = False

            # Atualizar Status da Solicitação para "Em Rota" (ID 2 no seu banco)
            # Apenas se tiver uma solicitação vinculada (Base não tem)
            if id_solicitacao:
                sql_update = "UPDATE SolicitacaoConsulta SET ID_STATUS = 2 WHERE ID_SOLICITACAO_CONSULTA = %s"
                executar_query_escrita(sql_update, (id_solicitacao,))
            
            ordem += 1

    return sucesso_total




@login_manager.user_loader
def load_user(user_id):
    res = executar_query("SELECT ID_FUNCIONARIO, NOME_FUNCIONARIO, ID_NIVEL_ACESSO FROM Funcionario WHERE ID_FUNCIONARIO = %s", (user_id,))
    if res: return Usuario(res[0]['ID_FUNCIONARIO'], res[0]['NOME_FUNCIONARIO'], res[0]['ID_NIVEL_ACESSO'])
    return None


def get_mapa_vazio():
    return folium.Map(location=[-22.213200, -49.944700], zoom_start=13)._repr_html_()


def rota_real_osrm_segmento(origem_latlon, destino_latlon):
    """
    Recebe (lat, lon) de origem e destino e retorna a lista de coordenadas da rua.
    """
    # OSRM espera longitude,latitude
    coords_str = f"{origem_latlon[1]},{origem_latlon[0]};{destino_latlon[1]},{destino_latlon[0]}"
    url = f"https://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    try:
        r = requests.get(url, timeout=2)
        if r.status_code == 200:
            data = r.json()
            # Retorna lista de [lon, lat]. Precisaremos inverter para [lat, lon] depois.
            return data["routes"][0]["geometry"]["coordinates"]
    except:
        pass
    return [] # Retorna vazio se falhar



# --- VISUALIZAÇÃO DAS ROTAS POR FILTRO --- 
@app.route('/visualizar_rotas_salvas')
@login_required
def visualizar_rotas_salvas():
    # 1. Parâmetros e Data Padrão
    data_filtro = request.args.get('data')
    veiculo_id = request.args.get('veiculo')
    
    if not data_filtro:
        data_filtro = os.getenv("DATA_SOLVER", datetime.date.today().strftime('%Y-%m-%d'))

    # 2. Conexão DB
    conn = criar_conexao()
    if not conn: return "Erro conexão"
    
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT p.*, e.LATITUDE, e.LONGITUDE, e.NUMERO_ENDERECO, r.NOME_RUA,
               pac.NOME_PACIENTE, la.NOME_LOCAL_ATENDIMENTO, tv.NOME_TIPO_VEICULO
        FROM Parada p
        JOIN Veiculo v ON p.ID_VEICULO = v.ID_VEICULO
        JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO
        JOIN Endereco e ON p.ID_ENDERECO = e.ID_ENDERECO
        JOIN Rua r ON e.ID_RUA = r.ID_RUA
        LEFT JOIN Paciente pac ON p.ID_PACIENTE = pac.ID_PACIENTE
        LEFT JOIN LocalAtendimento la ON p.ID_ENDERECO = la.ID_ENDERECO
        WHERE p.DATA_ROTA = %s
    """
    params = [data_filtro]
    if veiculo_id and veiculo_id != "0": 
        sql += " AND p.ID_VEICULO = %s"
        params.append(veiculo_id)
    
    sql += " ORDER BY p.ID_VEICULO, p.ORDEM ASC"
    
    try:
        cursor.execute(sql, params)
        paradas = cursor.fetchall()
    except Exception as e:
        print(f"Erro SQL: {e}")
        return get_mapa_vazio()
    finally:
        cursor.close(); conn.close()

    if not paradas: return get_mapa_vazio()

    # 3. Mapa
    try:
        m = folium.Map(location=[float(paradas[0]['LATITUDE']), float(paradas[0]['LONGITUDE'])], zoom_start=14)
    except:
        m = folium.Map(location=[-22.2132, -49.9447], zoom_start=13)

    # 4. Agrupa por veículo
    rotas_veiculos = {}
    for p in paradas:
        rotas_veiculos.setdefault(p['ID_VEICULO'], []).append(p)

    colors = ['blue', 'green', 'red', 'purple', 'orange', 'darkred', 'cadetblue']
    
    # 5. Desenha
    for i, (vid, lista) in enumerate(rotas_veiculos.items()):
        cor = colors[i % len(colors)]
        pontos_para_api = [] 
        coords_controle = {} 

        for ponto in lista:
            # Coordenadas
            lat_real = float(ponto['LATITUDE'])
            lon_real = float(ponto['LONGITUDE'])
            pontos_para_api.append(f"{lon_real},{lat_real}")

            # Jitter (Anti-sobreposição visual)
            lat_visual, lon_visual = lat_real, lon_real
            chave_coord = (lat_real, lon_real)
            if chave_coord in coords_controle:
                fator = coords_controle[chave_coord]
                offset = 0.00025 * fator 
                lat_visual += offset
                lon_visual += offset
                coords_controle[chave_coord] += 1
            else:
                coords_controle[chave_coord] = 1

            # --- DADOS PARA O ÍCONE ---
            tipo = ponto['TIPO_PARADA']
            ordem = ponto['ORDEM']
            
            # Recupera o Nome
            nome_exibicao = ponto.get('NOME_PACIENTE') or ponto.get('NOME_LOCAL_ATENDIMENTO') or 'Base'
            if len(nome_exibicao) > 22: nome_exibicao = nome_exibicao[:20] + "..."

            # LÓGICA DOS ÍCONES E CORES
            if tipo == 'COLETA': 
                cor_css = "#28a745" # Verde Bootstrap
                icone_fa = "fa-house" # Ícone de Casa
            elif tipo == 'ENTREGA': 
                cor_css = "#dc3545" # Vermelho Bootstrap
                icone_fa = "fa-hospital" # Ícone de Hospital
            else: 
                cor_css = "#212529" # Preto Base
                icone_fa = "fa-flag" # Ícone de Bandeira

            # --- HTML DO ÍCONE COM SÍMBOLO ---
            # Aumentei a largura (width) para 45px para caber ícone + número
            html_icone = f"""
            <div style="position: relative; width: 220px;">
                
                <div style="
                    background-color: {cor_css}; color: white; border-radius: 30px;
                    min-width: 45px; height: 30px;
                    padding: 0 8px;
                    display: flex; align-items: center; justify-content: center;
                    font-weight: bold; font-family: Arial;
                    border: 2px solid white; box-shadow: 2px 2px 4px rgba(0,0,0,0.5);
                    position: absolute; left: 0; top: 0; z-index: 2;
                ">
                    <i class="fa-solid {icone_fa}" style="font-size: 12px; margin-right: 5px;"></i>
                    {ordem}
                </div>

                <div style="
                    background-color: rgba(255, 255, 255, 0.95);
                    color: black;
                    padding: 4px 8px 4px 35px; /* Mais espaço na esquerda para a pílula */
                    border-radius: 4px;
                    border: 1px solid {cor_css};
                    font-size: 11px;
                    font-weight: bold;
                    white-space: nowrap;
                    position: absolute;
                    left: 10px; 
                    top: 2px;
                    z-index: 1;
                    box-shadow: 1px 1px 3px rgba(0,0,0,0.3);
                ">
                    {nome_exibicao}
                </div>
            </div>
            """
            
            texto_popup = f"<b>{ordem}. {tipo}</b><br>{ponto.get('NOME_PACIENTE') or 'Local'}<br>{ponto.get('NOME_RUA')}, {ponto.get('NUMERO_ENDERECO')}"

            folium.Marker(
                [lat_visual, lon_visual],
                icon=DivIcon(icon_size=(30, 30), icon_anchor=(15, 15), html=html_icone),
                popup=texto_popup
            ).add_to(m)

        # --- Desenha Trajeto ---
        if len(pontos_para_api) > 1:
            try:
                coords_str = ";".join(pontos_para_api)
                url = f"https://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
                r = requests.get(url, timeout=3)
                if r.status_code == 200:
                    geo = r.json()['routes'][0]['geometry']['coordinates']
                    folium.PolyLine([[c[1], c[0]] for c in geo], color=cor, weight=5, opacity=0.7).add_to(m)
                else:
                    folium.PolyLine([[float(p['LATITUDE']), float(p['LONGITUDE'])] for p in lista], color=cor, weight=3, dash_array='5,5').add_to(m)
            except:
                 folium.PolyLine([[float(p['LATITUDE']), float(p['LONGITUDE'])] for p in lista], color=cor, weight=3, dash_array='5,5').add_to(m)

    return m._repr_html_()



# --- ROTAS E MAPAS ---

@app.route('/rotas')
@login_required
def rotas_vazias():
    #Mapa da cidade de marilia vazio
    map_html = get_mapa_vazio()
    return render_template("visualizacao_rotas.html", map=map_html, tempo_total_min=0)

@app.route('/calcularRota')
@login_required
def visualizar_rota_1():
    try:
        print(">>> 1. Buscando dados...")
        dados_db = obter_dados_reais_hoje()
        
        print(">>> 2. Calculando otimização...")
        mapas = get_mapas_calculados(dados_db)
        
        if not mapas or 'rota1' not in mapas:
            return jsonify({"status": "error", "message": "Não foi possível gerar a rota."}), 400
            
        # --- NOVO TRECHO DE CÓDIGO ---
        print(">>> 3. Salvando no Banco de Dados...")
        data_hoje = os.getenv("DATA_SOLVER") # Ou a data específica que você está calculando
        
        # Passamos o objeto mapas e a data para a função que criamos acima
        # OBS: Verifique se 'mapas' tem a estrutura que o 'salvar_resultado_otimizacao' espera
        salvou = salvar_resultado_otimizacao(mapas, data_hoje)
        # -----------------------------

        if salvou:
            print(">>> SUCESSO: Ciclo completo finalizado.")
            return jsonify({"status": "success", "message": "Rotas calculadas e salvas com sucesso!"}), 200
        else:
            return jsonify({"status": "warning", "message": "Rotas calculadas, mas houve erro ao salvar algumas paradas."}), 200

    except Exception as e:
        print(f">>> ERRO CRÍTICO: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    #Anterior
    # dados_db = obter_dados_reais_hoje()
    
    # mapas = get_mapas_calculados(dados_db)
    
    # if not mapas or 'rota1' not in mapas:
    #     return "<h1>Não foi possível gerar a rota 1 (Sem dados ou rota vazia).</h1>"
        
    # return render_template("visualizacao_rotas.html", map=mapas['rota1'], tempo_total_min=0)

@app.route('/rota2')
@login_required
def visualizar_rota_2():
    # Mesma lógica para rota 2
    dados_db = obter_dados_reais_hoje()
    mapas = get_mapas_calculados(dados_db)
    
    if not mapas or 'rota2' not in mapas:
        return "<h1>Não foi possível gerar a rota 2 (Sem dados ou rota vazia).</h1>"
        
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
        folium.PolyLine([(c[1], c[0]) for c in traçado], weight=5, color="#FFD700", opacity=0.8).add_to(m)
    else:
        folium.PolyLine(coords_ordenadas, weight=2, color="#FFD700", opacity=0.5, dash_array='5, 10').add_to(m)

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
    conexao = None
    cursor = None
    
    try:
        # --- 1. Validações Iniciais ---
        nome_local = dados.get('nome')
        cep_bruto = dados.get('cep')
        numero = dados.get('numero')
        lat, lon = dados.get('latitude'), dados.get('longitude')

        if not nome_local: 
            return jsonify({"erro": "Nome do hospital é obrigatório."}), 400
        if not cep_bruto or not numero:
            return jsonify({"erro": "CEP e Número são obrigatórios para validação."}), 400
        if lat is None or lon is None: 
            return jsonify({"erro": "Coordenadas obrigatórias."}), 400

        # Limpeza do CEP
        cep_limpo = re.sub(r'\D', '', cep_bruto).ljust(8, '0')[:8]

        # --- 2. Verificação de Duplicidade (NOME) ---
        if executar_query("SELECT 1 FROM LocalAtendimento WHERE NOME_LOCAL_ATENDIMENTO = %s", (nome_local,)):
            return jsonify({"erro": f"Erro: O local '{nome_local}' já está cadastrado."}), 409

        # --- 3. Verificação de Duplicidade (ENDEREÇO: CEP + NÚMERO) ---
        # Esta é a lógica que discutimos. Verifica se já existe um local com esse CEP e Número.
        sql_check_endereco = """
            SELECT count(*) as total
            FROM LocalAtendimento la
            JOIN Endereco e ON la.ID_ENDERECO = e.ID_ENDERECO
            JOIN Rua r ON e.ID_RUA = r.ID_RUA
            WHERE r.CEP = %s AND e.NUMERO_ENDERECO = %s
        """
        resultado_check = executar_query(sql_check_endereco, (cep_limpo, numero))
        
        # Como sua função executar_query retorna lista de dicionários:
        if resultado_check and resultado_check[0]['total'] > 0:
            return jsonify({
                "erro": "Endereço duplicado.",
                "mensagem": f"Já existe um local de atendimento cadastrado no CEP {cep_limpo}, número {numero}."
            }), 409

        # --- 4. Inserção no Banco (Lógica original mantida) ---
        conexao = criar_conexao()
        conexao.autocommit = False
        cursor = conexao.cursor()
        
        estado_uf_limpo = (dados.get('estado') or 'ER').upper()[:2]

        # Insere/Busca Estado
        cursor.execute("INSERT INTO Estado (NOME_ESTADO) VALUES (%s) ON DUPLICATE KEY UPDATE ID_ESTADO=LAST_INSERT_ID(ID_ESTADO)", (estado_uf_limpo,))
        id_estado = cursor.lastrowid
        
        # Insere/Busca Cidade
        cursor.execute("INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_CIDADE=LAST_INSERT_ID(ID_CIDADE)", (id_estado, dados.get('cidade')))
        id_cidade = cursor.lastrowid
        
        # Insere/Busca Bairro
        cursor.execute("INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ID_BAIRRO=LAST_INSERT_ID(ID_BAIRRO)", (id_cidade, dados.get('bairro')))
        id_bairro = cursor.lastrowid
        
        # Insere/Busca Rua (Usando o CEP limpo)
        cursor.execute("INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE ID_RUA=LAST_INSERT_ID(ID_RUA)", (id_bairro, dados.get('rua'), cep_limpo))
        id_rua = cursor.lastrowid
        
        # Insere Endereço
        cursor.execute("INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES (%s, %s, %s, %s, %s)", (id_rua, numero, lat, lon, dados.get('complemento')))
        id_endereco = cursor.lastrowid
        
        # Insere Local de Atendimento
        cursor.execute("INSERT INTO LocalAtendimento (ID_ENDERECO, NOME_LOCAL_ATENDIMENTO) VALUES (%s, %s)", (id_endereco, nome_local))
        
        conexao.commit()
        return jsonify({"sucesso": True, "mensagem": "Hospital/Local cadastrado com sucesso!"}), 201

    except Exception as e:
        if conexao: conexao.rollback()
        print(f"Erro ao criar local: {e}") # Log no terminal para debug
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexao: conexao.close()

@app.route('/api/veiculos', methods=['GET', 'POST'])
@login_required
def handle_veiculos():
    # --- GET: Listar Veículos ---
    if request.method == 'GET':
        status = request.args.get('status')
        sql = "SELECT v.*, tv.NOME_TIPO_VEICULO FROM Veiculo v JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO"
        if status and status != 'all': 
            sql += f" WHERE v.ID_STATUS = {status}"
        return jsonify(executar_query(sql) or [])
    
    # --- POST: Cadastrar Veículo (Com verificação de duplicidade) ---
    d = request.get_json()
    placa_limpa = re.sub(r'[^A-Z0-9]', '', d.get('placa', '').upper())

    # 1. VERIFICAÇÃO (O passo crucial para seu frontend)
    check = executar_query("SELECT 1 FROM Veiculo WHERE PLACA = %s", (placa_limpa,))
    if check:
        # Retorna 409 (Conflict) para o front saber que deve oferecer a atualização
        return jsonify({"erro": f"A placa {placa_limpa} já existe."}), 409

    # 2. INSERÇÃO
    sql = "INSERT INTO Veiculo (ID_TIPO_VEICULO, ID_STATUS, CAPACIDADE, PLACA) VALUES (%s, %s, %s, %s)"
    params = (d.get('id_tipo_veiculo'), d.get('id_status'), d.get('capacidade'), placa_limpa)
    
    if executar_query_escrita(sql, params): 
        return jsonify({"sucesso": True}), 201
        
    return jsonify({"erro": "Erro ao inserir no banco"}), 500

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


@app.route('/api/filtros/tiposconsulta', methods=['GET'])
@login_required 
def get_filtros_tipos_consulta():
    query = "SELECT ID_TIPO_CONSULTA, DESCRICO_CONSULTA FROM TipoConsulta ORDER BY DESCRICO_CONSULTA;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar tipos de consulta"}), 500
    return jsonify(resultados)


@app.route('/api/filtros/locais', methods=['GET'])
@login_required 
def get_filtros_locais():
    query = "SELECT ID_LOCAL_ATENDIMENTO, NOME_LOCAL_ATENDIMENTO FROM LocalAtendimento ORDER BY NOME_LOCAL_ATENDIMENTO;"
    resultados = executar_query(query)
    if resultados is None:
        return jsonify({"erro": "Falha ao buscar locais"}), 500
    return jsonify(resultados)


@app.route('/api/veiculos/todos_dropdown', methods=['GET'])
@login_required
def get_todos_veiculos_dropdown():
    # Busca todos os veículos cadastrados no sistema para preencher o select
    sql = """
        SELECT v.ID_VEICULO, v.PLACA, tv.NOME_TIPO_VEICULO 
        FROM Veiculo v 
        JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO 
        ORDER BY tv.NOME_TIPO_VEICULO, v.PLACA
    """
    return jsonify(executar_query(sql) or [])



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



@app.route('/api/consultas', methods=['POST'])
@login_required 
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



@app.route('/api/listar_veiculos')
@login_required
def listar_veiculos_api():
    conn = criar_conexao()
    cursor = conn.cursor(dictionary=True)
    
    # Busca ID, Placa e Nome do Tipo (ex: Ambulância)
    # Ajuste o WHERE conforme seus IDs de Status (supondo que 4 seja inativo)
    sql = """
        SELECT v.ID_VEICULO, v.PLACA, tv.NOME_TIPO_VEICULO 
        FROM Veiculo v
        JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO
        ORDER BY v.ID_VEICULO ASC
    """
    
    cursor.execute(sql)
    veiculos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(veiculos)



@app.route('/api/rotas/veiculos_ativos', methods=['GET'])
@login_required
def get_veiculos_ativos_rota():
    data = request.args.get('data')
    
    # Busca do arquivo
    path = os.path.join('backend', 'src', 'modules', 'queries', 'get_veiculos_rota_data.sql')
    sql = ler_query_de_arquivo(path)
    
    return jsonify(executar_query(sql, (data,)) or [])



@app.route('/api/rotas/lista_pacientes', methods=['GET'])
@login_required
def get_lista_pacientes_rota():
    data = request.args.get('data')
    veiculo_id = request.args.get('veiculo')
    
    # SQL Ajustado: Traz qualquer parada que tenha paciente vinculado
    # e removemos o filtro estrito de 'COLETA' para garantir que a lista carregue
    sql = """
        SELECT 
            CAST(p.HORA_PARADA AS CHAR) as HORA_PARADA, 
            COALESCE(pac.NOME_PACIENTE, 'Paciente (Sem Nome)') as NOME_PACIENTE,
            COALESCE(pac.CPF_PACIENTE, '---') as CPF_PACIENTE,
            tv.NOME_TIPO_VEICULO,
            v.PLACA,
            p.TIPO_PARADA,
            COALESCE(tc.DESCRICO_CONSULTA, 'Transporte') as TIPO_CONSULTA
        FROM Parada p
        JOIN Veiculo v ON p.ID_VEICULO = v.ID_VEICULO
        JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO
        LEFT JOIN Paciente pac ON p.ID_PACIENTE = pac.ID_PACIENTE
        LEFT JOIN SolicitacaoConsulta sc ON sc.ID_PACIENTE = pac.ID_PACIENTE 
             AND DATE(sc.DATA_HORA_IDA) = p.DATA_ROTA
        LEFT JOIN TipoConsulta tc ON sc.ID_TIPO_CONSULTA = tc.ID_TIPO_CONSULTA
        WHERE p.DATA_ROTA = %s 
          AND p.TIPO_PARADA != 'BASE' 
    """
    params = [data]
    
    if veiculo_id and veiculo_id != "0":
        sql += " AND p.ID_VEICULO = %s"
        params.append(veiculo_id)
        
    sql += " ORDER BY p.HORA_PARADA ASC"
    
    return jsonify(executar_query(sql, tuple(params)) or [])


# --- ROTA PARA PREENCHER O SELECT DE MOTORISTAS ---
@app.route('/api/motoristas/dropdown', methods=['GET'])
@login_required
def get_motoristas_dropdown():
    # Busca apenas ID e Nome para ficar leve
    sql = "SELECT ID_MOTORISTA, NOME_MOTORISTA FROM Motorista ORDER BY NOME_MOTORISTA"
    return jsonify(executar_query(sql) or [])



# --- ROTA PARA SALVAR A ATRIBUIÇÃO (MOTORISTA -> VEÍCULO) ---
@app.route('/api/atribuir/salvar', methods=['POST'])
@login_required
def salvar_atribuicao():
    dados = request.get_json()
    
    id_motorista = dados.get('id_motorista')
    id_veiculo = dados.get('id_veiculo')
    data = dados.get('data')
    hora = dados.get('hora')
    
    if not all([id_motorista, id_veiculo, data, hora]):
        return jsonify({"erro": "Preencha todos os campos"}), 400
        
    # Concatena data e hora para o formato DATETIME do MySQL
    data_hora_emprestimo = f"{data} {hora}:00"
    
    sql = """
        INSERT INTO MotoristaVeiculo (ID_MOTORISTA, ID_VEICULO, DATA_HORA_EMPRESTIMO) 
        VALUES (%s, %s, %s)
    """
    params = (id_motorista, id_veiculo, data_hora_emprestimo)
    
    if executar_query_escrita(sql, params):
        return jsonify({"sucesso": True}), 201
    
    return jsonify({"erro": "Erro ao salvar atribuição"}), 500



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