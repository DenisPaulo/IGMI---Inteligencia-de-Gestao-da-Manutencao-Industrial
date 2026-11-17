"""Pipeline limpo: todos os QC verdes e números da fato_os conferidos."""
import re

from pmb import config, quality


def test_todos_os_checks_verdes(con):
    falhas = [r for r in quality.run(con) if not r["ok"]]
    assert falhas == []


def test_ids_unicos():
    ids = [c.id for c in quality.CHECKS]
    assert len(ids) == len(set(ids))



def test_taxa_nao_esta_fixa_no_codigo():
    taxa = config.parametros().get("custo_hora")  # não existe: a taxa mora em custo_hora_celula.csv
    assert taxa is None
    for f in list((config.ROOT / "pmb").glob("*.py")) + list(config.SQL.rglob("*.sql")):
        assert not re.search(r"120[.,]00", f.read_text(encoding="utf-8")), f"taxa fixa em {f}"


def test_fato_os_filtro_quebra_e_mttr(con):
    q = dict(con.sql("SELECT task_id, escopo_quebra FROM gold.fato_os").fetchall())
    assert q == {"SINT-T0001": True, "SINT-T0002": False, "SINT-T0003": True, "SINT-T0005": True, "SINT-T0006": False}
    assert con.sql("SELECT os_n, esforco_min, mttr_h FROM gold.kpi_mttr_tecnico").fetchone() == (2, 165, 1.38)
    # custo só em parada real (csv_producao) de OS completed com taxa no seed: só a SINT-T0001 (80 min × 120,00/h)
    assert con.sql("SELECT task_id, hora_parada_min, custo_parada FROM gold.fato_os WHERE custo_parada IS NOT NULL").fetchall() == [("SINT-T0001", 80, __import__("decimal").Decimal("160.00"))]
