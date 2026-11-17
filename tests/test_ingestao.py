"""Ingestão idempotente por task_id + data_carga, só CSV (sem MySQL/credencial)."""
import duckdb

from pmb import config, ingest


def _contagens(raw):
    c = duckdb.connect()
    return c.sql(f"SELECT data_carga, count(*), count(DISTINCT task_id) FROM read_parquet('{(raw / 'tasks').as_posix()}/*/*.parquet', hive_partitioning=true) GROUP BY 1").fetchall()


def test_rodar_duas_vezes_nao_duplica(tmp_path):
    raw = tmp_path / "raw"
    for _ in range(2):
        r = ingest.carregar(duckdb.connect(), raw=raw)
        assert r["status"] == "OK" and r["data_carga"] == "2026-10-12"
    assert [(str(d), n, u) for d, n, u in _contagens(raw)] == [("2026-10-12", 6, 6)]


def test_nova_data_carga_gera_nova_particao_e_silver_le_a_ultima(build, entrada_copia, tmp_path):
    build(entrada=entrada_copia)
    (entrada_copia / "_parameters.csv").write_text("key,value\nlast_export_date,2026-10-13 06:00:00\n", encoding="utf-8")
    con = build(entrada=entrada_copia)
    assert sorted(p.name for p in (tmp_path / "raw" / "tasks").iterdir()) == ["data_carga=2026-10-12", "data_carga=2026-10-13"]
    assert con.sql("SELECT DISTINCT data_carga FROM gold.fato_os").fetchall()[0][0].isoformat() == "2026-10-13"


def test_coluna_nova_no_fim_e_alerta_e_ignorada(build, entrada_copia):
    p = entrada_copia / "equipments.csv"
    linhas = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join([linhas[0] + ",coluna_nova"] + [l + ",x" for l in linhas[1:]]) + "\n", encoding="utf-8")
    con = build(entrada=entrada_copia)
    assert con.sql("SELECT status FROM meta.carga").fetchone()[0] == "OK"
    assert con.sql("SELECT problema FROM meta.schema_diff").fetchall() == [("nova_no_fim",)]
    assert "coluna_nova" not in con.sql("SELECT * FROM raw.equipments").columns


def test_dados_sinteticos_marcados():
    for f in config.ENTRADA_CSV.glob("*.csv"):
        if f.name in ("tasks.csv", "activities.csv", "equipments.csv", "tasks_tags.csv", "tags.csv"):
            for linha in f.read_text(encoding="utf-8").splitlines()[1:]:
                assert linha.startswith("SINT-"), f"{f.name}: linha sem marca SINT-: {linha}"
