"""Ingestão do fallback CSV no schema do Data Connector -> crua particionada por data_carga.

Idempotente por chave (task_id + data_carga): rodar de novo sobre o mesmo export SOBRESCREVE a partição.
data_carga = date(_parameters.last_export_date), não o relógio. Sem MySQL, sem credencial.
"""
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pmb import config


def contrato() -> dict:
    return json.loads((config.CONTRATO / "conector_v0.json").read_text(encoding="utf-8"))


def _header(p: Path) -> list[str]:
    with open(p, encoding="utf-8", newline="") as f:
        return next(csv.reader(f), [])


def schema_diff(entrada: Path) -> list[tuple[str, str, str]]:
    """(tabela, coluna, problema). problema: arquivo_ausente | faltando | fora_de_ordem (bloqueiam) | nova_no_fim (alerta)."""
    out = []
    for t, cols in contrato()["tabelas"].items():
        p = entrada / f"{t}.csv"
        if not p.exists():
            out.append((t, "*", "arquivo_ausente"))
            continue
        h = _header(p)
        out += [(t, c, "faltando") for c in cols if c not in h]
        presentes = [c for c in h if c in cols]
        if presentes != [c for c in cols if c in h] or h[: len(presentes)] != presentes:
            out.append((t, "*", "fora_de_ordem"))
        out += [(t, c, "nova_no_fim") for c in h[len(cols):] if c not in cols]
    return out


BLOQUEIA = {"arquivo_ausente", "faltando", "fora_de_ordem"}


def data_carga(entrada: Path, con) -> str:
    p = (entrada / "_parameters.csv").as_posix()
    v = con.sql(f"SELECT value FROM read_csv('{p}', all_varchar=true) WHERE key='last_export_date'").fetchone()
    if not v:
        raise ValueError("_parameters sem last_export_date")
    return datetime.fromisoformat(v[0]).date().isoformat()


def carregar(con, entrada: Path | None = None, raw: Path | None = None) -> dict:
    entrada, raw = Path(entrada or config.ENTRADA_CSV), Path(raw or config.RAW)
    diff = schema_diff(entrada)
    con.sql("CREATE SCHEMA IF NOT EXISTS meta")
    con.sql("CREATE OR REPLACE TABLE meta.schema_diff (tabela VARCHAR, coluna VARCHAR, problema VARCHAR)")
    if diff:
        con.executemany("INSERT INTO meta.schema_diff VALUES (?, ?, ?)", diff)
    if any(d[2] in BLOQUEIA for d in diff):
        return {"status": "SCHEMA_QUEBRADO", "diff": diff}   # para a carga: nenhuma partição gravada
    d = data_carga(entrada, con)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for t, cols in contrato()["tabelas"].items():
        src = entrada / f"{t}.csv"
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        part = raw / t / f"data_carga={d}"
        if part.exists():
            shutil.rmtree(part)                               # sobrescreve a partição (idempotência)
        part.mkdir(parents=True)
        sel = ", ".join(f'"{c}"' for c in cols)              # só colunas do contrato; coluna nova é ignorada
        con.sql(f"""COPY (SELECT {sel}, '{agora}' AS _loaded_at, 'csv' AS _fonte, '{sha}' AS _source_sha256
                    FROM read_csv('{src.as_posix()}', all_varchar=true, header=true))
                    TO '{(part / 'part-0.parquet').as_posix()}' (FORMAT parquet)""")
    return {"status": "OK", "data_carga": d, "diff": diff}
