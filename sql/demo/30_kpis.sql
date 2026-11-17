-- KPIs (definições em docs/demo/dicionario_kpis.md). Medidas diferentes ficam em colunas diferentes; nunca somadas entre si.

-- Confiabilidade por equipamento (nível 2; falhas de subconjuntos sobem para o equipamento pai).
CREATE OR REPLACE TABLE gold.kpi_equipamento AS
WITH f AS (
    SELECT equipamento_n2, count(*) falhas, count(*) FILTER (WHERE parada_min > 0) falhas_com_parada,
           sum(parada_min) parada_min, sum(tempo_tecnico_min) FILTER (WHERE status = 'completed') reparo_tecnico_min
    FROM gold.falhas GROUP BY 1)
SELECT e.equipment_id, e.nome, e.linha_id, e.classe_id, e.criticidade,
       coalesce(f.falhas, 0) falhas, coalesce(f.falhas_com_parada, 0) falhas_com_parada, coalesce(f.parada_min, 0) parada_min,
       round(coalesce(f.parada_min, 0) / 60.0, 2) parada_h,
       round(f.parada_min / 60.0 / nullif(f.falhas_com_parada, 0), 2) mttr_h,
       round((l.tempo_programado_h - coalesce(f.parada_min, 0) / 60.0) / nullif(f.falhas, 0), 1) mtbf_h,
       round(1 - coalesce(f.parada_min, 0) / 60.0 / l.tempo_programado_h, 4) disponibilidade,
       round(coalesce(f.parada_min, 0) / 60.0 * l.custo_hora_parada, 2) custo_parada
FROM gold.dim_equipamento e JOIN gold.dim_linha l USING (linha_id) LEFT JOIN f ON f.equipamento_n2 = e.equipment_id
WHERE e.nivel = 'equipamento';

-- Backlog: OS abertas, horas estimadas restantes (estimada - já apontada, mínimo 0) por especialidade.
CREATE OR REPLACE TABLE gold.backlog_os AS
SELECT task_id, task_short_id, linha_id, equipamento_n2_nome, especialidade_id, tipo_id, status, aberta_em, idade_dias,
       greatest(horas_estimadas - tempo_tecnico_min / 60.0, 0) horas_restantes,
       CASE WHEN idade_dias <= 7 THEN '0-7 dias' WHEN idade_dias <= CAST(p('os_envelhecida_dias') AS INT) THEN '8-30 dias' ELSE '> 30 dias' END faixa_idade,
       idade_dias > CAST(p('os_envelhecida_dias') AS INT) envelhecida, descricao
FROM gold.fato_os_demo WHERE aberta;

CREATE OR REPLACE TABLE gold.backlog_especialidade AS
SELECT s.especialidade_id, s.nome, count(b.task_id) os_abertas, round(coalesce(sum(b.horas_restantes), 0), 2) horas_backlog,
       s.horas_backlog_semana capacidade_semana_h,
       round(coalesce(sum(b.horas_restantes), 0) / s.horas_backlog_semana, 2) backlog_semanas
FROM cat.especialidades s LEFT JOIN gold.backlog_os b USING (especialidade_id) GROUP BY s.especialidade_id, s.nome, s.horas_backlog_semana;

-- PM compliance: cada OS de plano é uma ocorrência; no prazo = fechada até aberta_em + tolerância.
CREATE OR REPLACE TABLE gold.pm_ocorrencias AS
SELECT o.task_id, o.task_short_id, o.plano_id, o.linha_id, o.tipo_id, o.mes, o.aberta_em vencimento,
       o.aberta_em + to_days(pl.tolerancia_dias) limite, o.fechada_em,
       CASE WHEN o.fechada_em IS NOT NULL AND o.fechada_em <= o.aberta_em + to_days(pl.tolerancia_dias) THEN 'no_prazo'
            WHEN o.fechada_em IS NOT NULL THEN 'atrasada'
            WHEN o.aberta_em + to_days(pl.tolerancia_dias) < CAST((SELECT max(data_carga) FROM silver.tasks) AS TIMESTAMP) THEN 'vencida_aberta'
            ELSE 'a_vencer' END situacao
FROM gold.fato_os_demo o JOIN cat.planos_preventivos pl USING (plano_id)
WHERE NOT o.cancelada;

CREATE OR REPLACE TABLE gold.kpi_pm AS
SELECT coalesce(linha_id, 'PLANTA') escopo, coalesce(mes, 'período') mes,
       count(*) FILTER (WHERE situacao = 'no_prazo') no_prazo, count(*) FILTER (WHERE situacao = 'atrasada') atrasadas,
       count(*) FILTER (WHERE situacao = 'vencida_aberta') vencidas_abertas, count(*) FILTER (WHERE situacao = 'a_vencer') a_vencer,
       round(count(*) FILTER (WHERE situacao = 'no_prazo') / nullif(count(*) FILTER (WHERE situacao <> 'a_vencer'), 0), 4) pm_compliance
