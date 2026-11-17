-- Views só de leitura para a PRÉVIA do dashboard (python run.py preview). Regras ficam aqui, não no HTML.
CREATE OR REPLACE VIEW gold.preview_os AS
SELECT task_id, task_short_id, equipment_id, equipamento, linha, status,
       status IN ('scheduled', 'in_progress') pendente, escopo_quebra, modo_id,
       tempo_tecnico_min, hora_parada_min, custo_parada
FROM gold.fato_os;

CREATE OR REPLACE VIEW gold.parada_diaria_equip AS
SELECT f.equipment_id, f.equipamento, d.data_parada, CAST(sum(d.minutos) AS INTEGER) minutos
FROM gold.parada_diaria d JOIN gold.fato_os f ON f.task_short_id = d.os_ref
GROUP BY ALL;

-- Soma por linha/equipamento DENTRO de cada medida (parada, técnico, custo); nenhuma coluna soma medidas diferentes.
CREATE OR REPLACE VIEW gold.resumo_linha AS
SELECT coalesce(linha, 'sem linha') linha, equipment_id, equipamento,
       count(*) os_n, count(*) FILTER (WHERE pendente) os_pendentes,
       CAST(sum(tempo_tecnico_min) AS INTEGER) tempo_tecnico_min,
       CAST(sum(hora_parada_min) AS INTEGER) parada_min,
       sum(custo_parada) custo_parada
FROM gold.preview_os GROUP BY ALL;

CREATE OR REPLACE VIEW gold.filas_contadores AS
SELECT 'parada_sem_os' fila, count(*) n FROM gold.fila_parada_sem_os
UNION ALL SELECT 'candidato_exclusao', count(*) FROM gold.fila_candidato_exclusao
UNION ALL SELECT 'alertas', count(*) FROM gold.alertas_parada;

CREATE OR REPLACE VIEW gold.alertas_contadores AS
SELECT qc, count(*) n FROM gold.alertas_parada GROUP BY qc;
