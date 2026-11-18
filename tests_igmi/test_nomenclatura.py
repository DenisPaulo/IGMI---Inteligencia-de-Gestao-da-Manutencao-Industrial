"""Regressão da nomenclatura do IGMI 0.3.3 (sem DuckDB nem API)."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from igmi.copiloto import identificar_alvos
from pmb import simulador

RAIZ = Path(__file__).resolve().parents[1]
LINHAS = {"LR-01": "Linha Robotizada_1", "LR-02": "Linha Robotizada_2"}


def _csv(caminho):
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_linhas_e_hierarquia_ficticias_consistentes():
    linhas = _csv(RAIZ / "seeds/demo/linhas.csv")
    assert {x["linha_id"]: x["nome"].replace(" (sintética)", "") for x in linhas} == LINHAS
    centros = {r["cost_center"] for r in _csv(RAIZ / "seeds/demo/centros_custo.csv")}
    assert {x["cost_center"] for x in linhas} <= centros

    equipamentos = _csv(RAIZ / "seeds/demo/equipamentos.csv")
    ids = {e["equipment_id"] for e in equipamentos}
    assert len(ids) == len(equipamentos)
    for e in equipamentos:
        assert e["linha_id"] in LINHAS
        assert e["equipment_id"] == e["linha_id"] or e["equipment_id"].startswith(e["linha_id"] + "-")
        if e["nivel"] == "linha":
            assert e["equipment_id"] == e["linha_id"] and not e["pai_id"]
            assert e["nome"] == LINHAS[e["linha_id"]]
        else:
            assert e["pai_id"] in ids
    planos = _csv(RAIZ / "seeds/demo/planos_preventivos.csv")
    assert all(p["equipment_id"] in ids for p in planos)
    assert all(any(p["plano_id"].startswith("PM-" + l + "-") for l in LINHAS) for p in planos)


def test_simulador_deterministico_preservado_na_migracao():
    with TemporaryDirectory() as raiz_temporaria:
        saida = Path(raiz_temporaria)
        resumo = simulador.gerar(saida)
        assert resumo["os"] == 256
        assert resumo["atividades"] == 354
        assert resumo["paradas"] == 105
        for original in simulador.SAIDA.rglob("*.csv"):
            gerado = saida / original.relative_to(simulador.SAIDA)
            assert gerado.read_bytes() == original.read_bytes(), original.as_posix()


def test_conector_sintetico_tem_referencias_integras():
    c = RAIZ / "dados_sinteticos/demo/conector"
    equipamentos = {r["equipment_id"] for r in _csv(c / "equipments.csv")}
    tasks = _csv(c / "tasks.csv")
    tags = _csv(c / "tags.csv")
    planos = {r["plano_id"] for r in _csv(RAIZ / "seeds/demo/planos_preventivos.csv")}
    assert all(t["equipment_id"] in equipamentos for t in tasks)
    assert {r["tag_code"][6:] for r in tags if r["tag_code"].startswith("plano:")} <= planos
    assert len(tasks) == 256


def test_copiloto_entende_ids_com_prefixo_de_dois_segmentos():
    alvos = identificar_alvos("Compare LR-01-RB01-FER e LR-01-MS01-VEN", "LR-01")
    assert alvos == ("LR-01-RB01", "LR-01-MS01")
    assert identificar_alvos("Investigue o robô e a mesa de ventosas", "LR-02") == (
        "LR-02-RB01", "LR-02-MS01")


def test_referencias_ativas_nao_usam_ids_antigos():
    # Compõe padrões sem colocá-los literalmente no código ou na documentação pública.
    obsoletos = ("LT" + "3", "LT" + "56")
    diretorios = ("pmb", "igmi", "sql", "seeds", "dados_sinteticos", "tests", "tests_igmi")
    for pasta in diretorios:
        for caminho in (RAIZ / pasta).rglob("*"):
            if caminho.suffix not in (".py", ".sql", ".csv", ".json", ".md", ".html"):
                continue
            texto = caminho.read_text(encoding="utf-8")
            assert all(antigo not in texto for antigo in obsoletos), caminho.as_posix()


def test_dashboard_javascript_usa_chaves_entre_aspas_e_rotulos_publicos():
    html = (RAIZ / "pmb/demo_template.html").read_text(encoding="utf-8")
    assert "const LC = {'LR-01':" in html
    assert "L['LR-01'][k]" in html
    assert "L['LR-02'][k]" in html
    assert "Linha Robotizada_1" in html and "Linha Robotizada_2" in html
    assert "e.equipment_id.split('-').slice(2).join('-')" in html
