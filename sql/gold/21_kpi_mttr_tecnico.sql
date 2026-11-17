-- MTTR técnico = esforço ÷ OS, com numerador e denominador do MESMO conjunto:
-- OS de quebra ($corrective), completed, com tempo do técnico.
CREATE OR REPLACE TABLE gold.kpi_mttr_tecnico AS
SELECT 'quebra_completed' escopo, count(*) os_n, sum(tempo_tecnico_min) esforco_min,
       round(sum(tempo_tecnico_min) / 60.0 / nullif(count(*), 0), 2) mttr_h
FROM gold.fato_os
WHERE escopo_quebra AND status = 'completed' AND tempo_tecnico_min IS NOT NULL;
