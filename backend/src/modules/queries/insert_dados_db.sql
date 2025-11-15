-- Inserindo dados nas tabelas sem dependências

-- Tabela: Motorista
INSERT INTO Motorista (NOME_MOTORISTA, CPF_MOTORISTA, CATEGORIA_CNH, FOTO_PERFIL) VALUES
('João Silva', '11122233344', 'D', NULL),
('Carlos Pereira', '55566677788', 'D', NULL),
('Ana Souza', '99988877766', 'B', NULL),
('Mariana Costa', '33344455522', 'AB', NULL);

-- Tabela: TipoVeiculo
INSERT INTO TipoVeiculo (NOME_TIPO_VEICULO, MACA) VALUES
('Ambulância', TRUE),
('Van Adaptada', TRUE),
('Carro de Passeio', FALSE),
('Micro-ônibus', FALSE);

-- Tabela: StatusGeral
INSERT INTO StatusGeral (NOME_STATUS) VALUES
('Disponível'),
('Em Rota'),
('Em Manutenção'),
('Inativo');

-- Tabela: Estado
INSERT INTO Estado (NOME_ESTADO) VALUES
('SP'),
('RJ'),
('MG'),
('PR');

-- Tabela: TipoConsulta
INSERT INTO TipoConsulta (DESCRICO_CONSULTA) VALUES
('Fisioterapia'),
('Quimioterapia'),
('Hemodiálise'),
('Consulta de Rotina');

-- Tabela: NivelAcesso
INSERT INTO NivelAcesso (NIVEL_ACESSO) VALUES
('Administrador'),
('Gestor de Frota'),
('Atendente'),
('Motorista');

-- Inserindo dados nas tabelas com dependências (Nível 1)

-- Tabela: Veiculo
-- (Depende de TipoVeiculo e StatusGeral)
INSERT INTO Veiculo (ID_TIPO_VEICULO, ID_STATUS, CAPACIDADE) VALUES
(1, 1, 2), -- Ambulância, Disponível
(2, 1, 8), -- Van Adaptada, Disponível
(3, 1, 4), -- Carro de Passeio, Disponível
(4, 3, 15); -- Micro-ônibus, Em Manutenção

-- Tabela: Cidade
-- (Depende de Estado)
INSERT INTO Cidade (ID_ESTADO, NOME_CIDADE) VALUES
(1, 'São Paulo'),
(2, 'Rio de Janeiro'),
(3, 'Belo Horizonte'),
(1, 'Marília');

-- Tabela: Funcionario
-- (Depende de NivelAcesso)
INSERT INTO Funcionario (ID_NIVEL_ACESSO, NOME_FUNCIONARIO, CPF_FUNCIONARIO, DATA_NASCIMENTO_FUNCIONARIO, TELEFONE) VALUES
(1, 'Ricardo Gomes', '12312312311', '1980-05-10', '11987654321'),
(2, 'Fernanda Lima', '45645645622', '1992-11-20', '21912345678'),
(3, 'Lucas Martins', '78978978933', '1995-02-15', '31988887777'),
(4, 'Beatriz Santos', '10110110144', '1988-09-30', '14991223344');

-- Inserindo dados nas tabelas com dependências (Nível 2)

-- Tabela: Bairro
-- (Depende de Cidade)
INSERT INTO Bairro (ID_CIDADE, NOME_BAIRRO) VALUES
(1, 'Pinheiros'),
(2, 'Copacabana'),
(3, 'Savassi'),
(4, 'Centro');

-- Tabela: MotoristaVeiculo
-- (Depende de Motorista e Veiculo)
INSERT INTO MotoristaVeiculo (ID_MOTORISTA, ID_VEICULO, DATA_HORA_EMPRESTIMO) VALUES
(1, 1, '2025-10-07 08:00:00'),
(2, 2, '2025-10-07 09:00:00'),
(3, 3, '2025-10-07 10:00:00'),
(1, 2, '2025-10-06 14:00:00');

-- Inserindo dados nas tabelas com dependências (Nível 3)

-- Tabela: Rua
-- (Depende de Bairro)
INSERT INTO Rua (ID_BAIRRO, NOME_RUA, CEP) VALUES
(1, 'Rua dos Pinheiros', '05422000'),
(2, 'Avenida Atlântica', '22070002'),
(3, 'Rua Pernambuco', '30130150'),
(4, 'Avenida Sampaio Vidal', '17500021');

