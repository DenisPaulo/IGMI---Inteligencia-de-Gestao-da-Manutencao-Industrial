"""PRÉVIA estática do dashboard: lê SÓ a gold (tabelas/views) e gera export/dashboard_preview.html.
Nenhuma regra de negócio aqui: só leitura, formatação pt-BR e gráficos (ECharts embutido de vendor/, offline).
Não mostra títulos, descrições nem links de OS."""
import html
import json
from decimal import Decimal
from pathlib import Path

import duckdb

from pmb import config

OUT = config.ROOT / "export" / "dashboard_preview.html"
ECHARTS = config.ROOT / "vendor" / "echarts" / "echarts.min.js"
FAIXA = "PRÉVIA — todos os dados são SINTÉTICOS (conector e parada); o Power BI final vem depois"


def br(v, casas=2):
    if v is None:
        return "—"
    s = f"{Decimal(str(v)):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _rows(con, sql):
    rel = con.sql(sql)
    cols = rel.columns
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def _json(o):
    def conv(x):
        if isinstance(x, Decimal):
            return float(x)
        return str(x)
    return json.dumps(o, ensure_ascii=False, default=conv)


def dados(con) -> dict:
    return {
        "mttr": _rows(con, "SELECT * FROM gold.kpi_mttr_tecnico")[0],
        "status": {r["status"]: r["n"] for r in _rows(con, "SELECT status, count(*) n FROM gold.fato_os GROUP BY 1 ORDER BY 1")},
        "os": _rows(con, "SELECT task_short_id, equipment_id, equipamento, linha, status, pendente, escopo_quebra, modo_id, tempo_tecnico_min, hora_parada_min, custo_parada FROM gold.preview_os ORDER BY task_short_id"),
        "diario": _rows(con, "SELECT equipment_id, CAST(data_parada AS VARCHAR) data_parada, minutos FROM gold.parada_diaria_equip ORDER BY equipment_id, data_parada"),
        "linha": _rows(con, "SELECT * FROM gold.resumo_linha ORDER BY linha, equipamento"),
        "filas": {r["fila"]: r["n"] for r in _rows(con, "SELECT * FROM gold.filas_contadores")},
        "alertas": {r["qc"]: r["n"] for r in _rows(con, "SELECT * FROM gold.alertas_contadores ORDER BY qc")},
        "meta": {"data_carga": str(con.sql("SELECT max(data_carga) FROM gold.fato_os").fetchone()[0])},
    }


def _card(titulo, linhas, classe):
    itens = "".join(f"<div class=kv><span>{html.escape(k)}</span><b>{v}</b></div>" for k, v in linhas)
    return f"<section class='card {classe}'><h3>{html.escape(titulo)}</h3>{itens}</section>"


def render(d: dict) -> str:
    m = d["mttr"]
    cards = (
        _card("MTTR do técnico (OS de quebra concluídas)", [
            ("OS", str(m["os_n"])), ("Esforço", f"{m['esforco_min']} min"), ("MTTR", f"{br(m['mttr_h'])} h")], "tec")
        + _card("OS por status", [(k, str(n)) for k, n in d["status"].items()], "est"))
    filas = "".join(f"<div class=contador><b>{n}</b><span>{html.escape(k.replace('_', ' '))}</span></div>" for k, n in d["filas"].items())
    alertas = "".join(f"<div class='contador peq'><b>{n}</b><span>{html.escape(k)}</span></div>" for k, n in d["alertas"].items())
    linhas = "".join(
        f"<tr><td>{html.escape(r['linha'])}</td><td>{html.escape(r['equipamento'] or '—')}</td><td>{r['os_n']}</td><td>{r['os_pendentes']}</td>"
        f"<td>{'—' if r['parada_min'] is None else r['parada_min']}</td><td>{'—' if r['tempo_tecnico_min'] is None else r['tempo_tecnico_min']}</td>"
        f"<td>{'—' if r['custo_parada'] is None else 'R$ ' + br(r['custo_parada'])}</td></tr>" for r in d["linha"])
    return TEMPLATE.format(
        faixa=html.escape(FAIXA), cards=cards, filas=filas, alertas=alertas, linhas=linhas,
        data_carga=html.escape(d["meta"]["data_carga"]),
        dados=_json({k: d[k] for k in ("os", "diario", "linha")}).replace("</", "<\\/"),
        echarts=ECHARTS.read_text(encoding="utf-8"))


def gerar(con=None, out: Path | None = None) -> Path:
    con = con or duckdb.connect(str(config.WAREHOUSE), read_only=True)
    out = Path(out or OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(dados(con)), encoding="utf-8")
    return out


