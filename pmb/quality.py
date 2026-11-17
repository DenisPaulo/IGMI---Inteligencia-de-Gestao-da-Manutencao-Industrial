"""Checks (SQL) do formato do repo de referência: Check(id, area, descricao, sql, esperado).
Todo QC é bloqueante: se um falha, o run.py sai com código != 0 e nada é publicado.
Nenhum valor de negócio fixo aqui: taxas e parâmetros vêm de seeds/."""
from dataclasses import dataclass

from pmb import config


@dataclass
class Check:
    id: str
    area: str
    descricao: str
    sql: str
    esperado: object


CHECKS: list[Check] = [
    # --- Proibições da fato_os (D4) ---
    Check("QC01", "fato_os", "custo sem hora de parada real (origem csv_producao) = 0",
          "SELECT count(*) FROM gold.fato_os WHERE custo_parada IS NOT NULL AND (hora_parada_min IS NULL OR origem_parada IS DISTINCT FROM 'csv_producao')", 0),
    Check("QC02", "fato_os", "custo ≠ parada × taxa do centro de custo (taxa lida do seed custo_hora_celula) = 0",
          "SELECT count(*) FROM gold.fato_os f LEFT JOIN seed.custo_hora_celula c ON c.cost_center = f.linha "
          "WHERE f.custo_parada IS NOT NULL AND (c.custo_hora IS NULL OR f.custo_parada <> round(f.hora_parada_min / 60.0 * c.custo_hora, 2))", 0),
    Check("QC03", "fato_os", "custo fora de centro de custo com custo/h no seed = 0",
          "SELECT count(*) FROM gold.fato_os f LEFT JOIN seed.custo_hora_celula c ON c.cost_center = f.linha WHERE f.custo_parada IS NOT NULL AND c.cost_center IS NULL", 0),
    Check("QC04", "fato_os", "hora de parada sem origem (estimativa usada como parada) = 0",
          "SELECT count(*) FROM gold.fato_os WHERE hora_parada_min IS NOT NULL AND origem_parada IS NULL", 0),
    Check("QC05", "fato_os", "custo em OS pendente ou cancelada = 0",
          "SELECT count(*) FROM gold.fato_os WHERE custo_parada IS NOT NULL AND status <> 'completed'", 0),
    Check("QC07", "fato_os", "texto longo na gold (> 120) = 0",
          "SELECT count(*) FROM gold.fato_os WHERE length(descricao) > 120 OR length(execucao) > 120", 0),
    # --- Medidas nunca somadas ---
    Check("QC11a", "gold", "medidas nunca somadas: coluna gold fora da lista permitida (seeds/colunas_permitidas_gold.csv) = 0",
          "SELECT count(*) FROM information_schema.columns c LEFT JOIN seed.colunas_permitidas_gold p "
          "ON p.tabela = c.table_name AND p.coluna = c.column_name WHERE c.table_schema = 'gold' AND p.coluna IS NULL", 0),
    # --- ex-QD11 e ex-QD13, promovidos a QC (bloqueantes) ---
    Check("QC12", "carga", "(ex-QD11) task_id duplicado na mesma data_carga = 0",
          "SELECT count(*) FROM (SELECT task_id, data_carga FROM raw.tasks GROUP BY ALL HAVING count(*) > 1)", 0),
    Check("QC13", "carga", "(ex-QD13) coluna do contrato faltando, renomeada, fora de ordem ou arquivo ausente = 0",
          "SELECT count(*) FROM meta.schema_diff WHERE problema IN ('arquivo_ausente','faltando','fora_de_ordem')", 0),
    # --- MTTR: numerador e denominador do mesmo conjunto ---
    Check("QC14", "mttr", "MTTR técnico: denominador = OS do MESMO conjunto e mttr = esforço ÷ OS (violações = 0)",
          """SELECT (SELECT count(*) FROM gold.kpi_mttr_tecnico k WHERE
                       k.os_n <> (SELECT count(*) FROM gold.fato_os WHERE escopo_quebra AND status = 'completed' AND tempo_tecnico_min IS NOT NULL)
                       OR k.esforco_min IS DISTINCT FROM (SELECT sum(tempo_tecnico_min) FROM gold.fato_os WHERE escopo_quebra AND status = 'completed')
                       OR k.mttr_h IS DISTINCT FROM round(k.esforco_min / 60.0 / nullif(k.os_n, 0), 2))""", 0),
    Check("QC15", "fato_os", "OS fora do escopo de quebra ($corrective) contando no Pareto ou no MTTR = 0",
          "SELECT count(*) FROM gold.fato_os WHERE NOT escopo_quebra AND conta_no_pareto", 0),
    # --- Parada v2 (contrato PROPOSTO; amostras SINTÉTICAS). QCP01–13 por arquivo/linha estão em pmb/parada_v2.py e gold.alertas_parada ---
    Check("QCV01", "parada_v2", "linhas na crua vindas de arquivo rejeitado (QCP01–07) = 0",
          "SELECT count(*) FROM raw.parada_v2 r JOIN meta.parada_cargas c ON c.arquivo = r._arquivo WHERE c.status = 'REJEITADO'", 0),
    Check("QCV02", "parada_v2", "silver.parada: id_lancamento duplicado (mais de uma versão vigente) = 0",
          "SELECT count(*) - count(DISTINCT id_lancamento) FROM silver.parada", 0),
    Check("QCV03", "parada_v2", "vigente com os_ref, hora_inicio ou duracao_min inválidos = 0",
          "SELECT count(*) FROM silver.parada WHERE NOT regexp_full_match(coalesce(os_ref, ''), '[0-9a-f]{8}') OR hora_inicio IS NULL OR duracao_min IS NULL OR duracao_min <= 0", 0),
    Check("QCV04", "parada_v2", "fato_os.hora_parada_min ≠ Σ duracao_min vigente por OS (reconciliação) = 0",
          "SELECT count(*) FROM gold.fato_os f FULL JOIN (SELECT t.task_id, sum(p.duracao_min) m FROM silver.parada p JOIN silver.tasks t ON t.task_short_id = p.os_ref "
          "JOIN gold.fato_os g ON g.task_id = t.task_id GROUP BY 1) s USING (task_id) WHERE f.hora_parada_min IS DISTINCT FROM s.m", 0),
    Check("QCV05", "parada_v2", "visão diária: Σ minutos = Σ duracao_min vigente (soma por OS + dia, sem perder lançamento)",
          "SELECT (SELECT coalesce(sum(minutos), 0) FROM gold.parada_diaria) = (SELECT coalesce(sum(duracao_min), 0) FROM silver.parada)", True),
    Check("QCV06", "parada_v2", "candidato a exclusão (QCP13) apagado sozinho da silver = 0",
          "SELECT count(*) FROM gold.fila_candidato_exclusao c LEFT JOIN silver.parada p USING (id_lancamento) WHERE p.id_lancamento IS NULL", 0),
    Check("QCV07", "parada_v2", "hora de parada em OS não sintética nesta etapa = 0",
          "SELECT count(*) FROM gold.fato_os WHERE hora_parada_min IS NOT NULL AND NOT starts_with(task_id, 'SINT-')", 0),
]


def run(con, checks=None):
    out = []
    for c in checks or CHECKS:
        try:
            obs = con.sql(c.sql).fetchone()[0]
            ok = obs == c.esperado
        except Exception as e:   # tabela ausente (ex.: carga bloqueada) = falha, nunca "passa"
            obs, ok = f"ERRO: {type(e).__name__}", False
        out.append({"id": c.id, "area": c.area, "descricao": c.descricao, "esperado": c.esperado, "observado": obs, "ok": ok})
    return out


def report(res, path=None):
    path = path or config.REPORT
    n_ok = sum(r["ok"] for r in res)
    lines = ["# Relatório de qualidade (gerado; não versionado)", "",
             f"**{n_ok}/{len(res)} checks OK.** Todo QC é bloqueante.", "",
             "| id | área | descrição | esperado | observado | ok |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['area']} | {r['descricao']} | {r['esperado']} | {r['observado']} | {'✅' if r['ok'] else '❌'} |" for r in res]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return n_ok
