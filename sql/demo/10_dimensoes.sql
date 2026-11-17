-- Demo (SINTÉTICO). Parâmetros configuráveis lidos de seeds/demo/parametros_demo.csv.
CREATE OR REPLACE MACRO p(k) AS (SELECT valor FROM cat.parametros_demo WHERE chave = k);

CREATE OR REPLACE TABLE gold.dim_linha AS
SELECT l.linha_id, l.nome, l.planta_id, l.cost_center, c.custo_hora_parada,
       CAST(p('periodo_fim') AS DATE) - CAST(p('periodo_inicio') AS DATE) + 1 dias_periodo,
       round((CAST(p('periodo_fim') AS DATE) - CAST(p('periodo_inicio') AS DATE) + 1) * l.horas_dia * l.dias_semana / 7.0, 2) tempo_programado_h
FROM cat.linhas l JOIN cat.centros_custo c USING (cost_center);

-- Hierarquia linha > equipamento > subconjunto; equipamento_n2 = o equipamento "pai" de cada nó (para somar falhas).
CREATE OR REPLACE TABLE gold.dim_equipamento AS
SELECT e.equipment_id, coalesce(s.name, e.nome) nome, e.nivel, e.pai_id, e.linha_id, e.classe_id, e.criticidade, e.especialidade_id,
       CASE e.nivel WHEN 'subconjunto' THEN e.pai_id WHEN 'equipamento' THEN e.equipment_id END equipamento_n2
FROM cat.equipamentos e LEFT JOIN silver.equipments s USING (equipment_id);