TEMPLATE = """<!doctype html><html lang=pt-BR><head><meta charset=utf-8><title>IGMI — prévia do dashboard</title>
<style>
body{{margin:0;font-family:"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#f4f6f8;color:#1f2328}}
.faixa{{background:#9a3412;color:#fff;font-weight:700;padding:12px 24px;font-size:15px;letter-spacing:.2px}}
header{{padding:14px 24px 0;display:flex;align-items:baseline;gap:16px}} header h1{{font-size:20px;margin:0}} header small{{color:#59636e}}
nav{{padding:10px 24px 0;display:flex;gap:6px}} nav button{{border:1px solid #d1d9e0;background:#fff;padding:8px 16px;border-radius:6px 6px 0 0;cursor:pointer;font-size:14px}}
nav button.on{{background:#0b3d91;color:#fff;border-color:#0b3d91}}
main{{padding:16px 24px 28px}} .aba{{display:none}} .aba.on{{display:block}}
.cards{{display:grid;grid-template-columns:1fr 1fr 0.7fr;gap:14px}}
.card{{background:#fff;border-radius:8px;padding:12px 16px;border-top:5px solid #999;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
.card.tec{{border-color:#1d4ed8}} .card.est{{border-color:#9ca3af;background:#fafafa}}
.card h3{{margin:0 0 8px;font-size:15px}} .kv{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dashed #eee;font-size:14px}} .kv b{{font-size:16px}}
.nota{{color:#59636e;font-size:12.5px;margin:8px 0 0}}
.graficos{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}} .g{{background:#fff;border-radius:8px;height:360px;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
.filtro{{background:#fff;padding:10px 14px;border-radius:8px;margin-bottom:12px;display:flex;gap:12px;align-items:center}} select{{font-size:14px;padding:4px 8px}}
.mini{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:12px}} .mini div{{background:#fff;border-radius:8px;padding:10px 12px}} .mini b{{display:block;font-size:20px}} .mini span{{color:#59636e;font-size:12.5px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;font-size:13.5px}} th,td{{padding:7px 10px;border-bottom:1px solid #eef0f2;text-align:left}} th{{background:#eef2f7}}
.pend{{background:#fef3c7;color:#92400e;padding:1px 8px;border-radius:10px;font-size:12px}} .ok{{background:#dcfce7;color:#166534;padding:1px 8px;border-radius:10px;font-size:12px}}
.contadores{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}} .contador{{background:#fff;border-radius:8px;padding:12px 18px;min-width:150px;border-left:5px solid #b45309}} .contador b{{display:block;font-size:26px}} .contador span{{color:#59636e;font-size:13px}}
.contador.peq{{min-width:90px;border-left-color:#6b7280}} .contador.peq b{{font-size:18px}}
footer{{color:#59636e;font-size:12px;padding:0 24px 18px}}
</style></head><body>
<div class=faixa id=faixa>{faixa}</div>
<header><h1>IGMI — camada gold</h1><small>data_carga do conector (sintético) {data_carga}</small></header>
<nav><button data-aba=geral class=on>1 · Visão geral</button><button data-aba=maquina>2 · Máquina</button><button data-aba=linha>3 · Linha</button></nav>
<main>
<div class="aba on" id=aba-geral>
  <div class=cards>{cards}</div>
  <p class=nota>Monitor de OS e tarefas multi-linha. MTTR só sobre OS de quebra concluídas; tempo do técnico nunca vira custo.</p>
</div>
<div class=aba id=aba-maquina>
  <div class=filtro><label for=eq><b>Equipamento</b></label><select id=eq></select><span class=nota>fato_os + parada v2 SINTÉTICA</span></div>
  <div class=mini id=mini></div>
  <div class=graficos><div class=g id=g-dia></div><div class=g id=g-os></div></div>
  <h3>OS do equipamento</h3><table><thead><tr><th>OS (id)</th><th>modo</th><th>status</th><th>parada (min)</th><th>técnico (min)</th><th>custo</th></tr></thead><tbody id=tos></tbody></table>
  <p class=nota>Custo só onde há parada de origem csv_producao em OS concluída de centro de custo com taxa no seed (aqui, parada sintética). Tempo do técnico nunca vira custo.</p>
</div>
<div class=aba id=aba-linha>
  <h3>Filas de qualidade (parada v2 sintética)</h3><div class=contadores>{filas}</div>
  <h3>Alertas por regra</h3><div class=contadores>{alertas}</div>
  <h3>Soma por linha (cost_center) e equipamento — cada medida na sua coluna</h3>
  <table><thead><tr><th>linha</th><th>equipamento</th><th>OS</th><th>pendentes</th><th>parada (min)</th><th>técnico (min)</th><th>custo</th></tr></thead><tbody>{linhas}</tbody></table>
</div>
</main>
<footer>Gerado por <code>python run.py preview</code> a partir só da gold. Sem títulos, descrições ou links de OS.</footer>
<script id=dados type="application/json">{dados}</script>
<script>{echarts}</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent);
const fmt = (v, c=2) => v == null ? '—' : Number(v).toLocaleString('pt-BR', {{minimumFractionDigits:c, maximumFractionDigits:c}});
const charts = {{}};
const eqs = [...new Map(D.os.map(o => [o.equipment_id, o.equipamento])).entries()];
const sel = document.getElementById('eq');
eqs.forEach(([id, nome]) => sel.insertAdjacentHTML('beforeend', `<option value="${{id}}">${{nome}}</option>`));
function maquina() {{
  const id = sel.value, os = D.os.filter(o => o.equipment_id === id), dia = D.diario.filter(r => r.equipment_id === id);
  const r = D.linha.find(x => x.equipment_id === id) || {{}};   // totais vêm da gold.resumo_linha (sem somar no HTML)
  document.getElementById('mini').innerHTML =
    `<div><b>${{r.os_n ?? 0}}</b><span>OS (não canceladas)</span></div><div><b>${{r.os_pendentes ?? 0}}</b><span>pendentes</span></div>` +
    `<div><b>${{r.parada_min ?? '—'}} min</b><span>parada (sintética)</span></div><div><b>${{r.tempo_tecnico_min ?? '—'}} min</b><span>técnico (sem custo)</span></div>` +
    `<div><b>${{r.custo_parada == null ? '—' : 'R$ ' + fmt(r.custo_parada)}}</b><span>custo (só parada, com taxa)</span></div>`;
  document.getElementById('tos').innerHTML = os.map(o => `<tr><td>${{o.task_short_id}}</td><td>${{o.modo_id == null ? 'a classificar' : 'M' + o.modo_id}}</td>` +
    `<td>${{o.pendente ? '<span class=pend>pendente</span>' : '<span class=ok>' + o.status + '</span>'}}</td><td>${{o.hora_parada_min ?? '—'}}</td>` +
    `<td>${{o.tempo_tecnico_min ?? '—'}}</td><td>${{o.custo_parada == null ? '—' : 'R$ ' + fmt(o.custo_parada)}}</td></tr>`).join('');
  const g1 = charts['g-dia'] || (charts['g-dia'] = echarts.init(document.getElementById('g-dia')));
  g1.setOption({{animation:false, title:{{text:'Minutos de parada por dia (sintético)', left:10, top:6, textStyle:{{fontSize:14}}}}, grid:{{left:48,right:20,top:48,bottom:36}},
    tooltip:{{trigger:'axis'}}, xAxis:{{type:'category', data:dia.map(r=>r.data_parada)}}, yAxis:{{type:'value', name:'min'}},
    series:[{{type:'bar', data:dia.map(r=>r.minutos), itemStyle:{{color:'#c2410c'}}, label:{{show:true, position:'top'}}}}]}}, true);
  const g2 = charts['g-os'] || (charts['g-os'] = echarts.init(document.getElementById('g-os')));
  g2.setOption({{animation:false, title:{{text:'Por OS: parada × técnico (min, colunas separadas)', left:10, top:6, textStyle:{{fontSize:14}}}}, grid:{{left:48,right:20,top:56,bottom:36}},
    legend:{{top:28}}, tooltip:{{trigger:'axis'}}, xAxis:{{type:'category', data:os.map(o=>o.task_short_id)}}, yAxis:{{type:'value', name:'min'}},
    series:[{{name:'parada', type:'bar', data:os.map(o=>o.hora_parada_min), itemStyle:{{color:'#c2410c'}}}},
            {{name:'técnico', type:'bar', data:os.map(o=>o.tempo_tecnico_min), itemStyle:{{color:'#1d4ed8'}}}}]}}, true);
}}
sel.addEventListener('change', maquina);
document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('nav button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.aba').forEach(a => a.classList.toggle('on', a.id === 'aba-' + b.dataset.aba));
  if (b.dataset.aba === 'maquina') maquina();
  Object.values(charts).forEach(c => c.resize());
}}));
</script></body></html>"""
