-- 1 linha por OS (inclusive canceladas, marcadas; os KPIs as excluem). Classificação ISO 14224 vem das tags.
CREATE OR REPLACE TABLE gold.fato_os_demo AS
WITH tg AS (
    SELECT tt.task_id, split_part(g.tag_code, ':', 1) k, split_part(g.tag_code, ':', 2) v
    FROM silver.tasks_tags tt JOIN silver.tags g USING (tag_id) WHERE g.tag_code LIKE '%:%'),
cls AS (
    SELECT task_id, max(v) FILTER (WHERE k = 'tipo') tipo_id, max(v) FILTER (WHERE k = 'modo') modo_id,
           max(v) FILTER (WHERE k = 'causa') causa_id, max(v) FILTER (WHERE k = 'mec') mecanismo_id,
           max(v) FILTER (WHERE k = 'acao') acao_id, max(v) FILTER (WHERE k = 'plano') plano_id,
           count(*) FILTER (WHERE k = 'tipo') n_tipo
    FROM tg GROUP BY 1),
a AS (SELECT task_id, sum(duration_in_minutes) tec_min, count(*) n_ativ, min(started_at) ini FROM silver.activities GROUP BY 1),
pa AS (SELECT t.task_id, sum(p.duracao_min) parada_min, min(p.hora_inicio) parada_ini
       FROM silver.parada_demo p JOIN silver.tasks t ON t.task_short_id = p.os_ref WHERE p.acao = 'incluir' GROUP BY 1)
SELECT t.task_id, t.task_short_id, t.equipment_id, d.nome equipamento_nome, d.nivel, d.equipamento_n2,
       n2.nome equipamento_n2_nome, d.linha_id, d.classe_id, d.criticidade,
       coalesce(pl.especialidade_id, d.especialidade_id, 'MEC') especialidade_id,
       c.tipo_id, ty.planejada, ty.reativa, ty.conta_como_falha, c.n_tipo,
       c.modo_id, c.causa_id, c.mecanismo_id, c.acao_id, c.plano_id,
       t.status, t.status = 'canceled' cancelada, t.status IN ('scheduled', 'in_progress') aberta,
       t.scheduled_from aberta_em, t.scheduled_to programado_ate, t.done_date fechada_em,
       CAST(date_trunc('week', t.scheduled_from) AS DATE) semana_programada,
       CAST(strftime(t.scheduled_from, '%Y-%m') AS VARCHAR) mes,
       CASE WHEN hour(coalesce(pa.parada_ini, t.scheduled_from)) BETWEEN 6 AND 13 THEN 'A'
            WHEN hour(coalesce(pa.parada_ini, t.scheduled_from)) BETWEEN 14 AND 21 THEN 'B' ELSE 'C' END turno,
       coalesce(pl.horas_estimadas, round(epoch(t.scheduled_to - t.scheduled_from) / 3600.0, 2)) horas_estimadas,
       coalesce(a.tec_min, 0) tempo_tecnico_min, coalesce(a.n_ativ, 0) n_atividades, a.ini inicio_atendimento,
       coalesce(pa.parada_min, 0) parada_min,
       round(coalesce(pa.parada_min, 0) / 60.0 * l.custo_hora_parada, 2) custo_parada,
       CASE WHEN t.status IN ('scheduled', 'in_progress')
            THEN greatest(date_diff('day', t.scheduled_from, CAST((SELECT max(data_carga) FROM silver.tasks) AS TIMESTAMP)), 0) END idade_dias,   -- programada no futuro = 0
       left(t.description, 120) descricao
FROM silver.tasks t
JOIN gold.dim_equipamento d USING (equipment_id)
LEFT JOIN gold.dim_equipamento n2 ON n2.equipment_id = d.equipamento_n2
LEFT JOIN cls c USING (task_id)
LEFT JOIN cat.tipos_os ty ON ty.tipo_id = c.tipo_id
LEFT JOIN cat.planos_preventivos pl ON pl.plano_id = c.plano_id
LEFT JOIN a USING (task_id)
LEFT JOIN pa USING (task_id)
LEFT JOIN gold.dim_linha l ON l.linha_id = d.linha_id;

-- Falhas = corretivas (emergenciais e planejadas) não canceladas.
CREATE OR REPLACE VIEW gold.falhas AS
SELECT * FROM gold.fato_os_demo WHERE conta_como_falha AND NOT cancelada;
