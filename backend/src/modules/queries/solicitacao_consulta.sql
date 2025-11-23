SELECT 
    -- IDs CRUCIAIS PARA O BANCO DE DADOS
    sc.ID_SOLICITACAO_CONSULTA,
    sc.ID_PACIENTE,
    p.NOME_PACIENTE,
    
    -- Dados da CONSULTA
    sc.DATA_HORA_CONSULTA,
    sc.ACOMPANHANTE,
    sc.MACA,
    
    -- DADOS DA COLETA (Casa do Paciente - ORIGEM)
    e_origem.ID_ENDERECO AS ID_END_COLETA,
    e_origem.LATITUDE AS LAT_COLETA,
    e_origem.LONGITUDE AS LON_COLETA,
    -- (Opcional: Trazendo o nome da rua só para debug visual, se quiser)
    r_origem.NOME_RUA AS RUA_COLETA, 
    
    -- DADOS DA ENTREGA (Local de Atendimento - DESTINO)
    e_destino.ID_ENDERECO AS ID_END_ENTREGA,
    e_destino.LATITUDE AS LAT_ENTREGA,
    e_destino.LONGITUDE AS LON_ENTREGA,
    la.NOME_LOCAL_ATENDIMENTO

FROM SolicitacaoConsulta sc
-- 1. Pega dados do Paciente
INNER JOIN Paciente p ON sc.ID_PACIENTE = p.ID_PACIENTE

-- 2. Pega Endereço de Origem (Casa) e suas coordenadas
INNER JOIN Endereco e_origem ON sc.ID_ENDERECO = e_origem.ID_ENDERECO
INNER JOIN Rua r_origem ON e_origem.ID_RUA = r_origem.ID_RUA

-- 3. Pega Local de Atendimento e Endereço de Destino e suas coordenadas
INNER JOIN LocalAtendimento la ON sc.ID_LOCAL_ATENDIMENTO = la.ID_LOCAL_ATENDIMENTO
INNER JOIN Endereco e_destino ON la.ID_ENDERECO = e_destino.ID_ENDERECO

WHERE 
    DATE(sc.DATA_HORA_CONSULTA) = %s
    AND sc.ID_STATUS = 5 -- (IMPORTANTE: Apenas solicitações Pendentes)