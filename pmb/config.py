"""Caminhos e seeds. Dado da fábrica fica fora do repo: PMB_RAW (crua) e PMB_LANDING_PARADA (partições do CSV de parada)."""
import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "seeds"
SQL = ROOT / "sql"
CONTRATO = ROOT / "contrato"
# fallback CSV do conector; padrão = dados SINTÉTICOS versionados (nunca MySQL/credencial nesta entrega)
ENTRADA_CSV = Path(os.environ.get("PMB_ENTRADA_CSV", ROOT / "dados_sinteticos" / "entrada_csv"))
RAW = Path(os.environ.get("PMB_RAW", ROOT / "raw"))
LANDING_PARADA = Path(os.environ.get("PMB_LANDING_PARADA", ROOT / "landing_parada"))
WAREHOUSE = Path(os.environ.get("PMB_WAREHOUSE", ROOT / "warehouse" / "p_mobility.duckdb"))
REPORT = ROOT / "data_quality_report.md"


def parametros() -> dict[str, str]:
    with open(SEEDS / "parametros.csv", encoding="utf-8", newline="") as f:
        return {r["chave"]: r["valor"] for r in csv.DictReader(f)}

