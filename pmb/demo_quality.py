"""Checks (SQL) do dataset demo. Mesmo formato e mesma regra do pipeline principal: todo check é bloqueante."""
from pmb.quality import Check, run  # noqa: F401  (run reexportado para quem importa daqui)


def _p(k):
    return f"(SELECT valor FROM cat.parametros_demo WHERE chave = '{k}')"


N, X = f"CAST({_p('reincidencia_n')} AS INT)", f"CAST({_p('reincidencia_dias')} AS INT)"

CHECKS: list[Check] = [
    # --- carga e cadastro ---
    Check("QD01", "carga", "carga do conector demo OK (contrato conector_v0, sem coluna faltando)",
          "SELECT status = 'OK' FROM meta.carga", True),
    Check("QD02", "cadastro", "task_id ou task_short_id duplicado = 0",
          "SELECT (count(*) - count(DISTINCT task_id)) + (count(*) - count(DISTINCT task_short_id)) FROM silver.tasks", 0),
    Check("QD03", "cadastro", "task_short_id fora do padrão sintético ^dd[0-9a-f]{6}$ = 0",
          "SELECT count(*) FROM silver.tasks WHERE NOT regexp_full_match(task_short_id, 'dd[0-9a-f]{6}')", 0),
    Check("QD04", "cadastro", "OS em equipamento fora do cadastro (hierarquia) = 0",
          "SELECT count(*) FROM silver.tasks t LEFT JOIN cat.equipamentos e USING (equipment_id) WHERE e.equipment_id IS NULL", 0),
    Check("QD05", "cadastro", "hierarquia inválida: pai inexistente, pai em outra linha ou nível fora de linha>equipamento>subconjunto = 0",
          "SELECT count(*) FROM cat.equipamentos e LEFT JOIN cat.equipamentos p ON p.equipment_id = e.pai_id "
          "WHERE (e.nivel = 'linha' AND e.pai_id IS NOT NULL) OR (e.nivel <> 'linha' AND (p.equipment_id IS NULL OR p.linha_id <> e.linha_id "
          "OR (e.nivel = 'equipamento' AND p.nivel <> 'linha') OR (e.nivel = 'subconjunto' AND p.nivel <> 'equipamento')))", 0),
    Check("QD06", "cadastro", "criticidade fora de A/B/C ou especialidade fora do catálogo (equipamentos e subconjuntos) = 0",
          "SELECT count(*) FROM cat.equipamentos e LEFT JOIN cat.especialidades s USING (especialidade_id) "
          "WHERE e.criticidade NOT IN ('A','B','C') OR (e.nivel <> 'linha' AND s.especialidade_id IS NULL)", 0),
    # --- classificação ISO 14224 ---
    Check("QD07", "classificacao", "OS sem exatamente 1 tipo de OS do catálogo = 0",
          "SELECT count(*) FROM gold.fato_os_demo o LEFT JOIN cat.tipos_os t USING (tipo_id) WHERE o.n_tipo IS DISTINCT FROM 1 OR t.tipo_id IS NULL", 0),
    Check("QD08", "classificacao", "falha sem modo, causa, mecanismo ou ação do catálogo = 0",
          "SELECT count(*) FROM gold.falhas f LEFT JOIN cat.modos_falha m USING (modo_id) LEFT JOIN cat.causas c USING (causa_id) "
          "LEFT JOIN cat.mecanismos k USING (mecanismo_id) LEFT JOIN cat.acoes a USING (acao_id) "
          "WHERE m.modo_id IS NULL OR c.causa_id IS NULL OR k.mecanismo_id IS NULL OR a.acao_id IS NULL", 0),
    Check("QD09", "classificacao", "modo de falha de outra classe de equipamento (ex.: modo de robô num transportador) = 0",
          "SELECT count(*) FROM gold.falhas f JOIN cat.modos_falha m USING (modo_id) WHERE m.classe_id <> '*' AND m.classe_id <> f.classe_id", 0),
    Check("QD10", "classificacao", "uso do modo Outro/desconhecido acima do limite pct_outros_max = 0",
          f"SELECT (count(*) FILTER (WHERE modo_id = 'XX-OUT') > CAST({_p('pct_outros_max')} AS DOUBLE) * count(*))::INT FROM gold.falhas", 0),
    Check("QD11", "classificacao", "OS de plano em equipamento diferente do plano, ou plano com tipo diferente da OS = 0",
          "SELECT count(*) FROM gold.fato_os_demo o JOIN cat.planos_preventivos p USING (plano_id) WHERE p.equipment_id <> o.equipment_id OR p.tipo_id <> o.tipo_id", 0),
    # --- datas, status e apontamentos ---
    Check("QD12", "status", "concluída sem data de fechamento, aberta com data de fechamento ou fechamento antes da abertura = 0",
          "SELECT count(*) FROM gold.fato_os_demo WHERE (status = 'completed' AND (fechada_em IS NULL OR fechada_em < aberta_em)) "
          "OR (status <> 'completed' AND fechada_em IS NOT NULL)", 0),
    Check("QD13", "status", "concluída sem apontamento, ou cumulated_duration ≠ Σ atividades = 0",
          "SELECT (SELECT count(*) FROM gold.fato_os_demo WHERE status = 'completed' AND n_atividades = 0) + "
          "(SELECT count(*) FROM silver.tasks t LEFT JOIN (SELECT task_id, sum(duration_in_minutes) m FROM silver.activities GROUP BY 1) a USING (task_id) "
          "WHERE t.cumulated_duration_in_minutes IS DISTINCT FROM coalesce(a.m, 0))", 0),
    Check("QD14", "status", "apontamento por nome de pessoa (fora das funções de seeds/demo/tecnicos.csv) = 0",
          "SELECT count(*) FROM silver.activities a WHERE NOT EXISTS (SELECT 1 FROM cat.tecnicos t WHERE starts_with(a.name, t.funcao || ' · '))", 0),
    Check("QD15", "status", "fechamento ou apontamento depois da exportação (dado do futuro; programar para o futuro é permitido) = 0",
          f"SELECT (SELECT count(*) FROM silver.tasks WHERE done_date > CAST({_p('export_em')} AS TIMESTAMP)) + "
          f"(SELECT count(*) FROM silver.activities WHERE started_at > CAST({_p('export_em')} AS TIMESTAMP))", 0),
    # --- paradas ---
    Check("QD16", "parada", "parada sem OS, em OS que não é corretiva emergencial, ou duração ≤ 0 = 0",
          "SELECT count(*) FROM silver.parada_demo p LEFT JOIN gold.fato_os_demo o ON o.task_short_id = p.os_ref "
          "WHERE o.task_id IS NULL OR o.tipo_id <> 'CORR-EMG' OR p.duracao_min <= 0", 0),
    Check("QD17", "parada", "paradas sobrepostas na mesma linha (linha em série: parada contada 2x) = 0",
          "SELECT count(*) FROM (SELECT p.*, o.linha_id FROM silver.parada_demo p JOIN gold.fato_os_demo o ON o.task_short_id = p.os_ref) a "
          "JOIN (SELECT p.*, o.linha_id FROM silver.parada_demo p JOIN gold.fato_os_demo o ON o.task_short_id = p.os_ref) b "
          "ON a.linha_id = b.linha_id AND a.id_lancamento < b.id_lancamento "
          "AND a.hora_inicio < b.hora_inicio + to_minutes(b.duracao_min) AND b.hora_inicio < a.hora_inicio + to_minutes(a.duracao_min)", 0),
    # --- KPIs ---
    Check("QD18", "kpi", "disponibilidade, % planejada, % reativa, PM compliance ou aderência fora de [0, 1]; % planejada + % reativa > 1 = 0",
          "SELECT count(*) FROM gold.kpi_linha WHERE NOT (disponibilidade BETWEEN 0 AND 1 AND pct_planejada BETWEEN 0 AND 1 AND pct_reativa BETWEEN 0 AND 1 "
          "AND pm_compliance BETWEEN 0 AND 1 AND aderencia BETWEEN 0 AND 1 AND pct_planejada + pct_reativa <= 1.0001)", 0),
    Check("QD19", "kpi", "PLANTA ≠ Σ linhas (OS, falhas, parada, custo) = 0",
          "SELECT count(*) FROM (SELECT sum(os_total) o, sum(falhas) f, round(sum(parada_h), 2) h, round(sum(custo_parada), 2) c FROM gold.kpi_linha WHERE escopo <> 'PLANTA') s, "
          "gold.kpi_linha p WHERE p.escopo = 'PLANTA' AND (p.os_total <> s.o OR p.falhas <> s.f OR abs(p.parada_h - s.h) > 0.011 OR abs(p.custo_parada - s.c) > 0.011)", 0),
    Check("QD20", "kpi", "MTTR: numerador e denominador do mesmo conjunto (Σ parada ÷ falhas com parada) por equipamento = 0 violações",
          "SELECT count(*) FROM gold.kpi_equipamento k LEFT JOIN (SELECT equipamento_n2, sum(parada_min) m, count(*) FILTER (WHERE parada_min > 0) n FROM gold.falhas GROUP BY 1) f "
          "ON f.equipamento_n2 = k.equipment_id WHERE k.mttr_h IS DISTINCT FROM round(f.m / 60.0 / nullif(f.n, 0), 2)", 0),
    Check("QD21", "kpi", "Σ falhas por equipamento = falhas da linha (nenhuma falha perdida na hierarquia) = 0 violações",
          "SELECT count(*) FROM (SELECT linha_id, sum(falhas) f FROM gold.kpi_equipamento GROUP BY 1) e JOIN gold.kpi_linha l ON l.escopo = e.linha_id WHERE e.f <> l.falhas", 0),
    Check("QD22", "kpi", "custo ≠ parada × custo/h do centro de custo da linha = 0",
          "SELECT count(*) FROM gold.fato_os_demo o JOIN gold.dim_linha l USING (linha_id) WHERE o.custo_parada <> round(o.parada_min / 60.0 * l.custo_hora_parada, 2)", 0),
    Check("QD23", "kpi", "backlog_semanas ≠ horas de backlog ÷ capacidade semanal = 0",
          "SELECT count(*) FROM gold.backlog_especialidade WHERE backlog_semanas <> round(horas_backlog / capacidade_semana_h, 2)", 0),
    Check("QD24", "kpi", "PM: ocorrências classificadas ≠ OS de plano não canceladas = 0",
          "SELECT (SELECT count(*) FROM gold.fato_os_demo WHERE plano_id IS NOT NULL AND NOT cancelada) - "
          "(SELECT no_prazo + atrasadas + vencidas_abertas + a_vencer FROM gold.kpi_pm WHERE escopo = 'PLANTA' AND mes = 'período')", 0),
    Check("QD25", "pareto", "Pareto: Outros por último, % acumulado final = 100, Σ valor = total da medida, por escopo (violações = 0)",
          "SELECT count(*) FROM (SELECT escopo, arg_max(modo_id, ordem) ultimo, max(pct_acumulado) FILTER (WHERE ordem = (SELECT max(ordem) FROM gold.pareto_modo q WHERE q.escopo = x.escopo)) acum, "
          "sum(valor) v FROM gold.pareto_modo x GROUP BY escopo) s "
          "JOIN (SELECT coalesce(linha_id, 'PLANTA') escopo, sum(CASE (SELECT valor FROM cat.parametros_demo WHERE chave = 'pareto_medida') WHEN 'os_n' THEN 1 ELSE parada_min END) v "
          "FROM gold.falhas GROUP BY ROLLUP (linha_id)) t USING (escopo) "
          "WHERE (s.ultimo <> 'OUTROS' AND (SELECT count(*) FROM gold.pareto_modo WHERE modo_id = 'OUTROS' AND escopo = s.escopo) > 0) OR s.acum <> 100 OR s.v <> t.v", 0),
    Check("QD26", "reincidencia", "alerta sem N ocorrências do mesmo subconjunto + modo dentro de X dias = 0",
          f"SELECT count(*) FROM gold.alertas_reincidencia a WHERE (SELECT count(*) FROM gold.falhas f WHERE f.equipment_id = a.equipment_id AND f.modo_id = a.modo_id "
          f"AND f.aberta_em > a.disparado_em - to_days({X}) AND f.aberta_em <= a.disparado_em) < {N}", 0),
    Check("QD27", "reincidencia", "falha com N ocorrências em X dias sem alerta da mesma chave nos X dias anteriores = 0",
          f"SELECT count(*) FROM gold.falhas a WHERE a.modo_id <> 'XX-OUT' AND (SELECT count(*) FROM gold.falhas b WHERE b.equipment_id = a.equipment_id "
          f"AND b.modo_id = a.modo_id AND b.aberta_em > a.aberta_em - to_days({X}) AND b.aberta_em <= a.aberta_em) >= {N} "
          "AND NOT EXISTS (SELECT 1 FROM gold.alertas_reincidencia r WHERE r.equipment_id = a.equipment_id AND r.modo_id = a.modo_id "
          f"AND r.disparado_em <= a.aberta_em AND r.disparado_em >= a.aberta_em - to_days({X}))", 0),
]
