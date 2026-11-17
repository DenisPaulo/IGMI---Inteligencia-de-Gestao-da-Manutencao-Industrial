"""Primeiro Analista de Confiabilidade: relatório determinístico e rastreável.

Esta entrega ainda não faz nenhuma chamada a um modelo generativo.
"""

def analisar_confiabilidade(consultas, linha):
    kpi = consultas.consultar_kpis(linha)
    if kpi is None:
        raise ValueError(f'Nenhum KPI para {linha}')
    equipamentos = consultas.consultar_equipamentos(linha)
    pareto = consultas.consultar_pareto(linha)
    alertas = consultas.consultar_reincidencias(linha)
    os_ = consultas.consultar_os(linha)
    mensal = consultas.consultar_tendencia(linha)
    backlog = consultas.consultar_backlog(linha)
    qualidade = consultas.consultar_qualidade()
    hipoteses = []
    recomendacoes = []
    if equipamentos and equipamentos[0]['falhas']:
        eid = equipamentos[0]['equipment_id']
        hipoteses.append(f"A concentração de paradas em {eid} merece investigação; não demonstra causa raiz.")
        recomendacoes.append(f"Avaliar o histórico, as OS e as condições operacionais de {eid} com a equipe técnica.")
    if alertas:
        recomendacoes.append('Validar tecnicamente os alertas de reincidência, os modos e as OS relacionadas.')
    if backlog['os_envelhecidas']:
        recomendacoes.append('Revisar OS envelhecidas com o PCM e responsáveis pelos equipamentos.')
    if not recomendacoes:
        recomendacoes.append('Continuar monitorando os indicadores e a qualidade dos dados.')
    return {
        'produto': 'IGMI — Inteligência de Gestão da Manutenção Industrial',
        'versao': '0.1.0', 'tipo': 'analise_deterministica_sem_llm',
        'linha': linha, 'contexto': dict(consultas.contexto),
        'kpis': kpi, 'backlog': backlog,
        'equipamentos_prioritarios_por_parada': equipamentos,
        'pareto_modos': pareto, 'reincidencias': alertas,
        'os_evidencias': os_, 'tendencia_mensal': mensal,
        'qualidade_dado': qualidade,
        'hipoteses_para_investigacao': hipoteses,
        'recomendacoes_para_validacao': recomendacoes,
        'limitacoes': [
            'Dados exclusivamente sintéticos: não representam a planta real.',
            'KPIs agregados abrangem o período fechado do dataset, não uma janela móvel.',
            'As hipóteses não constituem diagnóstico de causa raiz.',
            'Ainda não há modelo de IA, interface conversacional ou acesso a sistemas reais.',
            'Ordenação de equipamentos por horas de parada não recalcula a criticidade A/B/C.',
        ],
    }


def markdown(r):
    c, k, b = r['contexto'], r['kpis'], r['backlog']
    lines = [f"# IGMI — Confiabilidade da linha {r['linha']}", '',
        '**Análise determinística sobre dados sintéticos (sem IA generativa)**', '',
        f"**Período:** {c['periodo_inicio']} a {c['periodo_fim']}",
        f"**Data da carga:** {c['data_carga']} · **Qualidade:** {c['checks_ok']}/{c['checks_total']} checks OK", '',
        '## KPIs do período completo', '', '| Indicador | Valor |', '|---|---:|']
    for nome, chave, unidade in [
        ('OS totais', 'os_total', ''), ('Falhas', 'falhas', ''),
        ('Falhas com parada', 'falhas_com_parada', ''), ('Parada total', 'parada_h', ' h'),
        ('MTTR', 'mttr_h', ' h'), ('MTBF', 'mtbf_h', ' h'),
        ('Disponibilidade', 'disponibilidade', ' (fração)'),
        ('OS abertas', 'os_abertas', ''), ('OS envelhecidas', 'os_envelhecidas', ''),
        ('PM compliance', 'pm_compliance', ' (fração)'), ('Aderência', 'aderencia', ' (fração)')]:
        val = k.get(chave)
        lines.append(f"| {nome} | {val if val is not None else 'n/d'}{unidade} |")
    lines += ['', '## Backlog', '', f"OS abertas: {b['os_abertas']} · OS envelhecidas: {b['os_envelhecidas']} · Horas restantes: {b['horas_restantes']}", '',
        '## Equipamentos com maior parada', '',
        '| Equipamento | Criticidade cadastrada | Falhas | Parada (h) |', '|---|---|---:|---:|']
    for e in r['equipamentos_prioritarios_por_parada']:
        lines.append(f"| `{e['equipment_id']}` | {e['criticidade']} | {e['falhas']} | {e['parada_h']} |")
    lines += ['', f"## Pareto por modo ({c['pareto_medida']})", '',
        '| Modo | Valor | Acumulado (%) |', '|---|---:|---:|']
    for p in r['pareto_modos']:
        lines.append(f"| {p['modo_id']} — {p['modo_nome']} | {p['valor']} | {p['pct_acumulado']} |")
    lines += ['', '## Reincidências', '']
    if not r['reincidencias']:
        lines.append('Nenhuma reincidência alertada no período.')
    for a in r['reincidencias']:
        lines.append(f"- **{a['equipment_id']}**, modo {a['modo_id']}, {a['ocorrencias']} ocorrências em {a['janela_dias']} dias; OS: {a['os_lista']}")
    lines += ['', '## Tendência mensal observada', '',
        '| Mês | Falhas | Parada (h) | Disponibilidade |', '|---|---:|---:|---:|']
    for m in r['tendencia_mensal']:
        lines.append(f"| {m['mes']} | {m['falhas']} | {m['parada_h']} | {m['disponibilidade']} |")
    lines += ['', '## Ordens de serviço para verificar', '',
        '| OS | Equipamento | Modo | Parada (min) |', '|---|---|---|---:|']
    for o in r['os_evidencias']:
        lines.append(f"| `{o['task_short_id']}` | {o['equipment_id']} | {o['modo_id'] or 'n/d'} | {o['parada_min']} |")
    for title, key in [('Hipóteses para investigação (não comprovadas)', 'hipoteses_para_investigacao'),
                       ('Recomendações para validação humana', 'recomendacoes_para_validacao'),
                       ('Limitações', 'limitacoes')]:
        lines += ['', f'## {title}', '']
        lines += [f'- {s}' for s in r[key]] or ['- Nenhum registro.']
    lines += ['', '## Qualidade do dado — indicadores da GOLD', '',
        '| Indicador | Ocorrências | Base |', '|---|---:|---:|']
    for q in r['qualidade_dado']:
        lines.append(f"| {q['indicador']} | {q['n']} | {q['base']} |")
    return '\n'.join(lines) + '\n'
