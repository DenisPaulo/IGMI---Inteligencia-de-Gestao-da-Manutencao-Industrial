-- Pareto por modo de falha. Medida configurável (pareto_medida: parada_min | os_n); top N + Outros (sempre por último).
-- XX-OUT (outro/desconhecido) vai para Outros: não é um modo acionável.
CREATE OR REPLACE TABLE gold.pareto_modo AS
WITH v AS (
    SELECT coalesce(linha_id, 'PLANTA') escopo, modo_id,
           sum(CASE p('pareto_medida') WHEN 'os_n' THEN 1 ELSE parada_min END) valor, count(*) os_n
    FROM gold.falhas WHERE modo_id IS NOT NULL GROUP BY GROUPING SETS ((linha_id, modo_id), (modo_id))),
r AS (SELECT *, row_number() OVER (PARTITION BY escopo ORDER BY (modo_id = 'XX-OUT'), valor DESC, modo_id) rk FROM v),
g AS (
    SELECT escopo, CASE WHEN rk <= CAST(p('pareto_top') AS INT) AND modo_id <> 'XX-OUT' THEN modo_id ELSE 'OUTROS' END modo_id,
           sum(valor) valor, sum(os_n) os_n
    FROM r GROUP BY ALL),
o AS (SELECT *, row_number() OVER (PARTITION BY escopo ORDER BY (modo_id = 'OUTROS'), valor DESC, modo_id) ordem FROM g)
SELECT o.escopo, o.ordem, o.modo_id, coalesce(m.nome, 'Outros') modo_nome, coalesce(m.classe_id, '*') classe_id,
       p('pareto_medida') medida, o.valor, o.os_n,
       round(100.0 * o.valor / sum(o.valor) OVER (PARTITION BY o.escopo), 2) pct,
       round(100.0 * sum(o.valor) OVER (PARTITION BY o.escopo ORDER BY o.ordem) / sum(o.valor) OVER (PARTITION BY o.escopo), 2) pct_acumulado
FROM o LEFT JOIN cat.modos_falha m USING (modo_id);

-- Alerta de reincidência: mesma falha (subconjunto + modo) N vezes em X dias (parâmetros reincidencia_n / reincidencia_dias).
-- Um alerta por episódio: dispara na OS que leva a contagem a N; rearma só depois de X dias do último alerta da mesma chave.
CREATE OR REPLACE TABLE gold.alertas_reincidencia AS
WITH RECURSIVE f AS (
    SELECT a.task_id, a.task_short_id, a.equipment_id, a.equipamento_nome, a.equipamento_n2_nome, a.linha_id, a.modo_id, a.criticidade, a.aberta_em,
           (SELECT count(*) FROM gold.falhas b WHERE b.equipment_id = a.equipment_id AND b.modo_id = a.modo_id
              AND b.aberta_em > a.aberta_em - to_days(CAST(p('reincidencia_dias') AS INT)) AND b.aberta_em <= a.aberta_em) n_janela
    FROM gold.falhas a WHERE a.modo_id IS NOT NULL AND a.modo_id <> 'XX-OUT'),
c AS (SELECT *, row_number() OVER (PARTITION BY equipment_id, modo_id ORDER BY aberta_em, task_id) rn
      FROM f WHERE n_janela >= CAST(p('reincidencia_n') AS INT)),
r AS (
    SELECT equipment_id, modo_id, rn, aberta_em ultimo_alerta, true eh_alerta FROM c WHERE rn = 1
    UNION ALL
    SELECT c.equipment_id, c.modo_id, c.rn,
           CASE WHEN c.aberta_em > r.ultimo_alerta + to_days(CAST(p('reincidencia_dias') AS INT)) THEN c.aberta_em ELSE r.ultimo_alerta END,
           c.aberta_em > r.ultimo_alerta + to_days(CAST(p('reincidencia_dias') AS INT))
    FROM r JOIN c ON c.equipment_id = r.equipment_id AND c.modo_id = r.modo_id AND c.rn = r.rn + 1)
SELECT e.linha_id, e.equipment_id, e.equipamento_nome, e.equipamento_n2_nome, e.modo_id, m.nome modo_nome, e.criticidade,
       CASE e.criticidade WHEN 'A' THEN 'alta' WHEN 'B' THEN 'média' ELSE 'baixa' END prioridade,
       e.n_janela ocorrencias, CAST(p('reincidencia_dias') AS INT) janela_dias, e.aberta_em disparado_em, e.task_short_id os_gatilho,
       (SELECT string_agg(b.task_short_id, ', ' ORDER BY b.aberta_em) FROM gold.falhas b
         WHERE b.equipment_id = e.equipment_id AND b.modo_id = e.modo_id
           AND b.aberta_em > e.aberta_em - to_days(CAST(p('reincidencia_dias') AS INT)) AND b.aberta_em <= e.aberta_em) os_lista,
       'abrir OS de melhoria/análise de causa (alta prioridade se criticidade A)' acao_sugerida
FROM c e JOIN r USING (equipment_id, modo_id, rn) JOIN cat.modos_falha m USING (modo_id)
WHERE r.eh_alerta;

-- Qualidade do dado (o painel que impede os outros de mentir).
CREATE OR REPLACE TABLE gold.qualidade_dado AS
SELECT 'falhas sem modo de falha' indicador, count(*) FILTER (WHERE modo_id IS NULL) n, count(*) base FROM gold.falhas
UNION ALL SELECT 'falhas com modo Outro/desconhecido', count(*) FILTER (WHERE modo_id = 'XX-OUT'), count(*) FROM gold.falhas
UNION ALL SELECT 'falhas sem causa, mecanismo ou ação', count(*) FILTER (WHERE causa_id IS NULL OR mecanismo_id IS NULL OR acao_id IS NULL), count(*) FROM gold.falhas
UNION ALL SELECT 'OS concluídas sem apontamento de horas', count(*) FILTER (WHERE status = 'completed' AND n_atividades = 0), count(*) FILTER (WHERE status = 'completed') FROM gold.fato_os_demo
UNION ALL SELECT 'corretivas emergenciais sem parada registrada', count(*) FILTER (WHERE tipo_id = 'CORR-EMG' AND parada_min = 0), count(*) FILTER (WHERE tipo_id = 'CORR-EMG') FROM gold.fato_os_demo WHERE NOT cancelada;
