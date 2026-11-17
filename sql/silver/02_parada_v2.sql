-- Parada v2 (contrato PROPOSTO; dados SINTÉTICOS). Só arquivos aceitos chegam aqui (rejeitados não vão para a crua).
CREATE OR REPLACE TABLE silver.parada_linhas AS
SELECT r.id_lancamento, nullif(r.os_ref, '') os_ref,
       CAST(strptime(nullif(r.hora_inicio, ''), '%Y-%m-%dT%H:%M') AS TIMESTAMP) hora_inicio,
       CAST(nullif(r.duracao_min, '') AS INTEGER) duracao_min,
       coalesce(nullif(r.acao, ''), 'incluir') acao,
       r._arquivo, r._linha, r._sha256, r._loaded_at, r.data_carga, c.tipo
FROM raw.parada_v2 r JOIN meta.parada_cargas c ON c.data_carga = r.data_carga AND c.arquivo = r._arquivo;

-- Versões: uma linha nova só vira versão se mudar algum valor (export completo que repete o vigente não cria versão).
CREATE OR REPLACE TABLE silver.parada_versoes AS
WITH o AS (
    SELECT *, row_number() OVER w rn,
           lag(os_ref) OVER w p_os, lag(hora_inicio) OVER w p_hi, lag(duracao_min) OVER w p_d, lag(acao) OVER w p_a
    FROM silver.parada_linhas
    WINDOW w AS (PARTITION BY id_lancamento ORDER BY data_carga, _arquivo, _linha)),
k AS (
    SELECT * FROM o
    WHERE rn = 1 OR os_ref IS DISTINCT FROM p_os OR hora_inicio IS DISTINCT FROM p_hi
       OR duracao_min IS DISTINCT FROM p_d OR acao IS DISTINCT FROM p_a)
SELECT id_lancamento, row_number() OVER (PARTITION BY id_lancamento ORDER BY data_carga, _arquivo, _linha) versao,
       os_ref, hora_inicio, duracao_min, acao, _arquivo, _linha, _sha256, _loaded_at, data_carga
FROM k;

-- Vigente por id: última versão; excluída sai da silver (fica na trilha).
CREATE OR REPLACE TABLE silver.parada AS
SELECT id_lancamento, versao, os_ref, hora_inicio, duracao_min, _arquivo, _sha256, _loaded_at, data_carga
FROM silver.parada_versoes v
WHERE versao = (SELECT max(versao) FROM silver.parada_versoes x WHERE x.id_lancamento = v.id_lancamento)
  AND acao = 'incluir';

-- Trilha de auditoria: uma linha por campo alterado em cada versão > 1.
CREATE OR REPLACE TABLE silver.parada_auditoria AS
WITH p AS (
    SELECT n.id_lancamento, n.versao, n._arquivo, n._sha256, n._loaded_at, n.data_carga,
           a.os_ref a_os, n.os_ref n_os, CAST(a.hora_inicio AS VARCHAR) a_hi, CAST(n.hora_inicio AS VARCHAR) n_hi,
           CAST(a.duracao_min AS VARCHAR) a_d, CAST(n.duracao_min AS VARCHAR) n_d, a.acao a_a, n.acao n_a
    FROM silver.parada_versoes n JOIN silver.parada_versoes a ON a.id_lancamento = n.id_lancamento AND a.versao = n.versao - 1)
SELECT id_lancamento, versao, campo, valor_anterior, valor_novo, _arquivo, _sha256, _loaded_at, data_carga FROM (
    SELECT *, 'os_ref' campo, a_os valor_anterior, n_os valor_novo FROM p
    UNION ALL SELECT *, 'hora_inicio', a_hi, n_hi FROM p
    UNION ALL SELECT *, 'duracao_min', a_d, n_d FROM p
    UNION ALL SELECT *, 'acao', a_a, n_a FROM p)
WHERE valor_anterior IS DISTINCT FROM valor_novo AND NOT (campo <> 'acao' AND valor_novo IS NULL AND n_a = 'excluir');

-- Parada por OS (soma dos lançamentos vigentes), só OS existentes no conector.
CREATE OR REPLACE TABLE silver.parada_por_os AS
SELECT t.task_id, CAST(sum(p.duracao_min) AS INTEGER) hora_parada_min, 'csv_producao' origem_parada
FROM silver.parada p JOIN silver.tasks t ON t.task_short_id = p.os_ref
GROUP BY t.task_id;
