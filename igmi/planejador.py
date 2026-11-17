"""IGMI 0.3.2: planejamento local multi-intenção; não executa SQL nem acessa API.

O catálogo é fechado e as leituras continuam exclusivamente em ConsultasDemo.
Os fatos quantitativos são redigidos em Python; o modelo recebe somente recortes.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
import unicodedata

from igmi.ia_economica import duracao_min, duracao_h, hora_decimal, porcentagem, recortar

TOP_N = 3
LIMITE_CONSULTA = 30
MAX_PAYLOAD_CHARS = 5800

ORDEM = ('geral', 'impacto', 'reincidencias', 'mttr', 'tendencia',
         'backlog', 'pareto', 'os', 'melhorias')
FERRAMENTAS_POR_INTENCAO = {
    'geral': ('consultar_kpis',),
    'impacto': ('consultar_equipamentos',),
    'reincidencias': ('consultar_reincidencias',),
    'mttr': ('consultar_kpis', 'consultar_equipamentos'),
    'tendencia': ('consultar_tendencia',),
    'backlog': ('consultar_backlog',),
    'pareto': ('consultar_pareto',),
    'os': ('consultar_os',),
    'melhorias': (),
}


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.lower())
                   if not unicodedata.combining(c))


def _tem(texto, padrao):
    return bool(re.search(padrao, texto))


def planejar(pergunta, meses=(), alvos=()):
    """Retorna plano puro; múltiplas intenções NÃO param na primeira coincidência."""
    t = _normalizar(pergunta)
    flags = set()
    if _tem(t, r'\b(?:analise de confiabilidade|analise da confiabilidade|visao geral|panorama|kpis?|indicadores? gerais?|disponibilidade)\b'):
        flags.add('geral')
    if (_tem(t, r'\b(?:equipament\w*|maquin\w*|robo\w*|mesa\w*)\b')
            and _tem(t, r'\b(?:impact\w*|parad\w*|mais par\w*|maior\w*|ranking|prioridade\w*)\b')) or _tem(t, r'\branking de parada'):
        flags.add('impacto')
    if _tem(t, r'\b(?:reincid\w*|recorr\w*|repetit\w*)\b'):
        flags.add('reincidencias')
    if _tem(t, r'\b(?:mttr|tempo medio de reparo|tempo de reparo)\b'):
        flags.add('mttr')
    if _tem(t, r'\b(?:tendencia|mensal|evolucao)\b') or (meses and _tem(t, r'\bcompar\w*')):
        flags.add('tendencia')
    if _tem(t, r'\b(?:backlog|pendenc\w*|os abertas|envelhecid\w*)\b'):
        flags.add('backlog')
    if _tem(t, r'\b(?:pareto|modos de falha)\b'):
        flags.add('pareto')
    if _tem(t, r'\b(?:ordens? de servico|(?:quais|mostrar|liste)\s+os\b)'):
        flags.add('os')
    if _tem(t, r'\b(?:reduz\w*|melhor\w*|investig\w*|recomend\w*|hipotes\w*|propo\w*|suger\w*|causas?\b|plano de acao)'):
        flags.add('melhorias')
    intencoes = tuple(k for k in ORDEM if k in flags)
    necessarias = {nome for k in intencoes for nome in FERRAMENTAS_POR_INTENCAO[k]}
    ferramentas = tuple(nome for nome in ('consultar_kpis', 'consultar_equipamentos',
        'consultar_reincidencias', 'consultar_tendencia', 'consultar_backlog',
        'consultar_pareto', 'consultar_os') if nome in necessarias)
    interpretativa = 'melhorias' in flags or _tem(t, r'\b(?:analise|analisar|por que|prioriz\w*)\b')
    return {'intencoes': intencoes, 'ferramentas': ferramentas,
            'alvos': tuple(alvos), 'interpretativa': bool(interpretativa),
            'multiplas': len(intencoes) > 1 and set(intencoes) != {'reincidencias', 'melhorias'}}


def _numero(valor):
    try:
        numero = Decimal(str(valor))
        return numero if numero.is_finite() and numero >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _alvo(registro, alvo):
    ident = str(registro.get('equipment_id', ''))
    return ident == alvo or ident.startswith(alvo + '-')


def _registro_evidencia(nome, resultados, eid, linha, periodo, *, alvo=None):
    meta = {'id': eid, 'ferramenta': nome, 'escopo': linha, 'periodo': periodo}
    if alvo:
        meta['equipamento'] = alvo
    return meta


def _resumir_reincidencias(registros, eid, *, alvo=None):
    """Agrupa alertas do mesmo modo sem somar janelas ou contar OS repetidas.

    Alertas de janelas diferentes não são eventos adicionais comprovados;
    preservamos os IDs de OS distintos e declaramos cada janela separadamente.
    """
    agrupados = {}
    for r in registros:
        chave = (str(r.get('equipment_id') or alvo or '?'),
                 str(r.get('modo_nome') or 'não informado'),
                 str(r.get('janela_dias') or '?'))
        grupos = agrupados.setdefault(chave, {'alertas': set(), 'ordens': []})
        os_ids = [x.strip() for x in str(r.get('os_lista') or '').split(',') if x.strip()]
        assinatura = (str(r.get('disparado_em') or r.get('os_gatilho') or ''),
                      str(r.get('ocorrencias') or '?'), tuple(os_ids))
        grupos['alertas'].add(assinatura)
        for os_id in os_ids:
            if os_id not in grupos['ordens']:
                grupos['ordens'].append(os_id)
    fatos = []
    for (equipamento, modo, janela), dados in agrupados.items():
        assinaturas = dados['alertas']
        if len(assinaturas) == 1:
            _, quantidade, _ = next(iter(assinaturas))
            descricao = f"{equipamento}: modo '{modo}', {quantidade} ocorrências em {janela} dias"
        else:
            contagens = sorted({q for _, q, _ in assinaturas})
            detalhe = ('cada alerta registra ' + contagens[0] + ' ocorrências'
                       if len(contagens) == 1 else
                       'alertas com contagens diferentes')
            descricao = (f"{equipamento}: modo '{modo}', {len(assinaturas)} alertas de reincidência "
                         f"em janelas de {janela} dias ({detalhe}; não somar ocorrências)")
        if dados['ordens']:
            descricao += '; OS distintas: ' + ', '.join(dados['ordens'])
        fatos.append(f'{descricao}. — {eid}')
    return fatos


def montar(plano, resultados, *, linha, periodo, meses=()):
    """Produz fatos+matriz+evidências compactas. Não presume ausência fora do recorte."""
    fatos, referencias, pacotes = [], [], []
    estados = {}
    total_resultados = {}
    for nome, linhas in resultados.items():
        total_resultados[nome] = len(linhas) if isinstance(linhas, list) else int(bool(linhas))

    def evidencia(nome, dados, alvo=None):
        eid = f'E{len(referencias)+1}'
        referencias.append(_registro_evidencia(nome, dados, eid, linha, periodo, alvo=alvo))
        pacotes.append({'id': eid, 'consulta': nome, 'alvo': alvo,
                        'registros': recortar(nome, dados)})
        return eid

    kpi = resultados.get('consultar_kpis')
    eq = resultados.get('consultar_equipamentos') or []
    rec = resultados.get('consultar_reincidencias') or []
    ordenados = sorted((r for r in eq if _numero(r.get('parada_min')) is not None),
                       key=lambda r: (-_numero(r['parada_min']), str(r.get('equipment_id'))))
    if 'geral' in plano['intencoes']:
        if isinstance(kpi, dict) and all(kpi.get(k) is not None for k in
                                        ('os_total', 'falhas', 'parada_h', 'disponibilidade')):
            eid = evidencia('consultar_kpis', kpi)
            fatos.append(f"Visão {linha}: {kpi['os_total']} OS, {kpi['falhas']} falhas, "
                         f"parada total {duracao_h(kpi['parada_h'])}, "
                         f"disponibilidade {porcentagem(kpi['disponibilidade'])}. — {eid}")
            estados['geral'] = 'coberta'
        else:
            estados['geral'] = 'sem_dados'
    if 'impacto' in plano['intencoes']:
        if ordenados:
            eid = evidencia('consultar_equipamentos', ordenados[:TOP_N])
            itens = [f"{r['equipment_id']}: {duracao_min(r['parada_min'])} de parada"
                     for r in ordenados[:TOP_N]]
            fatos.append('Ranking por horas de parada (maior → menor): ' + '; '.join(itens) + f'. — {eid}')
            estados['impacto'] = 'coberta'
        else:
            estados['impacto'] = 'sem_dados'
    if 'mttr' in plano['intencoes']:
        mttr = kpi.get('mttr_h') if isinstance(kpi, dict) else None
        if _numero(mttr) is not None:
            eid = next((r['id'] for r in referencias if r['ferramenta'] == 'consultar_kpis'), None)
            if not eid:
                eid = evidencia('consultar_kpis', kpi)
            fatos.append(f"MTTR da linha {linha}: {hora_decimal(mttr)} "
                         f"(aprox. {duracao_h(mttr)}). — {eid}")
        else:
            estados['mttr'] = 'sem_dados'
        alvos_mttr = plano['alvos'] or tuple(r.get('equipment_id') for r in ordenados[:2])
        disponiveis = []
        for alvo in alvos_mttr:
            r = next((r for r in ordenados if r.get('equipment_id') == alvo), None)
            if r is None or _numero(r.get('mttr_h')) is None:
                fatos.append(f'MTTR de {alvo} não disponível no recorte consultado; '
                             'não é possível estimar esse indicador.')
                continue
            eid = evidencia('consultar_equipamentos', [r], alvo)
            fatos.append(f"MTTR {alvo}: {hora_decimal(r['mttr_h'])} "
                         f"(aprox. {duracao_h(r['mttr_h'])}). — {eid}")
            disponiveis.append(alvo)
        if 'mttr' not in estados:
            estados['mttr'] = ('coberta' if len(disponiveis) == len(alvos_mttr)
                               else 'parcial')
    if 'reincidencias' in plano['intencoes']:
        alvos = plano['alvos']
        if alvos:
            faltantes = 0
            for alvo in alvos:
                destaques = [r for r in rec if _alvo(r, alvo)]
                if not destaques:
                    fatos.append(f'{alvo}: nenhuma reincidência identificada nos alertas retornados '
                                 '(a consulta limitada não prova inexistência de falhas).')
                    faltantes += 1
                    continue
                eid = evidencia('consultar_reincidencias', destaques[:2], alvo)
                fatos.extend(_resumir_reincidencias(destaques[:2], eid, alvo=alvo))
            estados['reincidencias'] = ('sem_dados' if faltantes == len(alvos)
                                       else 'parcial' if faltantes else 'coberta')
        elif rec:
            eid = evidencia('consultar_reincidencias', rec[:TOP_N])
            fatos.extend(_resumir_reincidencias(rec[:TOP_N], eid))
            estados['reincidencias'] = 'coberta'
        else:
            estados['reincidencias'] = 'sem_dados'
    if 'backlog' in plano['intencoes']:
        r = resultados.get('consultar_backlog')
        if isinstance(r, dict) and all(r.get(k) is not None for k in
                                       ('os_abertas', 'os_envelhecidas', 'horas_restantes')):
            eid = evidencia('consultar_backlog', r)
            fatos.append(f"Backlog {linha}: {r['os_abertas']} OS abertas, "
                         f"{r['os_envelhecidas']} envelhecidas e "
                         f"{hora_decimal(r['horas_restantes'])} restantes estimadas. — {eid}")
            estados['backlog'] = 'coberta'
        else:
            estados['backlog'] = 'sem_dados'
    if 'tendencia' in plano['intencoes']:
        series = [r for r in (resultados.get('consultar_tendencia') or [])
                  if not meses or int(str(r.get('mes','00'))[-2:]) in meses]
        if series:
            eid = evidencia('consultar_tendencia', series[:6])
            for r in series[:6]:
                fatos.append(f"{r['mes']}: {r['falhas']} falhas; "
                             f"{hora_decimal(r['parada_h'])} de parada. — {eid}")
            estados['tendencia'] = 'coberta'
        else:
            estados['tendencia'] = 'sem_dados'
    if 'pareto' in plano['intencoes']:
        itens = resultados.get('consultar_pareto') or []
        if itens:
            eid = evidencia('consultar_pareto', itens[:TOP_N])
            for r in itens[:TOP_N]:
                medida = r.get('medida')
                valor = duracao_min(r['valor']) if medida == 'parada_min' else str(r.get('valor'))
                fatos.append(f"Pareto: {r.get('modo_nome')} — {valor} ({medida}). — {eid}")
            estados['pareto'] = 'coberta'
        else:
            estados['pareto'] = 'sem_dados'
    if 'os' in plano['intencoes']:
        ordens = resultados.get('consultar_os') or []
        if plano['alvos']:
            ordens = [r for r in ordens if any(_alvo(r, a) for a in plano['alvos'])]
        if ordens:
            eid = evidencia('consultar_os', ordens[:TOP_N])
            for r in ordens[:TOP_N]:
                fatos.append(f"OS {r['task_short_id']}: {r['equipment_id']}, "
                             f"{duracao_min(r.get('parada_min') or 0)} de parada. — {eid}")
            estados['os'] = 'coberta'
        else:
            estados['os'] = 'sem_dados'
    if 'melhorias' in plano['intencoes']:
        validas = any(estados.get(k) == 'coberta' for k in ('geral', 'impacto', 'reincidencias', 'mttr', 'pareto'))
        estados['melhorias'] = 'parcial' if validas else 'sem_dados'
        fatos.append('Melhorias: as medidas acima orientam a investigação; '
                     'causas e ações corretivas exigem validação técnica.')
    for chave in plano['intencoes']:
        if estados.get(chave) != 'coberta':
            fatos.append(f"Cobertura {chave}: {estados.get(chave, 'sem_dados')}; "
                         'não concluir esse ponto sem dados adicionais ou validação.')
    return {'fatos': fatos, 'evidencias': referencias, 'payload_evidencias': pacotes,
            'cobertura': estados, 'total_resultados': total_resultados}
