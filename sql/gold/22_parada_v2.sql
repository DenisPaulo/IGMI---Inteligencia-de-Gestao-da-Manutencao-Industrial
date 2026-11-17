-- Visão diária: soma por OS + dia (lançamentos continuam separados na silver).
CREATE OR REPLACE TABLE gold.parada_diaria AS
SELECT os_ref, CAST(hora_inicio AS DATE) data_parada, CAST(sum(duracao_min) AS INTEGER) minutos, count(*) lancamentos
FROM silver.parada GROUP BY ALL;

-- QCP09: os_ref sem OS no conector (sem custo).
CREATE OR REPLACE TABLE gold.fila_parada_sem_os AS
SELECT p.id_lancamento, p.os_ref, p.duracao_min, p._arquivo, p.data_carga
FROM silver.parada p LEFT JOIN silver.tasks t ON t.task_short_id = p.os_ref
WHERE t.task_id IS NULL;

-- QCP13: id vigente ausente do último export completo -> candidato (nunca apagado sozinho).
CREATE OR REPLACE TABLE gold.fila_candidato_exclusao AS
WITH c AS (SELECT max(data_carga) d FROM meta.parada_cargas WHERE tipo = 'completo' AND status IN ('OK', 'SEM_MUDANCA'))
SELECT p.id_lancamento, p.os_ref, p.duracao_min, (SELECT d FROM c) data_completo
FROM silver.parada p
WHERE (SELECT d FROM c) IS NOT NULL
  AND (SELECT min(data_carga) FROM silver.parada_linhas l WHERE l.id_lancamento = p.id_lancamento) < (SELECT d FROM c)
  AND p.id_lancamento NOT IN (SELECT id_lancamento FROM silver.parada_linhas WHERE data_carga = (SELECT d FROM c));

-- Alertas (marca e segue).
CREATE OR REPLACE TABLE gold.alertas_parada AS
SELECT 'ALERTA_REDUCAO' qc, id_lancamento, 'duracao_min ' || valor_anterior || ' -> ' || valor_novo detalhe, data_carga
FROM silver.parada_auditoria WHERE campo = 'duracao_min' AND CAST(valor_novo AS INTEGER) < CAST(valor_anterior AS INTEGER)
UNION ALL
SELECT 'QCP08', id_lancamento, 'os_ref ' || valor_anterior || ' -> ' || valor_novo, data_carga
FROM silver.parada_auditoria WHERE campo = 'os_ref' AND valor_anterior IS NOT NULL AND valor_novo IS NOT NULL
UNION ALL
SELECT 'QCP09', id_lancamento, 'os_ref ' || os_ref || ' sem OS', data_carga FROM gold.fila_parada_sem_os
UNION ALL
SELECT 'QCP10', id_lancamento, 'hora_inicio ' || CAST(hora_inicio AS VARCHAR) || ' depois da carga ' || CAST(data_carga AS VARCHAR), data_carga
FROM silver.parada WHERE CAST(hora_inicio AS DATE) > data_carga
UNION ALL
SELECT 'QCP11', b.id_lancamento, 'sobrepõe ' || a.id_lancamento || ' na OS ' || a.os_ref, b.data_carga
FROM silver.parada a JOIN silver.parada b ON a.os_ref = b.os_ref AND a.id_lancamento < b.id_lancamento
 AND a.hora_inicio < b.hora_inicio + to_minutes(b.duracao_min) AND b.hora_inicio < a.hora_inicio + to_minutes(a.duracao_min)
UNION ALL
SELECT 'QCP12', id_lancamento, 'exclusão de id nunca carregado', data_carga
FROM silver.parada_versoes WHERE versao = 1 AND acao = 'excluir'
UNION ALL
SELECT 'QCP13', id_lancamento, 'ausente do export completo de ' || CAST(data_completo AS VARCHAR), data_completo
FROM gold.fila_candidato_exclusao;
