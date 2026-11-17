"""Pipeline do dataset de DEMONSTRAÇÃO (100% sintético): monitor de OS e tarefas multi-linha.

Reaproveita a ingestão do conector (pmb/ingest.py, mesmo contrato) e a silver (sql/silver/01_conector.sql);
acrescenta catálogos ISO 14224 (seeds/demo/), paradas no formato do contrato v2 e a gold de KPIs (sql/demo/).
Warehouse separado (warehouse/demo.duckdb): não mistura com o pipeline principal.
"""
from pathlib import Path

import duckdb

from pmb import config, db, ingest, simulador

ENTRADA = simulador.SAIDA / "conector"
PARADAS = simulador.SAIDA / "paradas" / "paradas_demo.csv"
WAREHOUSE = config.WAREHOUSE.parent / "demo.duckdb"
RAW = config.ROOT / "raw_demo"
SQL = config.SQL / "demo"


def carregar_catalogos(con):
    con.sql("CREATE SCHEMA IF NOT EXISTS cat")
    for f in sorted(simulador.SEEDS.glob("*.csv")):
        con.sql(f"CREATE OR REPLACE TABLE cat.{f.stem} AS SELECT * FROM read_csv('{f.as_posix()}', header=true, auto_detect=true)")


def build(path=":memory:", entrada: Path | None = None, raw: Path | None = None, paradas: Path | None = None):
    con = duckdb.connect(str(path))
    db.carregar_seeds(con)
    carregar_catalogos(con)
    r = ingest.carregar(con, entrada or ENTRADA, raw or RAW)
    raw = Path(raw or RAW)
    con.sql("CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS silver; CREATE SCHEMA IF NOT EXISTS gold")
    con.execute("CREATE OR REPLACE TABLE meta.carga AS SELECT ? status, ? data_carga", [r["status"], r.get("data_carga")])
    if r["status"] != "OK":
        return con
    for t in ingest.contrato()["tabelas"]:
        con.sql(f"""CREATE OR REPLACE VIEW raw.{t} AS SELECT * FROM read_parquet('{(raw / t).as_posix()}/*/*.parquet',
                    hive_partitioning=true, hive_types={{'data_carga': DATE}})""")
    con.sql((config.SQL / "silver" / "01_conector.sql").read_text(encoding="utf-8"))
    p = Path(paradas or PARADAS).as_posix()
    con.sql(f"""CREATE OR REPLACE TABLE silver.parada_demo AS
                SELECT id_lancamento, os_ref, CAST(strptime(hora_inicio, '%Y-%m-%dT%H:%M') AS TIMESTAMP) hora_inicio,
                       CAST(duracao_min AS INTEGER) duracao_min, acao
                FROM read_csv('{p}', all_varchar=true, header=true)""")
    for f in sorted(SQL.glob("*.sql")):
        con.sql(f.read_text(encoding="utf-8"))
    return con
