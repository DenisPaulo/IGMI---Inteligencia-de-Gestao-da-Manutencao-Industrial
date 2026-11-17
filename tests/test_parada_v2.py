"""Parada v2 (contrato PROPOSTO) sobre amostras SINTÉTICAS: cenários a–g, idempotência, QCP01–13 e injeção de falhas."""
import pytest

from pmb import db, parada_v2, quality

CARGAS = parada_v2.manifesto()
CAB = ",".join(parada_v2.CABECALHO)


def falhas(con):
    return {r["id"] for r in quality.run(con) if not r["ok"]}


@pytest.fixture
def ate(tmp_path):
    """Monta o warehouse com as k primeiras cargas do manifesto, sempre na mesma crua."""
    def _a(k):
        return db.build(raw=tmp_path / "raw", cargas_parada=CARGAS[:k])
    return _a


def horas(con):
    return dict(con.sql("SELECT task_id, hora_parada_min FROM gold.fato_os").fetchall())


def alertas(con):
    return sorted(con.sql("SELECT qc, id_lancamento FROM gold.alertas_parada").fetchall())


def test_a_carga_normal(ate):
    con = ate(1)
    assert horas(con) == {"SINT-T0001": 60, "SINT-T0002": 45, "SINT-T0003": None, "SINT-T0005": 30, "SINT-T0006": 20}
    assert alertas(con) == [] and falhas(con) == set()


def test_b_correcao_mesmo_id_substitui_com_auditoria_e_alerta_de_reducao(ate):
    con = ate(2)
    assert horas(con)["SINT-T0001"] == 50 and horas(con)["SINT-T0005"] == 45
    aud = sorted(con.sql("SELECT id_lancamento, versao, campo, valor_anterior, valor_novo, _arquivo FROM silver.parada_auditoria").fetchall())
    assert aud == [("SINT-L0001", 2, "duracao_min", "60", "50", "parada_2026-10-02_b_correcao.csv"),
                   ("SINT-L0002", 2, "duracao_min", "30", "45", "parada_2026-10-02_b_correcao.csv")]
    assert con.sql("SELECT count(*) FROM silver.parada_auditoria WHERE _sha256 IS NULL OR _loaded_at IS NULL").fetchone()[0] == 0
    assert alertas(con) == [("ALERTA_REDUCAO", "SINT-L0001")]   # só a que reduz


def test_c_exclusao_por_acao_e_exclusao_de_id_nunca_carregado(ate):
    con = ate(3)
    assert horas(con)["SINT-T0006"] is None
    assert con.sql("SELECT count(*) FROM silver.parada WHERE id_lancamento IN ('SINT-L0004', 'SINT-L0099')").fetchone()[0] == 0
    assert con.sql("SELECT campo, valor_anterior, valor_novo FROM silver.parada_auditoria WHERE id_lancamento = 'SINT-L0004'").fetchall() == [("acao", "incluir", "excluir")]
    assert ("QCP12", "SINT-L0099") in alertas(con)


def test_d_mesma_os_mesmo_dia_soma_na_diaria_e_separa_na_silver(ate):
    con = ate(4)
    assert con.sql("SELECT id_lancamento, duracao_min FROM silver.parada WHERE os_ref = 'ffff0001' ORDER BY 1").fetchall() == [("SINT-L0001", 50), ("SINT-L0005", 30)]
    assert con.sql("SELECT minutos, lancamentos FROM gold.parada_diaria WHERE os_ref = 'ffff0001' AND data_parada = DATE '2026-10-01'").fetchone() == (80, 2)
    assert horas(con)["SINT-T0001"] == 80
    assert not any(a[0] == "QCP11" for a in alertas(con))      # 08:10–09:00 e 09:45–10:15 não se sobrepõem


def test_g_alertas_qcp08_a_qcp11(ate):
    con = ate(5)
    a = alertas(con)
    for esperado in [("QCP08", "SINT-L0003"), ("QCP09", "SINT-L0007"), ("QCP10", "SINT-L0008"), ("QCP11", "SINT-L0009")]:
        assert esperado in a
    assert con.sql("SELECT id_lancamento FROM gold.fila_parada_sem_os").fetchall() == [("SINT-L0007",)]
    h = horas(con)
    assert h["SINT-T0002"] is None and h["SINT-T0003"] == 45 and h["SINT-T0005"] == 55 and h["SINT-T0006"] == 20
    assert falhas(con) == set()                                 # alertas marcam e seguem


def test_e_arquivo_invalido_rejeitado_inteiro_sem_gravar(ate, tmp_path):
    antes = horas(ate(5))
    con = ate(6)
    st = con.sql("SELECT status, erros FROM meta.parada_cargas WHERE data_carga = DATE '2026-10-06'").fetchone()
    assert st[0] == "REJEITADO"
    assert all(q in st[1] for q in ("QCP02", "QCP03", "QCP04", "QCP05", "QCP06", "QCP07"))
    assert not (tmp_path / "raw" / "parada_v2" / "data_carga=2026-10-06").exists()
    assert con.sql("SELECT count(*) FROM silver.parada_linhas WHERE starts_with(id_lancamento, 'SINT-L001')").fetchone()[0] == 0
    assert horas(con) == antes and falhas(con) == set()


