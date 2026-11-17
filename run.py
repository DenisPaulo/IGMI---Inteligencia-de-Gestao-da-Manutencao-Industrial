#!/usr/bin/env python3
"""Runner multiplataforma.  Uso: python run.py [all|test|clean]   (padrão: all)

  all    seeds + ingestão (CSV SINTÉTICO) + parada v2 (SINTÉTICA) -> silver -> gold -> QC; exit != 0 se algum QC falhar
  preview PRÉVIA estática do dashboard (só gold) -> export/dashboard_preview.html (roda depois de all)
  parada resumo da parada v2: status de cada carga, horas por OS, filas e alertas QCP08–13 (roda depois de all)
  simular  regera o dataset DEMO sintético (dados_sinteticos/demo/, semente fixa = mesmos bytes)
  demo     pipeline DEMO (catálogos ISO 14224 + KPIs) -> warehouse/demo.duckdb + checks QD; exit != 0 se algum falhar
  demo-preview  dashboard DEMO -> export/demo_dashboard.html (roda depois de demo)
  test   pytest
  igmi   analista de confiabilidade determinístico (demo): --linha LT3 [--formato markdown|json] [--saida arquivo]
  igmi-ia analista de confiabilidade com IA (API opcional): --linha LT3 --pergunta "..." --autorizar-api
  igmi-chat conversa de confiabilidade (consultas offline; IA opcional)
  clean  apaga o que é gerado (raw/, warehouse/, landing_parada/, export/, relatório)
"""
import os
import shutil
import subprocess
import sys

from pmb import config


def all_():
    config.WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    if config.WAREHOUSE.exists():
        config.WAREHOUSE.unlink()
    from pmb import db, quality
    con = db.build(config.WAREHOUSE)
    res = quality.run(con)
    n_ok = quality.report(res)
    for r in res:
        print(f"{'OK ' if r['ok'] else 'FALHA'} {r['id']:6} {r['descricao']} (obs={r['observado']})")
    st = con.sql("SELECT string_agg(status || '=' || n, ', ') FROM (SELECT status, count(*) n FROM meta.parada_cargas GROUP BY 1 ORDER BY 1)").fetchone()[0]
    print(f"parada v2: {st}")
    print(f"{n_ok}/{len(res)} checks OK; carga = {con.sql('SELECT status, data_carga FROM meta.carga').fetchone()}")
    con.close()
    return 0 if n_ok == len(res) else 1


def parada():
    import duckdb
    con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
    for titulo, q in [
        ("cargas", "SELECT data_carga, arquivo, tipo, status, erros FROM meta.parada_cargas ORDER BY 1"),
        ("hora de parada por OS (min) e custo", "SELECT task_id, status, linha, hora_parada_min, custo_parada FROM gold.fato_os ORDER BY 1"),
        ("fila: parada sem OS", "SELECT * FROM gold.fila_parada_sem_os"),
        ("fila: candidatos a exclusão", "SELECT * FROM gold.fila_candidato_exclusao"),
        ("alertas", "SELECT qc, id_lancamento, detalhe FROM gold.alertas_parada ORDER BY 1, 2")]:
        print(f"\n## {titulo}")
        for r in con.sql(q).fetchall():
            print("  ", " | ".join("" if v is None else str(v) for v in r))
    return 0


def preview():
    from pmb import preview as pv
    print(f"prévia gerada: {pv.gerar().relative_to(config.ROOT).as_posix()}")
    return 0


def simular():
    from pmb import simulador
    r = simulador.gerar()
    print(f"dataset demo: {r['os']} OS, {r['atividades']} apontamentos, {r['paradas']} paradas -> {r['saida'].relative_to(config.ROOT).as_posix()}")
    return 0


def demo_():
    from pmb import demo, demo_quality
    demo.WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    demo.WAREHOUSE.unlink(missing_ok=True)
    shutil.rmtree(demo.RAW, ignore_errors=True)
    con = demo.build(demo.WAREHOUSE)
    res = demo_quality.run(con, demo_quality.CHECKS)
    for r in res:
        print(f"{'OK ' if r['ok'] else 'FALHA'} {r['id']:5} {r['descricao']} (obs={r['observado']})")
    k = con.sql("SELECT escopo, os_total, falhas, disponibilidade, mtbf_h, mttr_h, pct_reativa, pm_compliance, aderencia FROM gold.kpi_linha ORDER BY escopo").fetchall()
    for r in k:
        print("  ", " | ".join(str(v) for v in r))
    n_ok = sum(r["ok"] for r in res)
    print(f"demo: {n_ok}/{len(res)} checks OK; {con.sql('SELECT count(*) FROM gold.alertas_reincidencia').fetchone()[0]} alertas de reincidência")
    con.close()
    return 0 if n_ok == len(res) else 1


def demo_preview():
    from pmb import demo_preview as dp
    print(f"dashboard demo: {dp.gerar().relative_to(config.ROOT).as_posix()}")
    return 0


def test():
    return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=config.ROOT, env={**os.environ, "PYTHONUTF8": "1"})


def clean():
    for p in (config.RAW, config.ROOT / "raw_demo", config.WAREHOUSE.parent, config.LANDING_PARADA, config.ROOT / "export"):
        shutil.rmtree(p, ignore_errors=True)
    config.REPORT.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "igmi":
        from igmi.cli import main as igmi_main
        sys.exit(igmi_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "igmi-ia":
        from igmi.ia_cli import main as ia_main
        sys.exit(ia_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "igmi-chat":
        from igmi.chat_cli import main as chat_main
        sys.exit(chat_main(sys.argv[2:]))
    alvos = {"all": all_, "parada": parada, "preview": preview, "simular": simular, "demo": demo_, "demo-preview": demo_preview, "test": test, "clean": clean}
    for a in sys.argv[1:] or ["all"]:
        if a not in alvos:
            sys.exit(f"alvo desconhecido: {a} (use {', '.join(alvos)})")
        rc = alvos[a]()
        if rc:
            sys.exit(rc)
