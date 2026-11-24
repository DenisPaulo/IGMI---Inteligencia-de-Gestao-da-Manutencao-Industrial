-- gold.fato_os: 1 linha por OS não cancelada (planta toda), última data_carga.
-- hora_parada_min = Σ duracao_min dos lançamentos vigentes (contrato v2 PROPOSTO; hoje só amostras SINTÉTICAS);
-- custo só com origem csv_producao, OS completed e centro de custo com custo/h no seed.
-- Classificador de modo fora desta entrega: modo_id nulo -> conta_no_pareto = false.
CREATE OR REPLACE TABLE gold.fato_os AS
WITH a AS (
    SELECT task_id, sum(duration_in_minutes) tec_min, min(started_at) ini,
           string_agg(name, ' | ' ORDER BY started_at) exec_txt
    FROM silver.activities GROUP BY task_id),
p AS (SELECT task_id, hora_parada_min, origem_parada FROM silver.parada_por_os)   -- parada v2 (SINTÉTICA nesta etapa)
SELECT t.task_id, t.task_short_id, t.equipment_id, e.name equipamento, e.cost_center linha, t.status,
       q.task_id IS NOT NULL escopo_quebra,
       CAST(NULL AS INTEGER) modo_id,
       coalesce(t.status = 'completed' AND q.task_id IS NOT NULL AND CAST(NULL AS INTEGER) IS NOT NULL, false) conta_no_pareto,
       p.hora_parada_min, p.origem_parada,
       CASE WHEN t.status = 'completed' THEN a.tec_min END tempo_tecnico_min,     -- esforço; nunca em custo
       CASE WHEN p.origem_parada = 'csv_producao' AND t.status = 'completed'
            THEN CAST(round(p.hora_parada_min / 60.0 * c.custo_hora, 2) AS DECIMAL(12,2)) END custo_parada,
       t.scheduled_from abertura_programada, a.ini inicio_atendimento, t.done_date fechamento,
       CAST(NULL AS VARCHAR) link,
       left(t.description, 120) descricao, left(a.exec_txt, 120) execucao, t.data_carga
FROM silver.tasks t
LEFT JOIN silver.equipments e USING (equipment_id)
LEFT JOIN silver.os_quebra q USING (task_id)
LEFT JOIN a USING (task_id)
LEFT JOIN p USING (task_id)
LEFT JOIN seed.custo_hora_celula c ON c.cost_center = e.cost_center   -- só centros de custo com taxa no seed têm valor
WHERE t.status <> 'canceled';