def test_f_export_completo_id_sumido_vira_candidato_sem_apagar(ate):
    v6 = ate(6).sql("SELECT count(*) FROM silver.parada_versoes").fetchone()[0]
    con = ate(7)
    assert con.sql("SELECT id_lancamento FROM gold.fila_candidato_exclusao").fetchall() == [("SINT-L0009",)]
    assert con.sql("SELECT count(*) FROM silver.parada WHERE id_lancamento = 'SINT-L0009'").fetchone()[0] == 1
    assert con.sql("SELECT count(*) FROM silver.parada_versoes").fetchone()[0] == v6   # completo igual ao vigente: sem versão nova
    assert horas(con)["SINT-T0005"] == 55
    assert falhas(con) == set()


def test_reprocessar_e_idempotente(ate, tmp_path):
    ate(7)
    parts = {p: p.stat().st_mtime_ns for p in (tmp_path / "raw" / "parada_v2").rglob("*.parquet")}
    con = ate(7)
    assert {p: p.stat().st_mtime_ns for p in (tmp_path / "raw" / "parada_v2").rglob("*.parquet")} == parts
    st = dict(con.sql("SELECT status, count(*) FROM meta.parada_cargas GROUP BY 1").fetchall())
    assert st == {"SEM_MUDANCA": 6, "REJEITADO": 1}
    assert con.sql("SELECT count(*), count(DISTINCT (id_lancamento, data_carga)) FROM silver.parada_linhas").fetchone() == (19, 19)
    assert con.sql("SELECT max(versao) FROM silver.parada_versoes").fetchone()[0] == 2


def test_particao_imutavel_com_outro_arquivo_falha(tmp_path):
    import duckdb
    parada_v2.carregar(duckdb.connect(), tmp_path, CARGAS[:1])
    outro = [{**CARGAS[0], "arquivo": CARGAS[1]["arquivo"]}]
    with pytest.raises(FileExistsError):
        parada_v2.carregar(duckdb.connect(), tmp_path, outro)


def test_checks_verdes_com_parada_v2(con):
    assert falhas(con) == set()

# ---- QCP01–07: um defeito por arquivo ----
CASOS = {
    "QCP01_cabecalho": ("id,os_ref,hora_inicio,duracao_min,acao\nSINT-L1,ffff0001,2026-10-01T08:00,10,\n", "QCP01"),
    "QCP01_bom": ("\ufeff" + CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,10,\n", "QCP01"),
    "QCP02_id_vazio": (CAB + "\n,ffff0001,2026-10-01T08:00,10,\n", "QCP02"),
    "QCP03_id_repetido": (CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,10,\nSINT-L1,ffff0001,2026-10-01T09:00,10,\n", "QCP03"),
    "QCP04_os_ref": (CAB + "\nSINT-L1,FFFF0001,2026-10-01T08:00,10,\n", "QCP04"),
    "QCP05_formato": (CAB + "\nSINT-L1,ffff0001,01/10/2026 08:00,10,\n", "QCP05"),
    "QCP05_data_inexistente": (CAB + "\nSINT-L1,ffff0001,2026-02-30T08:00,10,\n", "QCP05"),
    "QCP06_decimal": (CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,1.5,\n", "QCP06"),
    "QCP06_zero": (CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,0,\n", "QCP06"),
    "QCP06_hhmm": (CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,00:20,\n", "QCP06"),
    "QCP07_acao": (CAB + "\nSINT-L1,ffff0001,2026-10-01T08:00,10,apagar\n", "QCP07"),
}


@pytest.mark.parametrize("nome", CASOS)
def test_qcp01_a_07_rejeitam(tmp_path, nome):
    txt, qc = CASOS[nome]
    p = tmp_path / "x.csv"
    p.write_bytes(txt.encode("utf-8"))
    assert set(parada_v2.validar(p)) == {qc}


def test_exclusao_sem_campos_e_valida(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text(CAB + "\nSINT-L1,,,,excluir\n", encoding="utf-8")
    assert parada_v2.validar(p) == {}


# ---- injeção de falhas nos checks QCV ----
FAULTS = {
    "linha_de_rejeitado_na_crua": ("UPDATE meta.parada_cargas SET status = 'REJEITADO' WHERE data_carga = DATE '2026-10-01'", {"QCV01"}),
    "id_vigente_duplicado": ("INSERT INTO silver.parada SELECT * FROM silver.parada WHERE id_lancamento = 'SINT-L0005'", {"QCV02", "QCV04", "QCV05"}),
    "duracao_zero_na_silver": ("UPDATE silver.parada SET duracao_min = 0 WHERE id_lancamento = 'SINT-L0008'", {"QCV03", "QCV04", "QCV05"}),
    "fato_os_nao_reconcilia": ("UPDATE gold.fato_os SET hora_parada_min = 81 WHERE task_id = 'SINT-T0001'", {"QCV04", "QC02"}),
    "diaria_perdeu_lancamento": ("DELETE FROM gold.parada_diaria WHERE os_ref = 'ffff0001'", {"QCV05"}),
    "candidato_apagado_sozinho": ("DELETE FROM silver.parada WHERE id_lancamento = 'SINT-L0009'", {"QCV04", "QCV05", "QCV06"}),
    "parada_em_os_real": ("UPDATE gold.fato_os SET task_id = 'abcdef12' WHERE task_id = 'SINT-T0006'", {"QCV04", "QCV07"}),
}


@pytest.mark.parametrize("nome", FAULTS)
def test_injecao_qcv(con, nome):
    sql, esperado = FAULTS[nome]
    con.execute(sql)
    assert falhas(con) == esperado
