"""Teste dos testes: cada defeito injetado tem que derrubar o check certo."""
import pytest

from pmb import quality

BY_ID = {c.id: c for c in quality.CHECKS}


def falhas(con):
    return {r["id"] for r in quality.run(con) if not r["ok"]}



FAULTS = {
    "mttr_fato_os_denominador_de_outro_conjunto": ("UPDATE gold.kpi_mttr_tecnico SET os_n = 1, mttr_h = round(esforco_min / 60.0, 2)", {"QC14"}),
    "custo_fato_os_taxa_fixa_errada": ("UPDATE gold.fato_os SET custo_parada = 999 WHERE task_id = 'SINT-T0001'", {"QC02"}),
    "custo_sem_parada_real": ("UPDATE gold.fato_os SET custo_parada = 10 WHERE task_id = 'SINT-T0002'", {"QC01"}),
    "custo_fora_da_celula": ("UPDATE gold.fato_os SET custo_parada = 50 WHERE task_id = 'SINT-T0005'", {"QC02", "QC03"}),
    "estimativa_como_parada": ("UPDATE gold.fato_os SET hora_parada_min = 60 WHERE task_id = 'SINT-T0002'", {"QC04", "QCV04"}),
    "custo_em_pendente": ("UPDATE gold.fato_os SET custo_parada = round(45 / 60.0 * 1000, 2) WHERE task_id = 'SINT-T0003'", {"QC02", "QC05"}),
    "preventiva_no_pareto": ("UPDATE gold.fato_os SET conta_no_pareto = true WHERE task_id = 'SINT-T0002'", {"QC15"}),
}


@pytest.mark.parametrize("nome", FAULTS)
def test_defeito_injetado_falha_o_check_certo(con, nome):
    sql, esperado = FAULTS[nome]
    con.execute(sql)
    assert falhas(con) == esperado


def test_qc02_le_a_taxa_do_seed(con):
    # custo calculado com a taxa atual passa; se o seed muda, o mesmo custo passa a falhar
    assert "QC02" not in falhas(con)          # SINT-T0001 já tem custo calculado com a taxa do seed
    con.execute("UPDATE seed.custo_hora_celula SET custo_hora = 1000 WHERE celula = 'SINT-A'")
    assert "QC02" in falhas(con)



def test_qc12_task_duplicada_na_mesma_carga(build, entrada_copia):
    t = entrada_copia / "tasks.csv"
    linhas = t.read_text(encoding="utf-8").splitlines(keepends=True)
    t.write_text("".join(linhas + [linhas[1]]), encoding="utf-8")
    assert "QC12" in falhas(build(entrada=entrada_copia))


@pytest.mark.parametrize("troca", [("task_short_id", "short_id"), ("cost_center", None)])
def test_qc13_coluna_renomeada_ou_faltando_para_a_carga(build, entrada_copia, tmp_path, troca):
    velho, novo = troca
    arq = "equipments.csv" if velho == "cost_center" else "tasks.csv"
    p = entrada_copia / arq
    linhas = p.read_text(encoding="utf-8").splitlines()
    cab = linhas[0].split(",")
    if novo:
        cab[cab.index(velho)] = novo
        linhas[0] = ",".join(cab)
    else:
        i = cab.index(velho)
        linhas = [",".join(c for j, c in enumerate(l.split(",")) if j != i) for l in linhas]
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    con = build(entrada=entrada_copia)
    assert con.sql("SELECT status FROM meta.carga").fetchone()[0] == "SCHEMA_QUEBRADO"
    assert not (tmp_path / "raw" / "tasks").exists()   # nenhuma partição do conector gravada
    f = falhas(con)
    assert "QC13" in f

