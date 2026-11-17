"""PRÉVIA do dashboard: números do HTML = gold; nenhum total somado entre bases; sem títulos, descrições ou links."""
import json
import re

import pytest

from pmb import preview


@pytest.fixture
def gerado(con, tmp_path):
    out = preview.gerar(con, tmp_path / "p.html")
    txt = out.read_text(encoding="utf-8")
    dados = json.loads(re.search(r'<script id=dados type="application/json">(.*?)</script>', txt, re.S).group(1).replace("<\\/", "</"))
    # texto do dashboard sem o bundle do ECharts
    sem_lib = txt[: txt.index('<script id=dados')] + txt[txt.index("</script>", txt.index('<script id=dados')):].split("<script>", 2)[-1]
    return con, txt, sem_lib, dados


def test_faixa_de_previa_no_topo(gerado):
    _, txt, _, _ = gerado
    assert txt.index(preview.FAIXA.replace("—", "—")) < txt.index("<main>")


def test_numeros_do_html_batem_com_a_gold(gerado):
    con, _, html, _ = gerado
    n, esf, mttr = con.sql("SELECT os_n, esforco_min, mttr_h FROM gold.kpi_mttr_tecnico").fetchone()
    assert (n, esf, float(mttr)) == (2, 165, 1.38)
    for txt in ("1,38 h", "165 min", "<b>2</b>"):
        assert txt in html, txt


def test_nenhum_total_somado(gerado):
    _, _, html, dados = gerado
    for proibido in ("Total", "total geral"):
        assert proibido not in html, proibido
    assert "pareto" not in dados
    assert "reduce(" not in html                      # nada de soma no HTML: totais vêm da gold


def test_sem_titulos_descricoes_links(gerado):
    _, txt, html, dados = gerado
    assert "mobility-work.com" not in txt and "<a " not in html
    assert "[SINTÉTICO] OS" not in txt and "execução de teste" not in txt   # descrições da fato_os não vão
    assert all(set(o) >= {"task_short_id"} and "descricao" not in o and "link" not in o for o in dados["os"])


def test_custo_so_em_parada_com_taxa(gerado):
    _, _, _, dados = gerado
    com_custo = [o for o in dados["os"] if o["custo_parada"] is not None]
    assert [(o["task_short_id"], o["linha"], o["status"]) for o in com_custo] == [("ffff0001", "SINT-CC-A", "completed")]
    assert all(o["hora_parada_min"] for o in com_custo)
