"""Dataset DEMO (sintético): simulador determinístico, checks QD, KPIs e regras (reincidência, Pareto, PM, backlog)."""
import csv
import json
import re
from collections import Counter
from datetime import datetime

import pytest

from pmb import demo, demo_preview, demo_quality, simulador

DADOS = simulador.SAIDA


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    return demo.build(raw=tmp_path_factory.mktemp("raw_demo"))


def _csv(nome, pasta="conector"):
    with open(DADOS / pasta / f"{nome}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def falhas(con):
    return {r["id"] for r in demo_quality.run(con, demo_quality.CHECKS) if not r["ok"]}


# ---------------- simulador ----------------
def test_simulador_deterministico_e_igual_ao_versionado(tmp_path):
    simulador.gerar(tmp_path)
    for f in sorted(DADOS.rglob("*.csv")):
        assert (tmp_path / f.relative_to(DADOS)).read_bytes() == f.read_bytes(), f"{f.name} difere: rode python run.py simular"


def test_volume_periodo_linhas_e_tipos():
    t = _csv("tasks")
    assert 230 <= len(t) <= 280
    datas = [t_["scheduled_from"][:10] for t_ in t if t_["status"] == "completed"]
    assert min(datas) >= "2026-04-01" and max(datas) <= "2026-09-30"
    assert {"-".join(x["equipment_id"].split("-")[:2]) for x in t} == {"LR-01", "LR-02"}
    assert {"completed", "scheduled", "in_progress", "canceled"} == {x["status"] for x in t}
    tags = {g["tag_id"]: g["tag_code"] for g in _csv("tags")}
    tipos = Counter(tags[r["tag_id"]] for r in _csv("tasks_tags") if tags[r["tag_id"]].startswith("tipo:"))
    assert set(tipos) == {"tipo:CORR-EMG", "tipo:CORR-PLN", "tipo:PREV", "tipo:PRED", "tipo:MELH"}
    assert sum(tipos.values()) == len(t)                                   # 1 tipo por OS


def test_sem_pessoas_links_ou_ids_reais():
    funcoes = {r["funcao"] for r in csv.DictReader(open(simulador.SEEDS / "tecnicos.csv", encoding="utf-8"))}
    assert all(re.fullmatch(r"Técnico (Mec|Elet) \d", f) for f in funcoes)
    assert all(a["name"].split(" · ")[0] in funcoes for a in _csv("activities"))
    for f in DADOS.rglob("*.csv"):
        txt = f.read_text(encoding="utf-8")
        assert "http" not in txt and "730PLT" not in txt
    assert all(re.fullmatch(r"DEMO-T\d{4}", x["task_id"]) and re.fullmatch(r"dd[0-9a-f]{6}", x["task_short_id"]) for x in _csv("tasks"))


def test_paradas_so_em_corretiva_emergencial_e_no_contrato_v2():
    p = _csv("paradas_demo", "paradas")
    assert list(p[0]) == ["id_lancamento", "os_ref", "hora_inicio", "duracao_min", "acao"]
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", r["hora_inicio"]) and int(r["duracao_min"]) > 0 for r in p)


# ---------------- checks ----------------
def test_todos_os_checks_demo_verdes(con):
    assert falhas(con) == set()


def test_ids_dos_checks_unicos():
    ids = [c.id for c in demo_quality.CHECKS]
    assert len(ids) == len(set(ids))


DEFEITOS = {
    "modo_de_robo_em_transportador": ("UPDATE gold.fato_os_demo SET modo_id = 'RB-COL' WHERE task_id = (SELECT min(task_id) FROM gold.falhas WHERE classe_id = 'TRANSP')", "QD09"),
    "falha_sem_causa": ("UPDATE gold.fato_os_demo SET causa_id = NULL WHERE task_id = (SELECT min(task_id) FROM gold.falhas)", "QD08"),
    "apontamento_com_nome": ("UPDATE silver.activities SET name = 'Fulano · reparo' WHERE activity_id = (SELECT min(activity_id) FROM silver.activities)", "QD14"),
    "short_id_duplicado": ("UPDATE silver.tasks SET task_short_id = 'dd000001' WHERE task_id = 'DEMO-T0002'", "QD02"),
    "short_id_real": ("UPDATE silver.tasks SET task_short_id = '1a2b3c4d' WHERE task_id = 'DEMO-T0003'", "QD03"),
    "os_sem_tipo": ("UPDATE gold.fato_os_demo SET n_tipo = 0 WHERE task_id = 'DEMO-T0004'", "QD07"),
    "parada_sobreposta": ("INSERT INTO silver.parada_demo SELECT 'DEMO-L9999', os_ref, hora_inicio + INTERVAL 1 MINUTE, 5, 'incluir' FROM silver.parada_demo LIMIT 1", "QD17"),
    "parada_em_preventiva": ("INSERT INTO silver.parada_demo SELECT 'DEMO-L9998', task_short_id, TIMESTAMP '2026-04-02 03:00:00', 5, 'incluir' FROM gold.fato_os_demo WHERE tipo_id = 'PREV' LIMIT 1", "QD16"),
    "custo_com_taxa_errada": ("UPDATE gold.fato_os_demo SET custo_parada = custo_parada + 1 WHERE parada_min > 0 AND task_id = (SELECT min(task_id) FROM gold.fato_os_demo WHERE parada_min > 0)", "QD22"),
    "planta_diferente_da_soma": ("UPDATE gold.kpi_linha SET falhas = falhas + 1 WHERE escopo = 'PLANTA'", "QD19"),
    "mttr_de_outro_conjunto": ("UPDATE gold.kpi_equipamento SET mttr_h = mttr_h + 0.5 WHERE equipment_id = 'LR-01-RB01'", "QD20"),
    "backlog_semanas_errado": ("UPDATE gold.backlog_especialidade SET backlog_semanas = backlog_semanas * 2", "QD23"),
    "alerta_apagado": ("DELETE FROM gold.alertas_reincidencia WHERE equipment_id = 'LR-02-MS01-VEN'", "QD27"),
    "alerta_falso": ("INSERT INTO gold.alertas_reincidencia SELECT * REPLACE ('LR-01-TR02-COR' AS equipment_id) FROM gold.alertas_reincidencia LIMIT 1", "QD26"),
    "pareto_sem_100": ("UPDATE gold.pareto_modo SET pct_acumulado = 99 WHERE modo_id = 'OUTROS' AND escopo = 'LR-01'", "QD25"),
    "disponibilidade_maior_que_1": ("UPDATE gold.kpi_linha SET disponibilidade = 1.2 WHERE escopo = 'LR-01'", "QD18"),
    "hierarquia_quebrada": ("UPDATE cat.equipamentos SET pai_id = 'LR-02-RB01' WHERE equipment_id = 'LR-01-RB01-FER'", "QD05"),
    "fechamento_antes_da_abertura": ("UPDATE gold.fato_os_demo SET fechada_em = aberta_em - INTERVAL 1 DAY WHERE task_id = 'DEMO-T0001'", "QD12"),
}


@pytest.mark.parametrize("nome", DEFEITOS)
def test_defeito_injetado_derruba_o_check_certo(tmp_path, nome):
    c = demo.build(raw=tmp_path / "raw")
    sql, qd = DEFEITOS[nome]
    c.execute(sql)
    assert qd in falhas(c)


def test_carga_com_coluna_faltando_bloqueia(tmp_path):
    import shutil
    e = tmp_path / "conector"
    shutil.copytree(demo.ENTRADA, e)
    t = e / "tasks.csv"
    t.write_text(t.read_text(encoding="utf-8").replace("task_short_id", "short_id", 1), encoding="utf-8")
    c = demo.build(entrada=e, raw=tmp_path / "raw")
    assert c.sql("SELECT status FROM meta.carga").fetchone()[0] == "SCHEMA_QUEBRADO"
    assert "QD01" in falhas(c)


# ---------------- KPIs ----------------
def test_kpis_da_planta(con):
    k = dict(zip(*[[c for c in con.sql("SELECT * FROM gold.kpi_linha WHERE escopo = 'PLANTA'").columns],
                   con.sql("SELECT * FROM gold.kpi_linha WHERE escopo = 'PLANTA'").fetchone()]))
    assert (k["os_total"], k["falhas"], k["falhas_com_parada"]) == (253, 137, 105)
    assert (k["disponibilidade"], k["mtbf_h"], k["mttr_h"]) == (0.985, 54.1, 1.08)
    assert (k["pct_planejada"], k["pct_reativa"], k["pm_compliance"], k["aderencia"]) == (0.6599, 0.3401, 0.6923, 0.7211)
    assert k["pct_planejada"] + k["pct_reativa"] == pytest.approx(1)


def test_disponibilidade_e_mttr_recalculados_direto_do_csv(con):
    """Recalcula fora do SQL, a partir dos arquivos: paradas (min) por linha -> disponibilidade e MTTR."""
    linha = {t["task_short_id"]: "-".join(t["equipment_id"].split("-")[:2]) for t in _csv("tasks")}
    par = Counter()
    n = Counter()
    for p in _csv("paradas_demo", "paradas"):
        par[linha[p["os_ref"]]] += int(p["duracao_min"])
        n[linha[p["os_ref"]]] += 1
    horas_prog = 183 * 24 * 6 / 7
    for l in ("LR-01", "LR-02"):
        disp, mttr = con.sql(f"SELECT disponibilidade, mttr_h FROM gold.kpi_linha WHERE escopo = '{l}'").fetchone()
        assert disp == round(1 - par[l] / 60 / horas_prog, 4)
        assert mttr == round(par[l] / 60 / n[l], 2)


def test_mtbf_por_equipamento(con):
    eq, falhas_, parada, mtbf = con.sql("SELECT equipment_id, falhas, parada_min, mtbf_h FROM gold.kpi_equipamento ORDER BY falhas DESC LIMIT 1").fetchone()
    assert mtbf == round((183 * 24 * 6 / 7 - parada / 60) / falhas_, 1)
    assert con.sql("SELECT sum(falhas) FROM gold.kpi_equipamento").fetchone()[0] == 137


def test_backlog_e_pm(con):
    b = {r[0]: r[1:] for r in con.sql("SELECT especialidade_id, os_abertas, horas_backlog, backlog_semanas FROM gold.backlog_especialidade").fetchall()}
    assert set(b) == {"MEC", "ELE"} and all(v[0] > 0 and v[2] > 0 for v in b.values())
    s = dict(con.sql("SELECT situacao, count(*) FROM gold.pm_ocorrencias GROUP BY 1").fetchall())
    assert s["no_prazo"] > s["atrasada"] > 0 and s["vencida_aberta"] > 0


def test_aderencia_faixa(con):
    f = dict(con.sql("SELECT faixa, count(*) FROM gold.aderencia_semanal WHERE escopo = 'PLANTA' GROUP BY 1").fetchall())
    assert f.get("saudável", 0) > f.get("abaixo", 0)


# ---------------- reincidência e Pareto ----------------
def _alertas(c):
    return [(e, m, d) for e, m, d in c.sql("SELECT equipment_id, modo_id, disparado_em FROM gold.alertas_reincidencia").fetchall()]


@pytest.mark.parametrize("eq,modo,ini,fim", [("LR-01-RB01-FER", "RB-FER", "2026-07-06", "2026-07-17"),
                                             ("LR-02-MS01-VEN", "MS-VEN", "2026-08-03", "2026-08-12"),
                                             ("LR-02-DS01-BIC", "DS-ENT", "2026-05-11", "2026-05-24")])
def test_reincidencias_injetadas_disparam_alerta(con, eq, modo, ini, fim):
    assert any(e == eq and m == modo and ini <= d.strftime("%Y-%m-%d") <= fim for e, m, d in _alertas(con))


def test_3_vezes_em_21_dias_nao_dispara(con):
    assert not any(e == "LR-02-VI01-CAM" and m == "VI-ILU" for e, m, _ in _alertas(con))


def test_regra_configuravel(tmp_path):
    c = demo.build(raw=tmp_path / "raw")
    c.execute("UPDATE cat.parametros_demo SET valor = '6' WHERE chave = 'reincidencia_n'")
    c.sql((demo.SQL / "40_pareto_alertas.sql").read_text(encoding="utf-8"))
    assert _alertas(c) == []
    c.execute("UPDATE cat.parametros_demo SET valor = 'os_n' WHERE chave = 'pareto_medida'")
    c.execute("UPDATE cat.parametros_demo SET valor = '3' WHERE chave = 'pareto_top'")
    c.sql((demo.SQL / "40_pareto_alertas.sql").read_text(encoding="utf-8"))
    r = c.sql("SELECT modo_id, valor FROM gold.pareto_modo WHERE escopo = 'PLANTA' ORDER BY ordem").fetchall()
    assert len(r) == 4 and r[-1][0] == "OUTROS" and sum(v for _, v in r) == 137
    assert falhas(c) == set()


def test_pareto_ordenado_com_outros_no_fim(con):
    r = con.sql("SELECT modo_id, valor, pct_acumulado FROM gold.pareto_modo WHERE escopo = 'PLANTA' ORDER BY ordem").fetchall()
    assert r[-1][0] == "OUTROS" and r[-1][2] == 100.0
    v = [x[1] for x in r[:-1]]
    assert v == sorted(v, reverse=True) and r[0][0] == "MS-VEN"


# ---------------- dashboard ----------------
def test_dashboard(con, tmp_path):
    out = demo_preview.gerar(con, tmp_path / "d.html")
    txt = out.read_text(encoding="utf-8")
    assert demo_preview.FAIXA in txt and "DADOS SINTÉTICOS" in txt
    for k, _ in demo_preview.ABAS:
        assert f'<section id="{k}"' in txt and f'href="#{k}"' in txt
    assert '<meta name="viewport"' in txt and "@media (max-width:720px)" in txt   # celular
    assert 'id="ch-tl"' in txt                                              # linha do tempo por linha
    d = json.loads(re.search(r'<script id="?dados"? type="application/json">(.*?)</script>', txt, re.DOTALL).group(1).replace("<\\/", "</"))
    planta = next(r for r in d["linha"] if r["escopo"] == "PLANTA")
    assert planta["falhas"] == 137 and planta["disponibilidade"] == 0.985
    assert len(d["alertas"]) == con.sql("SELECT count(*) FROM gold.alertas_reincidencia").fetchone()[0]
    assert "mobility-work.com" not in txt
    assert out.stat().st_size < 2_000_000                     # leve: um HTML só, offline
    assert datetime.fromisoformat(d["data_carga"]).year == 2026
    assert d["checks_ok"] == d["checks_total"] == len(demo_quality.CHECKS)


def test_dashboard_sem_resquicio_de_outro_projeto(con, tmp_path):
    """O visual foi reaproveitado; nenhum link, foto, id de OS ou valor real pode vir junto no template."""
    tpl = demo_preview.TEMPLATE.read_text(encoding="utf-8").lower()
    for s in ("http://", "https://", "<img", "data:image", "work-orders", "mobility-work"):
        assert s not in tpl, s
    assert not re.search(r"\b\d{7,}\b", tpl)                 # nada parecido com id real de OS
    html = demo_preview.gerar(con, tmp_path / "d.html").read_text(encoding="utf-8")
    dados = re.search(r'<script id="?dados"? type="application/json">(.*?)</script>', html, re.DOTALL).group(1)
    assert "mobility-work" not in dados and "http" not in dados
