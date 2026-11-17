"""Ingestão do CSV de parada no contrato v2 (PROPOSTO): roda só sobre amostras SINTÉTICAS nesta etapa.

- QCP01–07 rejeitam o arquivo inteiro: nada é gravado na crua.
- Crua: raw/parada_v2/data_carga=AAAA-MM-DD/part-0.parquet (fora do repo), imutável.
  Reprocessar o mesmo arquivo (mesmo sha256) não regrava, não duplica e não cria versão nova.
- Silver/gold (versões, auditoria, filas, alertas QCP08–13) em sql/silver/02_parada_v2.sql e sql/gold/22_parada_v2.sql.
"""
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from pmb import config

SCHEMA = json.loads((config.CONTRATO / "parada_v2.schema.json").read_text(encoding="utf-8"))
CABECALHO = SCHEMA["arquivo"]["cabecalho_proposto"]
RX = {c["nome"]: re.compile(c["regex"]) for c in SCHEMA["colunas"] if "regex" in c}
ACOES = next(c["dominio"] for c in SCHEMA["colunas"] if c["nome"] == "acao")
MANIFESTO = Path(config.ROOT / "dados_sinteticos" / "parada_v2" / "cargas.csv")


def validar(path: Path) -> dict[str, list[str]]:
    """{QCPxx: [erros]} para QCP01–07. Vazio = arquivo aceito."""
    b = Path(path).read_bytes()
    err: dict[str, list[str]] = {}

    def add(qc, msg):
        err.setdefault(qc, []).append(msg)

    if b.startswith(b"\xef\xbb\xbf"):
        add("QCP01", "BOM UTF-8")
    try:
        txt = b.decode("utf-8")
    except UnicodeDecodeError:
        add("QCP01", "não é UTF-8")
        return err
    rows = list(csv.reader(txt.lstrip("\ufeff").splitlines()))
    if not rows or rows[0] != CABECALHO:
        add("QCP01", f"cabeçalho {rows[0] if rows else []} ≠ {CABECALHO}")
        return err
    vistos = set()
    for n, r in enumerate(rows[1:], start=2):
        if len(r) != len(CABECALHO):
            add("QCP01", f"linha {n}: {len(r)} colunas")
            continue
        idl, os_ref, hi, dur, acao = r
        acao = acao or "incluir"
        if not idl.strip():
            add("QCP02", f"linha {n}: id_lancamento vazio")
        elif idl in vistos:
            add("QCP03", f"linha {n}: id_lancamento {idl} repetido no arquivo")
        vistos.add(idl)
        if acao not in ACOES:
            add("QCP07", f"linha {n}: acao {acao!r}")
        excluir = acao == "excluir"
        if (os_ref or not excluir) and not RX["os_ref"].match(os_ref):
            add("QCP04", f"linha {n}: os_ref {os_ref!r}")
        if hi or not excluir:
            ok = bool(RX["hora_inicio"].match(hi))
            if ok:
                try:
                    datetime.strptime(hi, "%Y-%m-%dT%H:%M")
                except ValueError:
                    ok = False
            if not ok:
                add("QCP05", f"linha {n}: hora_inicio {hi!r}")
        if (dur or not excluir) and (not RX["duracao_min"].match(dur) or int(dur) <= 0):
            add("QCP06", f"linha {n}: duracao_min {dur!r}")
    return err


def manifesto(path: Path | None = None) -> list[dict]:
    with open(path or MANIFESTO, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def carregar(con, raw: Path | None = None, cargas: list[dict] | None = None, pasta: Path | None = None) -> list[dict]:
    """Valida e grava cada carga do manifesto. Registra o resultado em meta.parada_cargas."""
    raw = Path(raw or config.RAW) / "parada_v2"
    pasta = Path(pasta or MANIFESTO.parent)
    cargas = manifesto() if cargas is None else cargas
    out = []
    for c in cargas:
        src = pasta / c["arquivo"]
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        part = raw / f"data_carga={c['data_carga']}"
        erros = validar(src)
        if erros:
            status = "REJEITADO"                         # nada gravado
        elif part.exists():
            prev = duckdb.connect().sql(f"SELECT DISTINCT _sha256 FROM read_parquet('{part.as_posix()}/*.parquet')").fetchall()
            if prev != [(sha,)]:
                raise FileExistsError(f"partição {part.name} imutável já existe com outro arquivo")
            status = "SEM_MUDANCA"                       # reprocesso: não regrava
        else:
            part.mkdir(parents=True)
            agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                con.sql(f"""COPY (SELECT *, '{c['arquivo']}' AS _arquivo, CAST(row_number() OVER () + 1 AS INTEGER) AS _linha,
                                 '{sha}' AS _sha256, '{agora}' AS _loaded_at
                                 FROM read_csv('{src.as_posix()}', all_varchar=true, header=true))
                            TO '{(part / 'part-0.parquet').as_posix()}' (FORMAT parquet)""")
            except Exception:
                shutil.rmtree(part, ignore_errors=True)
                raise
            status = "OK"
        out.append({**c, "sha256": sha, "status": status,
                    "erros": "; ".join(f"{k}: {len(v)}" for k, v in sorted(erros.items()))})
    con.sql("CREATE SCHEMA IF NOT EXISTS meta")
    con.sql("CREATE OR REPLACE TABLE meta.parada_cargas (data_carga DATE, arquivo VARCHAR, tipo VARCHAR, cenario VARCHAR, sha256 VARCHAR, status VARCHAR, erros VARCHAR)")
    if out:
        con.executemany("INSERT INTO meta.parada_cargas VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [[o["data_carga"], o["arquivo"], o["tipo"], o["cenario"], o["sha256"], o["status"], o["erros"]] for o in out])
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")
    if any(raw.glob("data_carga=*/*.parquet")):
        con.sql(f"""CREATE OR REPLACE VIEW raw.parada_v2 AS SELECT * FROM read_parquet('{raw.as_posix()}/*/*.parquet',
                    hive_partitioning=true, hive_types={{'data_carga': DATE}})""")
    else:
        con.sql("""CREATE OR REPLACE TABLE raw.parada_v2 (id_lancamento VARCHAR, os_ref VARCHAR, hora_inicio VARCHAR, duracao_min VARCHAR,
                   acao VARCHAR, _arquivo VARCHAR, _linha INTEGER, _sha256 VARCHAR, _loaded_at VARCHAR, data_carga DATE)""")
    return out
