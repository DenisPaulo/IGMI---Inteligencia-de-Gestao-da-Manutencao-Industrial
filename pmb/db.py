"""Monta o warehouse DuckDB: seeds, crua (ingestão), silver e gold."""
from pathlib import Path

import duckdb

from pmb import config, ingest, parada_v2


def _sql_dir(con, d: Path, pattern="*.sql"):
    for f in sorted(d.glob(pattern)):
        con.execute(f.read_text(encoding="utf-8"))


def carregar_seeds(con):
    con.sql("CREATE SCHEMA IF NOT EXISTS seed")
    con.sql(f"CREATE OR REPLACE TABLE seed.parametros AS SELECT * FROM read_csv('{(config.SEEDS / 'parametros.csv').as_posix()}', all_varchar=true)")
    con.sql(f"""CREATE OR REPLACE TABLE seed.custo_hora_celula AS SELECT celula, cost_center, CAST(custo_hora AS DECIMAL(8,2)) custo_hora
               FROM read_csv('{(config.SEEDS / 'custo_hora_celula.csv').as_posix()}', all_varchar=true)""")
    con.sql(f"CREATE OR REPLACE TABLE seed.colunas_permitidas_gold AS SELECT * FROM read_csv('{(config.SEEDS / 'colunas_permitidas_gold.csv').as_posix()}', all_varchar=true)")


def build(path=":memory:", entrada=None, raw=None, cargas_parada=None, pasta_parada=None):
    con = duckdb.connect(str(path))
    carregar_seeds(con)
    r = ingest.carregar(con, entrada, raw)
    raw = Path(raw or config.RAW)
    con.sql("CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS silver; CREATE SCHEMA IF NOT EXISTS gold")
    parada_v2.carregar(con, raw, cargas_parada, pasta_parada)   # parada v2 (amostras SINTÉTICAS)
    if r["status"] == "OK" or any((raw / t).exists() for t in ingest.contrato()["tabelas"]):
        for t in ingest.contrato()["tabelas"]:
            con.sql(f"""CREATE OR REPLACE VIEW raw.{t} AS SELECT * FROM read_parquet('{(raw / t).as_posix()}/*/*.parquet',
                        hive_partitioning=true, hive_types={{'data_carga': DATE}})""")
        _sql_dir(con, config.SQL / "silver")
        _sql_dir(con, config.SQL / "gold", "2*.sql")       # fato_os: só com crua carregada
    con.execute("CREATE SCHEMA IF NOT EXISTS meta")
    con.execute("CREATE OR REPLACE TABLE meta.carga AS SELECT ? status, ? data_carga", [r["status"], r.get("data_carga")])
    return con
