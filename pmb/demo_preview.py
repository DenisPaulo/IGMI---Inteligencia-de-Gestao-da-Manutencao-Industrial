"""Dashboard DEMO estático (HTML único, offline, leve): lê SÓ a gold do warehouse demo e gera export/demo_dashboard.html.
Todos os dados são SINTÉTICOS. Nenhuma regra de negócio aqui: só leitura e formatação pt-BR (ECharts de vendor/).
Visual: paleta azul/teal, cards de KPI, navegação fixa por seções, tabelas que viram cartões no celular (< 720 px).
Seções: #geral, #linha, #timeline, #equipamento, #backlog, #alertas, #pareto; #so-<seção> mostra só uma (prints/TV)."""
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from pmb import config, demo, demo_quality

OUT = config.ROOT / "export" / "demo_dashboard.html"
ECHARTS = config.ROOT / "vendor" / "echarts" / "echarts.min.js"
FAIXA = "DADOS SINTÉTICOS — demonstração do monitor de OS e tarefas (nenhuma OS, pessoa, valor ou planta real)"
TEMPLATE = Path(__file__).with_name("demo_template.html")
ABAS = [("geral", "Visão geral"), ("linha", "Linha Robotizada_1 × LR-02"), ("timeline", "Linha do tempo"), ("equipamento", "Equipamento"),
        ("backlog", "Backlog & preventivas"), ("alertas", "Alertas de reincidência"), ("pareto", "Pareto")]


def _rows(con, sql):
    rel = con.sql(sql)
    return [dict(zip(rel.columns, r)) for r in rel.fetchall()]


def _conv(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, (date, datetime)):
        return x.isoformat(sep=" ")[:16]
    return str(x)


def dados(con) -> dict:
    res = demo_quality.run(con, demo_quality.CHECKS)
    return {
        "linha": _rows(con, "SELECT * FROM gold.kpi_linha ORDER BY escopo = 'PLANTA', escopo"),
        "mensal": _rows(con, "SELECT * FROM gold.kpi_mensal ORDER BY mes, linha_id"),
        "equip": _rows(con, "SELECT * FROM gold.kpi_equipamento ORDER BY linha_id, equipment_id"),
        "os": _rows(con, "SELECT task_short_id, linha_id, equipamento_n2, equipamento_nome, tipo_id, modo_id, status, aberta_em, "
                         "parada_min, tempo_tecnico_min, descricao FROM gold.fato_os_demo WHERE NOT cancelada ORDER BY aberta_em"),
        "backlog_esp": _rows(con, "SELECT * FROM gold.backlog_especialidade ORDER BY especialidade_id"),
        "backlog": _rows(con, "SELECT task_short_id, linha_id, equipamento_n2_nome, especialidade_id, tipo_id, status, aberta_em, idade_dias, "
                              "round(horas_restantes, 1) horas_restantes, faixa_idade, envelhecida, descricao FROM gold.backlog_os ORDER BY idade_dias DESC"),
        "pm": _rows(con, "SELECT * FROM gold.kpi_pm WHERE mes <> 'período' AND escopo <> 'PLANTA' ORDER BY mes, escopo"),
        "aderencia": _rows(con, "SELECT escopo, CAST(semana AS VARCHAR) semana, programadas, executadas, aderencia, faixa FROM gold.aderencia_semanal ORDER BY semana, escopo"),
        "alertas": _rows(con, "SELECT * FROM gold.alertas_reincidencia ORDER BY disparado_em"),
        "pareto": _rows(con, "SELECT * FROM gold.pareto_modo ORDER BY escopo, ordem"),
        "qualidade": _rows(con, "SELECT * FROM gold.qualidade_dado"),
        "param": {r["chave"]: r["valor"] for r in _rows(con, "SELECT chave, valor FROM cat.parametros_demo")},
        "data_carga": str(con.sql("SELECT data_carga FROM meta.carga").fetchone()[0]),
        "checks_ok": sum(r["ok"] for r in res), "checks_total": len(res),
    }


def render(d: dict) -> str:
    nav = "".join(f'<li><a href="#{k}">{t}</a></li>' for k, t in ABAS)
    return (TEMPLATE.read_text(encoding="utf-8").replace("%%FAIXA%%", FAIXA).replace("%%NAV%%", nav)
            .replace("%%DADOS%%", json.dumps(d, ensure_ascii=False, default=_conv).replace("</", "<\\/"))
            .replace("%%ECHARTS%%", ECHARTS.read_text(encoding="utf-8")))


def gerar(con=None, out: Path | None = None) -> Path:
    con = con or duckdb.connect(str(demo.WAREHOUSE), read_only=True)
    out = Path(out or OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(dados(con)), encoding="utf-8")
    return out
