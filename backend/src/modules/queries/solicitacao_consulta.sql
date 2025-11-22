WITH 
endereco_solicitacaoconsulta_endereco_estado AS (
	SELECT
		ID_ESTADO, NOME_ESTADO
    FROM estado
),
endereco_solicitacaoconsulta_endereco_cidade AS (
	SELECT
		ID_CIDADE, NOME_CIDADE, NOME_ESTADO 
	FROM cidade
    LEFT JOIN endereco_solicitacaoconsulta_endereco_estado USING (ID_ESTADO)
),
endereco_solicitacaoconsulta_endereco_bairro AS (
	SELECT
		ID_BAIRRO, NOME_CIDADE, NOME_BAIRRO
    FROM bairro
    LEFT JOIN endereco_solicitacaoconsulta_endereco_cidade USING (ID_CIDADE)
),
endereco_solicitacaoconsulta_endereco_rua AS (
	SELECT 
		ID_RUA, NOME_RUA, CEP, NOME_CIDADE, NOME_BAIRRO
	FROM rua
    LEFT JOIN endereco_solicitacaoconsulta_endereco_bairro USING (ID_BAIRRO)
),
endereco_solicitacaoconsulta_endereco_base AS (
	SELECT
		ID_ENDERECO, NOME_RUA, NUMERO_ENDERECO, NOME_BAIRRO, NOME_CIDADE, CEP
	FROM endereco
    LEFT JOIN endereco_solicitacaoconsulta_endereco_rua USING (ID_RUA)
),
endereco_solicitacaoconsulta_endereco_base_localatendimento AS (
	SELECT
		ID_LOCAL_ATENDIMENTO, 
        NOME_RUA as NOME_RUA_LOCALATENDIMENTO, 
        NUMERO_ENDERECO AS NUMERO_ENDERECO_LOCALATENDIMENTO, 
        NOME_BAIRRO AS NOME_BAIRRO_LOCALATENDIMENTO, 
        NOME_CIDADE AS NOME_CIDADE_LOCALATENDIMENTO, 
        CEP AS CEP_LOCALATENDIMENTO, 
        NOME_LOCAL_ATENDIMENTO
    FROM localatendimento
    LEFT JOIN endereco_solicitacaoconsulta_endereco_base USING (ID_ENDERECO)
)

SELECT 
	ID_PACIENTE, 
    DATA_HORA_CONSULTA,
	DATE_SUB(DATA_HORA_CONSULTA, INTERVAL '20:00' MINUTE_SECOND) AS DATA_HORA_MAX_CHEGADA,
    ACOMPANHANTE, 
    MACA, 
    NOME_RUA, 
    NUMERO_ENDERECO, 
    NOME_BAIRRO, 
    NOME_CIDADE, 
    CEP, 
    NOME_LOCAL_ATENDIMENTO, 
    NOME_RUA_LOCALATENDIMENTO,
    NUMERO_ENDERECO_LOCALATENDIMENTO,
    NOME_BAIRRO_LOCALATENDIMENTO,
    NOME_CIDADE_LOCALATENDIMENTO,
    CEP_LOCALATENDIMENTO
FROM solicitacaoconsulta
LEFT JOIN endereco_solicitacaoconsulta_endereco_base USING (ID_ENDERECO)
LEFT JOIN endereco_solicitacaoconsulta_endereco_base_localatendimento USING (ID_LOCAL_ATENDIMENTO)
WHERE DATE(DATA_HORA_CONSULTA) = %s