-- Inserindo dados nas tabelas com dependências (Nível 4)

-- Tabela: Endereco
-- (Depende de Rua)
INSERT INTO Endereco (ID_RUA, NUMERO_ENDERECO, LATITUDE, LONGITUDE, COMPLEMENTO) VALUES
(1, '100', -23.565890, -46.693740, 'Apto 101'),
(2, '2000', -22.971960, -43.182920, 'Hotel Palace'),
(3, '550', -19.932820, -43.933850, 'Loja B'),
(4, '425', -22.2175, -49.9475, 'Fundos');

-- Inserindo dados nas tabelas com dependências (Nível 5)

-- Tabela: LocalAtendimento
-- (Depende de Endereco)
INSERT INTO LocalAtendimento (ID_ENDERECO, NOME_LOCAL_ATENDIMENTO) VALUES
(1, 'Hospital das Clínicas de São Paulo'),
(2, 'UPA Copacabana'),
(3, 'Santa Casa de Belo Horizonte'),
(4, 'Hospital das Clínicas de Marília');

-- Tabela: Paciente
-- (Depende de Endereco)
INSERT INTO Paciente (ID_ENDERECO, SEXO, NOME_PACIENTE, CPF_PACIENTE, SENHA, DATA_NASCIMENTO, TELEFONE) VALUES
(1, 'M', 'José Ferreira', '11111111111', 'senha123', '1950-01-15', '11999998888'),
(2, 'F', 'Maria Oliveira', '22222222222', 'senha456', '1965-07-22', '21988887777'),
(3, 'M', 'Pedro Almeida', '33333333333', 'senha789', '1982-03-10', '31977776666'),
(4, 'F', 'Clara Medeiros', '44444444444', 'senha101', '2001-12-05', '14966665555');

-- Inserindo dados nas tabelas de junção e transacionais (Nível mais alto de dependência)

-- Tabela: SolicitacaoConsulta
-- (Depende de Paciente, TipoConsulta, Endereco, LocalAtendimento, StatusGeral)
INSERT INTO SolicitacaoConsulta (ID_PACIENTE, ID_TIPO_CONSULTA, ID_ENDERECO, ID_LOCAL_ATENDIMENTO, ID_STATUS, DATA_HORA_IDA, DATA_HORA_RETORNO, DATA_HORA_CONSULTA, ACOMPANHANTE, MACA, INFORMACOES_ADICIONAIS) VALUES
(1, 2, 1, 1, 2, '2025-10-08 09:00:00', '2025-10-08 12:00:00', '2025-10-08 10:00:00', TRUE, TRUE, 'Paciente debilitado'),
(2, 3, 2, 2, 1, '2025-10-09 13:00:00', '2025-10-09 17:00:00', '2025-10-09 14:00:00', FALSE, FALSE, NULL),
(3, 1, 3, 3, 1, '2025-10-10 07:30:00', '2025-10-10 09:00:00', '2025-10-10 08:00:00', TRUE, FALSE, 'Levar cadeira de rodas'),
(4, 4, 4, 4, 2, '2025-10-08 15:00:00', NULL, '2025-10-08 16:00:00', FALSE, TRUE, 'Retorno não será necessário');

-- Tabela: PassageiroVeiculo
-- (Depende de Veiculo e SolicitacaoConsulta)
INSERT INTO PassageiroVeiculo (ID_VEICULO, ID_SOLICITACAO_CONSULTA) VALUES
(1, 1),
(3, 2),
(2, 3),
(1, 4);

-- Tabela: Parada
-- (Depende de Veiculo, Paciente, Endereco)
INSERT INTO Parada (ID_VEICULO, ID_PACIENTE, ID_ENDERECO, TIPO_PARADA, DATA_ROTA, HORA_PARADA) VALUES
(1, 1, 1, 'COLETA', '2025-10-08', '09:00:00'),
(1, 1, 1, 'ENTREGA', '2025-10-08', '12:00:00'),
(2, 3, 3, 'COLETA', '2025-10-10', '07:30:00'),
(2, 3, 3, 'ENTREGA', '2025-10-10', '09:00:00');