FROM gold.pm_ocorrencias GROUP BY GROUPING SETS ((linha_id, mes), (linha_id), (mes), ());

-- Aderência à programação (semanal): OS planejadas programadas na semana e fechadas na mesma semana.
CREATE OR REPLACE TABLE gold.aderencia_semanal AS
WITH s AS (
    SELECT coalesce(linha_id, 'PLANTA') escopo, semana_programada semana, count(*) programadas,
           count(*) FILTER (WHERE fechada_em IS NOT NULL AND CAST(date_trunc('week', fechada_em) AS DATE) = semana_programada) executadas
    FROM gold.fato_os_demo
    WHERE planejada AND NOT cancelada AND semana_programada <= CAST(p('periodo_fim') AS DATE)
    GROUP BY GROUPING SETS ((linha_id, semana_programada), (semana_programada)))
SELECT *, round(executadas / programadas, 4) aderencia,
       CASE WHEN executadas / programadas < CAST(p('aderencia_min') AS DOUBLE) THEN 'abaixo'
            WHEN executadas / programadas > CAST(p('aderencia_max') AS DOUBLE) THEN 'acima' ELSE 'saudável' END faixa
FROM s;

-- Visão por linha e planta (escopo PLANTA = soma das linhas, mesma fórmula).
CREATE OR REPLACE TABLE gold.kpi_linha AS
WITH base AS (
    SELECT coalesce(o.linha_id, 'PLANTA') escopo,
           count(*) FILTER (WHERE NOT o.cancelada) os_total,
           count(*) FILTER (WHERE o.conta_como_falha AND NOT o.cancelada) falhas,
           count(*) FILTER (WHERE o.conta_como_falha AND NOT o.cancelada AND o.parada_min > 0) falhas_com_parada,
           sum(o.parada_min) parada_min,
           sum(o.custo_parada) custo_parada,
           sum(o.tempo_tecnico_min) FILTER (WHERE o.status = 'completed') horas_tec_min,
           sum(o.tempo_tecnico_min) FILTER (WHERE o.status = 'completed' AND o.planejada) horas_plan_min,
           sum(o.tempo_tecnico_min) FILTER (WHERE o.status = 'completed' AND o.reativa) horas_reat_min,
           count(*) FILTER (WHERE o.aberta) os_abertas,
           count(*) FILTER (WHERE o.aberta AND o.idade_dias > CAST(p('os_envelhecida_dias') AS INT)) os_envelhecidas
    FROM gold.fato_os_demo o GROUP BY ROLLUP (o.linha_id)),
tp AS (SELECT coalesce(linha_id, 'PLANTA') escopo, sum(tempo_programado_h) tempo_programado_h FROM gold.dim_linha GROUP BY ROLLUP (linha_id))
SELECT b.escopo, b.os_total, b.falhas, b.falhas_com_parada, round(b.parada_min / 60.0, 2) parada_h, tp.tempo_programado_h,
       round(1 - b.parada_min / 60.0 / tp.tempo_programado_h, 4) disponibilidade,
       round(b.parada_min / 60.0 / nullif(b.falhas_com_parada, 0), 2) mttr_h,
       round((tp.tempo_programado_h - b.parada_min / 60.0) / nullif(b.falhas, 0), 1) mtbf_h,
       round(b.horas_plan_min / b.horas_tec_min, 4) pct_planejada, round(b.horas_reat_min / b.horas_tec_min, 4) pct_reativa,
       round(b.custo_parada, 2) custo_parada, b.os_abertas, b.os_envelhecidas,
       (SELECT pm_compliance FROM gold.kpi_pm k WHERE k.escopo = b.escopo AND k.mes = 'período') pm_compliance,
       (SELECT round(sum(executadas) / sum(programadas), 4) FROM gold.aderencia_semanal a WHERE a.escopo = b.escopo) aderencia
FROM base b JOIN tp USING (escopo);

-- Tendência mensal por linha.
CREATE OR REPLACE TABLE gold.kpi_mensal AS
SELECT o.mes, o.linha_id, count(*) FILTER (WHERE o.conta_como_falha AND NOT o.cancelada) falhas,
       round(sum(o.parada_min) / 60.0, 2) parada_h,
       round(1 - sum(o.parada_min) / 60.0 / (any_value(l.tempo_programado_h) / any_value(l.dias_periodo) * day(last_day(CAST(o.mes || '-01' AS DATE)))), 4) disponibilidade,
       round(sum(o.tempo_tecnico_min) FILTER (WHERE o.status = 'completed' AND o.reativa) / nullif(sum(o.tempo_tecnico_min) FILTER (WHERE o.status = 'completed'), 0), 4) pct_reativa
FROM gold.fato_os_demo o JOIN gold.dim_linha l USING (linha_id)
WHERE o.mes BETWEEN strftime(CAST(p('periodo_inicio') AS DATE), '%Y-%m') AND strftime(CAST(p('periodo_fim') AS DATE), '%Y-%m')
GROUP BY o.mes, o.linha_id;
