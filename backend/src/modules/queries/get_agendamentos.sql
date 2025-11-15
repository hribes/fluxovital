SELECT
    p.NOME_PACIENTE, p.CPF_PACIENTE,
    sc.DATA_HORA_CONSULTA, sc.DATA_HORA_RETORNO, sc.ACOMPANHANTE, sc.INFORMACOES_ADICIONAIS,
    sg.NOME_STATUS,
    tc.DESCRICO_CONSULTA,
    tv.NOME_TIPO_VEICULO,
    la.NOME_LOCAL_ATENDIMENTO,
    CONCAT(rua_local.NOME_RUA, ', ', end_local.NUMERO_ENDERECO, ' - ', bairro_local.NOME_BAIRRO) AS ENDERECO_LOCAL,
    CONCAT(rua_pac.NOME_RUA, ', ', end_pac.NUMERO_ENDERECO, ' - ', bairro_pac.NOME_BAIRRO) AS ENDERECO_PACIENTE
FROM SolicitacaoConsulta sc
JOIN Paciente p ON sc.ID_PACIENTE = p.ID_PACIENTE
JOIN StatusGeral sg ON sc.ID_STATUS = sg.ID_STATUS
JOIN TipoConsulta tc ON sc.ID_TIPO_CONSULTA = tc.ID_TIPO_CONSULTA
JOIN LocalAtendimento la ON sc.ID_LOCAL_ATENDIMENTO = la.ID_LOCAL_ATENDIMENTO
JOIN Endereco end_local ON la.ID_ENDERECO = end_local.ID_ENDERECO
JOIN Rua rua_local ON end_local.ID_RUA = rua_local.ID_RUA
JOIN Bairro bairro_local ON rua_local.ID_BAIRRO = bairro_local.ID_BAIRRO
JOIN Endereco end_pac ON p.ID_ENDERECO = end_pac.ID_ENDERECO
JOIN Rua rua_pac ON end_pac.ID_RUA = rua_pac.ID_RUA
JOIN Bairro bairro_pac ON rua_pac.ID_BAIRRO = bairro_pac.ID_BAIRRO
LEFT JOIN PassageiroVeiculo pv ON sc.ID_SOLICITACAO_CONSULTA = pv.ID_SOLICITACAO_CONSULTA
LEFT JOIN Veiculo v ON pv.ID_VEICULO = v.ID_VEICULO
LEFT JOIN TipoVeiculo tv ON v.ID_TIPO_VEICULO = tv.ID_TIPO_VEICULO