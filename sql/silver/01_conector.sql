-- silver: tipado, última data_carga válida. Fonte: raw.* (fallback CSV SINTÉTICO nesta entrega).
CREATE OR REPLACE TABLE silver.tasks AS
SELECT task_id, task_short_id, task_legacy_id, equipment_id, status, description,
       CAST(scheduled_from AS TIMESTAMP) scheduled_from, CAST(scheduled_to AS TIMESTAMP) scheduled_to,
       CAST(nullif(done_date, '') AS TIMESTAMP) done_date,
       is_part_of_maintenance_plan = 'true' is_part_of_maintenance_plan,
       CAST(cumulated_duration_in_minutes AS INTEGER) cumulated_duration_in_minutes,
       CAST(nullif(estimated_stop_time, '') AS INTEGER) estimated_stop_time,   -- estimativa: NUNCA vira parada (QC04)
       data_carga
FROM raw.tasks WHERE data_carga = (SELECT max(data_carga) FROM raw.tasks);

CREATE OR REPLACE TABLE silver.activities AS
SELECT activity_id, task_id, name, CAST(started_at AS TIMESTAMP) started_at, CAST(duration_in_minutes AS INTEGER) duration_in_minutes
FROM raw.activities WHERE data_carga = (SELECT max(data_carga) FROM raw.activities);

CREATE OR REPLACE TABLE silver.equipments AS
SELECT equipment_id, name, nullif(cost_center, '') cost_center
FROM raw.equipments WHERE data_carga = (SELECT max(data_carga) FROM raw.equipments);

CREATE OR REPLACE TABLE silver.tasks_tags AS
SELECT DISTINCT task_id, tag_id FROM raw.tasks_tags WHERE data_carga = (SELECT max(data_carga) FROM raw.tasks_tags);

CREATE OR REPLACE TABLE silver.tags AS
SELECT tag_id, tag_code, name FROM raw.tags WHERE data_carga = (SELECT max(data_carga) FROM raw.tags);

-- OS de quebra = tag de sistema $corrective (decisão do líder do projeto, 13/10/2026); o código vem do seed
CREATE OR REPLACE TABLE silver.os_quebra AS
SELECT DISTINCT tt.task_id
FROM silver.tasks_tags tt JOIN silver.tags g USING (tag_id)
WHERE g.tag_code = (SELECT valor FROM seed.parametros WHERE chave = 'tag_quebra');
