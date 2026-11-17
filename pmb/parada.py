"""Contrato v0 do CSV de parada da produção: só validação e registro da partição (hora_parada_min segue nula).
Ver docs/contrato_parada_v0.md e contrato/parada_v0.schema.json."""
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

import duckdb

from pmb import config

SCHEMA = json.loads((config.CONTRATO / "parada_v0.schema.json").read_text(encoding="utf-8"))
COLUNAS = [c["nome"] for c in SCHEMA["colunas"]]
RE_OS = re.compile(next(c["regex"] for c in SCHEMA["colunas"] if c["nome"] == "os_ref"))
RE_HORA = re.compile(r"^[0-9]{1,4}(\.[0-9]{1,2})?$")   # horas decimais, ponto como separador


def ler(path: Path):
    """Lê tudo como texto (all_varchar): 11112222 continua '11112222', nunca número."""
    con = duckdb.connect()
    rel = con.sql(f"SELECT * FROM read_csv('{Path(path).as_posix()}', all_varchar=true, header=true)")
    return rel.columns, rel.fetchall()


def validar(path: Path) -> list[str]:
    cols, rows = ler(path)
    if list(cols) != COLUNAS:
        return [f"cabeçalho {list(cols)} ≠ contrato {COLUNAS}"]
    erros = []
    for i, (os_ref, hora, data) in enumerate(rows, start=2):
        if os_ref is None or not RE_OS.match(os_ref):
            erros.append(f"linha {i}: os_ref {os_ref!r} fora de ^[0-9a-f]{{8}}$")
        if hora is None or not RE_HORA.match(hora) or float(hora) <= 0:
            erros.append(f"linha {i}: hora_lancada {hora!r} não é hora decimal > 0")
        if data not in (None, ""):
            try:
                date.fromisoformat(data)
            except ValueError:
                erros.append(f"linha {i}: data_parada {data!r} não é AAAA-MM-DD")
    return erros


def resumo(path: Path) -> tuple[int, float]:
    _, rows = ler(path)
    return len({r[0] for r in rows}), round(sum(float(r[1]) for r in rows), 2)


def registrar(path: Path, data_carga: str, landing: Path | None = None) -> str:
    """Grava o arquivo numa partição datada imutável (fora do repo). Retorna OK | SEM_MUDANCA | erro (exceção).
    Cada arquivo é tratado como acumulado e substitui o anterior na silver; arquivo com menos OS ou menos horas bloqueia."""
    landing = Path(landing or config.LANDING_PARADA)
    erros = validar(path)
    if erros:
        raise ValueError("; ".join(erros))
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    anteriores = sorted(landing.glob("data_carga=*/*.csv"))
    if any(hashlib.sha256(a.read_bytes()).hexdigest() == sha for a in anteriores):
        return "SEM_MUDANCA"
    part = landing / f"data_carga={data_carga}"
    if part.exists():
        raise FileExistsError(f"partição {part.name} já existe e é imutável")
    if anteriores:
        os_n, h = resumo(path)
        os_a, h_a = resumo(anteriores[-1])
        if os_n < os_a or h < h_a:
            raise ValueError(f"arquivo novo tem menos OS/horas que o anterior ({os_n}/{h} < {os_a}/{h_a}): provável incremental")
    part.mkdir(parents=True)
    shutil.copyfile(path, part / Path(path).name)
    return "OK"
