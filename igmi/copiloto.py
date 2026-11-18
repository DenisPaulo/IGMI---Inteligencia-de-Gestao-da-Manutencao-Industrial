"""IGMI 0.3.2.1: copiloto com planejamento multi-intenção, IA opcional.

A camada ConsultasDemo (criada por abrir_demo) valida todos os 27 QD e abre
DuckDB somente leitura. Instanciar/usar uma instância validada a cada turno.
"""
from __future__ import annotations

from datetime import date
import json
import re
import unicodedata

from igmi.exceptions import EscopoInvalido
from igmi.planejador import planejar, montar, MAX_PAYLOAD_CHARS, LIMITE_CONSULTA
from igmi.ia import IAIndisponivel, RespostaInvalida, _get, criar_cliente
from igmi.ia_economica import (
    INSTRUCOES, recortar, schema, validar_interpretacao, duracao_min, duracao_h,
    hora_decimal, porcentagem,
)

MAX_PERGUNTA = 1200
MAX_ITENS = 3
MAX_ALVOS = 3
MAX_CONSULTA_ALVOS = 30
MESES = ('janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho',
         'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro')
FERRAMENTAS = {
    'consultar_kpis': None,
    'consultar_equipamentos': 5,
    'consultar_reincidencias': 5,
    'consultar_pareto': 5,
    'consultar_tendencia': None,
    'consultar_os': 10,
    'consultar_backlog': None,
}


def simplificar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.lower())
                   if not unicodedata.combining(c))


# Sequências ANSI de edição do terminal devem ser descartadas antes da auditoria.
_ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|.)')
_SEGREDO = re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b')


def limpar_texto(texto):
    """Preserva UTF-8 e quebras legítimas, remove controles de cursor/terminal."""
    if not isinstance(texto, str):
        raise EscopoInvalido('Pergunta deve ser texto.')
    texto = _ANSI.sub('', texto.replace('\r\n', '\n').replace('\r', '\n'))
    texto = ''.join(c for c in texto if c in '\n\t' or
                    (ord(c) >= 32 and not 127 <= ord(c) <= 159))
    return _SEGREDO.sub('[SEGREDO OCULTO]', texto).strip()


def identificar_alvos(pergunta, linha):
    """Aliases da demonstração só são aceitos se presentes no resultado real.

    A seleção é feita sobre as linhas retornadas pela consulta autorizada, não
    sobre texto livre transformado em SQL.
    """
    t = simplificar(pergunta)
    alvos = []
    for ident in re.findall(r'\bLR-\d{2}-[A-Z]{2}\d{2}(?:-[A-Z0-9]+)?\b', pergunta.upper()):
        pai = '-'.join(ident.split('-')[:3])
        if pai not in alvos:
            alvos.append(pai)
    if re.search(r'\b(?:robo\w*|garra\w*|ferramenta\w*\s+d[oa]\s+robo)\b', t):
        ident = f'{linha}-RB01'
        if ident not in alvos:
            alvos.append(ident)
    if re.search(r'\b(?:mesa\w*(?:\s+de\s+ventosas?)?|ventosas?)\b', t):
        ident = f'{linha}-MS01'
        if ident not in alvos:
            alvos.append(ident)
    if len(alvos) > MAX_ALVOS:
        raise EscopoInvalido(f'No máximo {MAX_ALVOS} equipamentos por pergunta; divida a análise.')
    return tuple(alvos)


def _do_alvo(registro, alvo):
    ident = str(registro.get('equipment_id', ''))
    return ident == alvo or ident.startswith(alvo + '-')


def schema_multialvo():
    """Cada equipamento precisa de uma análise identificada separadamente."""
    base = schema()
    base['properties']['analises_por_alvo'] = {
        'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                  'properties': {'equipment_id': {'type': 'string'},
                                                 'analise': {'type': 'string'}},
                                  'required': ['equipment_id', 'analise']}}
    base['required'].append('analises_por_alvo')
    return base


def validar_multialvo(texto, alvos, evidencias, *, max_hipoteses=2):
    try:
        bruto = json.loads(texto)
    except (TypeError, ValueError) as exc:
        raise RespostaInvalida('JSON multialvo inválido.') from exc
    if not isinstance(bruto, dict) or set(bruto) != {
            'resumo', 'hipoteses', 'recomendacoes', 'limitacoes', 'analises_por_alvo'}:
        raise RespostaInvalida('Estrutura multialvo incompleta.')
    analises = bruto['analises_por_alvo']
    if not isinstance(analises, list) or len(analises) != len(alvos):
        raise RespostaInvalida('Cobertura incompleta de equipamentos.')
    vistos = set()
    for parte in analises:
        if not isinstance(parte, dict) or set(parte) != {'equipment_id', 'analise'}:
            raise RespostaInvalida('Análise sem identificação de alvo.')
        ident, descricao = parte['equipment_id'], parte['analise']
        if not isinstance(ident, str) or ident not in alvos or ident in vistos:
            raise RespostaInvalida('Alvo repetido ou não solicitado na interpretação.')
        vistos.add(ident)
        if not isinstance(descricao, str) or not 12 <= len(descricao.strip()) <= 300:
            raise RespostaInvalida(f'Interpretação ausente ou excessiva para {ident}.')
        # Reaproveita o validador de números, termos e inconsistências da 0.2.1.
        validar_interpretacao(json.dumps({'resumo': descricao, 'hipoteses': [],
                                          'recomendacoes': [], 'limitacoes': []},
                                         ensure_ascii=False), evidencias)
    if vistos != set(alvos):
        raise RespostaInvalida('Falta análise para um dos equipamentos solicitados.')
    qualitativo = {k: bruto[k] for k in ('resumo', 'hipoteses', 'recomendacoes', 'limitacoes')}
    validar_interpretacao(json.dumps(qualitativo, ensure_ascii=False), evidencias,
                          max_hipoteses=max_hipoteses)
    return bruto


def preparar_multialvo(nome, registros, alvos, contexto, linha):
    """Fatos por alvo, sem misturar OS e mantendo evidências distintas."""
    fatos, evidencias, recortes, ausentes = [], [], [], []
    for i, alvo in enumerate(alvos, 1):
        encontrados = [r for r in registros if _do_alvo(r, alvo)]
        eid = f'E{i}'
        evidencias.append({'id': eid, 'ferramenta': nome, 'escopo': linha,
                           'equipamento': alvo,
                           'periodo': [str(contexto['periodo_inicio']), str(contexto['periodo_fim'])]})
        if not encontrados:
            fatos.append(f'{alvo}: sem registros correspondentes nos {len(registros)} resultados da consulta '
                         f'(limite de até {MAX_CONSULTA_ALVOS}; não é prova de ausência de falhas). — {eid}')
            ausentes.append(alvo)
            continue
        if nome == 'consultar_reincidencias':
            for r in encontrados[:2]:
                fatos.append(f"{r['equipment_id']}: {r['modo_nome']}, {r['ocorrencias']} ocorrências "
                             f"em {r['janela_dias']} dias. OS: {r.get('os_lista', 'não informadas')}. — {eid}")
        elif nome == 'consultar_equipamentos':
            r = encontrados[0]
            fatos.append(f"{r['equipment_id']} ({r.get('nome', 'sem nome')}): {r['falhas']} falhas, "
                         f"parada {duracao_min(r['parada_min'])}, "
                         f"criticidade {r.get('criticidade', 'não informada')}. — {eid}")
        elif nome == 'consultar_os':
            for r in encontrados[:2]:
                fatos.append(f"OS {r['task_short_id']}: {r['equipment_id']} — "
                             f"{duracao_min(r.get('parada_min') or 0)} de parada. — {eid}")
        recortes.append({'id': eid, 'alvo': alvo, 'consulta': nome,
                         'registros': recortar(nome, encontrados[:2])})
    return fatos, evidencias, recortes, ausentes

def validar_escopo(consultas, linha, pergunta):
    consultas.validar_linha(linha)
    if not isinstance(pergunta, str) or not 1 <= len(pergunta.strip()) <= MAX_PERGUNTA:
        raise EscopoInvalido(f'Pergunta deve ter entre 1 e {MAX_PERGUNTA} caracteres.')
    texto = simplificar(pergunta)
    if re.search(r'\b(?:hoje|ontem|agora|atualmente|ultim[oa]s?|semana atual|este mes|mes passado|ano passado)\b', texto):
        raise EscopoInvalido('Dados históricos: informe mês/período do dataset; sem janela móvel.')
    if re.search(r'\b(?:drop\s+table|delete\s+from|truncate\s+table|update\s+\w+\s+set|'
                 r'ignore\s+(?:as\s+)?regras|api.key|credenciais|senha secreta)\b', texto):
        raise EscopoInvalido('Comando operacional ou solicitação de segredo fora do escopo.')
    citadas = set(re.findall(r'\bLR-\d{2}\b', pergunta.upper()))
    if citadas and citadas != {linha}:
        raise EscopoInvalido('A pergunta cita outra linha; utilize /linha para alterar o escopo.')
    c = consultas.contexto
    di, df = date.fromisoformat(str(c['periodo_inicio'])), date.fromisoformat(str(c['periodo_fim']))
    dias = re.findall(r'\b20\d{2}-\d\d-\d\d\b', pergunta)
    if dias and (dias != [di.isoformat(), df.isoformat()]):
        raise EscopoInvalido('Datas filtradas não suportadas: KPIs somente para período fechado.')
    sem_datas = re.sub(r'\b20\d{2}-\d\d-\d\d\b', '', pergunta)
    anos = set(re.findall(r'\b20\d{2}\b', sem_datas))
    if anos and anos != {str(di.year)}:
        raise EscopoInvalido('Ano fora do período do dataset sintético.')
    meses = [m + 1 for m, nome in enumerate(MESES) if re.search(r'\b' + nome + r'\b', texto)]
    if meses and (di.year != df.year or any(m < di.month or m > df.month for m in meses)):
        raise EscopoInvalido('Mês fora do intervalo suportado pela demonstração.')
    return meses


def intencao(pergunta, meses, equipamento_em_contexto=None):
    t = simplificar(pergunta)
    if re.search(r'\b(?:abrir arquivo|crie pasta|executar programa|tempo real|acionar valvula|desligar robo|programar clp)\b', t):
        return None, False
    interpretacao = bool(re.search(r'\b(?:analise|analisar|investig|hipotes|recomend|suger|melhor|causa|por que|plano de acao|prioriz)', t))
    if re.search(r'\b(?:tendencia|mensal|evolucao|meses?)\b', t) or (meses and re.search(r'\b(?:compar\w*|falhas?|paradas?)\b', t)):
        return 'consultar_tendencia', interpretacao
    if re.search(r'\b(?:reincid\w*|recorr\w*|repetit\w*|ventosas?|garra\w*|ferramenta do robo)\b', t):
        return 'consultar_reincidencias', interpretacao
    if re.search(r'\bcompar\w*\b', t) and re.search(
            r'\b(?:robo\w*|garra\w*|ventosas?|mesa\w*|lr-\d{2}-[a-z0-9-]+)\b', t):
        return 'consultar_equipamentos', interpretacao
    if re.search(r'\bcompar\w*\b', t):
        return 'consultar_tendencia', interpretacao
    if re.search(r'\b(?:backlog|pendenc\w*|atrasad\w*|abertas|envelhecid\w*)\b', t):
        return 'consultar_backlog', interpretacao
    if (re.search(r'\bOS\b', pergunta) or re.search(r'\b(?:ordens?|evidencia|justific)\b', t)):
        return 'consultar_os', interpretacao
    if re.search(r'\b(?:pareto|modo de falha)\b', t):
        return 'consultar_pareto', interpretacao
    if re.search(r'\b(?:equipament\w*|robo\w*|maquina\w*|parou mais|mais parou|maior parada|criticidade)\b', t):
        return 'consultar_equipamentos', interpretacao
    if re.search(r'\b(?:kpis?|indicadores?|mttr|mtbf|disponibilidade|total de falhas|quantas? falhas|parada total)\b', t):
        return 'consultar_kpis', interpretacao
    if interpretacao:
        return ('consultar_reincidencias' if equipamento_em_contexto else 'consultar_equipamentos'), True
    return None, False


def _selecionar_equipamento(registros, pergunta, ultimo):
    """Filtrar apenas resultados já consultados; nunca construir SQL do texto."""
    ids = re.findall(r'\bLR-\d{2}-[A-Z0-9-]+\b', pergunta.upper())
    # IDs podem ser LR-01-RB01 ou LR-01-RB01-FER, sem aceitar fragmentos arbitrários.
    t = simplificar(pergunta)
    referencias = bool(re.search(r'\b(?:ess[ea]s?|dessa?s?|justific|relacionad|daquele)\b', t))
    alvo = ids[0] if ids else (ultimo if referencias else None)
    if not alvo:
        for termo in ('ventosa', 'garra', 'ferramenta'):
            if termo in t:
                selecionados = [x for x in registros if termo in simplificar(' '.join(str(x.get(k, '')) for k in
                                  ('equipamento_nome', 'modo_nome', 'nome')))]
                return selecionados, None
        return registros, None
    selecionados = [x for x in registros if str(x.get('equipment_id', '')) == alvo
                   or str(x.get('equipment_id', '')).startswith(alvo + '-')]
    return selecionados, alvo


def _formatar_resultado(nome, registros, linha, pergunta, meses, ultimo):
    """Fatos exatos: nada quantitativo é escrito por IA."""
    if nome == 'consultar_kpis':
        r = registros
        if not r:
            return ['Sem indicadores para a linha.'], None
        return [f"{linha}: {r['os_total']} OS; {r['falhas']} falhas; {r['falhas_com_parada']} com parada; "
                f"parada {duracao_h(r['parada_h'])}; disponibilidade {porcentagem(r['disponibilidade'])}; "
                f"MTTR {hora_decimal(r['mttr_h'])}."], None
    if nome == 'consultar_backlog':
        r = registros
        return [f"{linha}: {r['os_abertas']} OS abertas; {r['os_envelhecidas']} envelhecidas; "
                 f"{hora_decimal(r['horas_restantes'])} restantes estimadas."], None
    if nome == 'consultar_equipamentos':
        escolhidos, alvo = _selecionar_equipamento(registros, pergunta, ultimo)
        if not escolhidos:
            return ['Equipamento não encontrado entre os primeiros resultados da consulta limitada.'], None
        quantidade = 1 if 'mais parou' in simplificar(pergunta) else MAX_ITENS
        linhas = [f"{r['equipment_id']} ({r.get('nome', 'sem nome')}): {r['falhas']} falhas, "
                  f"parada {duracao_min(r['parada_min'])}, criticidade {r.get('criticidade', 'não informada')}."
                  for r in escolhidos[:quantidade]]
        if len(escolhidos) > quantidade:
            linhas.append(f'Mostrando os primeiros {quantidade} de {len(escolhidos)} resultados retornados (consulta limitada).')
        return linhas, (alvo or (escolhidos[0]['equipment_id'] if len(escolhidos) == 1 or 'mais' in simplificar(pergunta) else None))
    if nome == 'consultar_reincidencias':
        escolhidos, alvo = _selecionar_equipamento(registros, pergunta, ultimo)
        if not escolhidos:
            return ['Sem reincidências correspondentes nos alertas retornados.'], None
        linhas = [f"{r['equipment_id']}: {r['modo_nome']}, {r['ocorrencias']} ocorrências em "
                  f"{r['janela_dias']} dias. OS: {r.get('os_lista', 'não informadas')}."
                  for r in escolhidos[:MAX_ITENS]]
        if len(escolhidos) > MAX_ITENS:
            linhas.append(f'Mostrando {MAX_ITENS} dos {len(escolhidos)} alertas retornados (consulta limitada).')
        ids = {x['equipment_id'] for x in escolhidos}
        return linhas, (alvo or (next(iter(ids)) if len(ids) == 1 else None))
    if nome == 'consultar_os':
        escolhidos, alvo = _selecionar_equipamento(registros, pergunta, ultimo)
        if not escolhidos:
            return ['Nenhuma OS correspondente entre as maiores paradas retornadas; consulta parcial, não exaustiva.'], None
        linhas = [f"OS {r['task_short_id']} · {r['equipment_id']} · modo {r.get('modo_id', '?')} · "
                  f"{duracao_min(r.get('parada_min') or 0)} de parada."
                  for r in escolhidos[:MAX_ITENS]]
        return linhas + ['A consulta de OS retorna as maiores paradas, não todo o histórico.'], alvo
    if nome == 'consultar_pareto':
        if not registros:
            return ['Não há modos de falha para o Pareto.'], None
        return [f"{r['modo_nome']}: " +
                (f"{duracao_min(r['valor'])} de parada" if r['medida'] == 'parada_min'
                 else f"{r['valor']} ({r['medida']})")
                for r in registros[:MAX_ITENS]], None
    if nome == 'consultar_tendencia':
        subset = [r for r in registros if not meses or int(str(r['mes'])[-2:]) in meses]
        if not subset:
            return ['Nenhum indicador mensal encontrado para os meses informados.'], None
        return [f"{r['mes']}: {r['falhas']} falhas, {hora_decimal(r['parada_h'])} de parada; "
                f"disponibilidade {porcentagem(r['disponibilidade'])}." for r in subset], None
    raise EscopoInvalido('Consulta desconhecida.')


class SessaoCopiloto:
    """Estado efêmero na memória; sem gravação automática nem histórico na API."""

    def __init__(self, linha, *, modelo='', limite_api=3):
        if type(limite_api) is not int or not 0 <= limite_api <= 10:
            raise ValueError('limite_api deve estar entre 0 e 10')
        self.linha = linha
        self.modelo = modelo
        self.limite_api = limite_api
        self.chamadas_api = 0
        self.tokens_entrada = 0
        self.tokens_saida = 0
        self.ultimo_equipamento = None
        self.ultimos_alvos = ()
        self.historico = []
        self._cache = {}
        self._assinatura = None

    def trocar_linha(self, nova_linha, consultas):
        consultas.validar_linha(nova_linha)
        if nova_linha != self.linha:
            self.linha = nova_linha
            self.ultimo_equipamento = None
            self.ultimos_alvos = ()
            self._cache.clear()
            self._assinatura = None
        return self.linha

    def _consulta(self, consultas, nome, *, limite=None):
        if nome not in FERRAMENTAS:
            raise EscopoInvalido('Ferramenta não autorizada.')
        lim = limite if limite is not None else FERRAMENTAS[nome]
        key = (self.linha, nome, lim)
        if key not in self._cache:
            metodo = getattr(consultas, nome)
            self._cache[key] = metodo(self.linha, lim) if lim is not None else metodo(self.linha)
        return self._cache[key]

    def _perguntar_planejado(self, consultas, pergunta, plano, meses, *, autorizar_api=False, cliente=None):
        """Múltiplas ferramentas em leituras locais; no máximo UMA chamada paga."""
        periodo = [str(consultas.contexto['periodo_inicio']),
                   str(consultas.contexto['periodo_fim'])]
        # A seleção é local, baseada numa allowlist. O texto do usuário NÃO vira SQL.
        resultados = {}
        for nome in plano['ferramentas']:
            resultados[nome] = self._consulta(
                consultas, nome, limite=LIMITE_CONSULTA if nome in
                ('consultar_equipamentos', 'consultar_reincidencias', 'consultar_os')
                and plano['alvos'] else None)
        saida = montar(plano, resultados, linha=self.linha, periodo=periodo, meses=meses)
        fatos, evidencias, cobertura = saida['fatos'], saida['evidencias'], saida['cobertura']
        if plano['alvos']:
            self.ultimos_alvos = plano['alvos']
            self.ultimo_equipamento = plano['alvos'][0] if len(plano['alvos']) == 1 else None
        if any(v != 'coberta' for k, v in cobertura.items() if k != 'melhorias') or not evidencias:
            return self._salvar(pergunta, fatos +
                ['Análise parcial: não há evidências suficientes para todos os subobjetivos; '
                 'nenhuma chamada à API realizada.'], evidencias, 'parcial_sem_dados',
                cobertura=cobertura, ferramentas=plano['ferramentas'])
        if not plano['interpretativa']:
            return self._salvar(pergunta, fatos, evidencias, 'dados',
                               cobertura=cobertura, ferramentas=plano['ferramentas'])
        if not autorizar_api:
            return self._salvar(pergunta, fatos +
                ['Interpretação opcional não executada: para usar IA, inicie o chat com '
                 '--autorizar-api e confirme AUTORIZAR.'], evidencias, 'sem_autorizacao',
                cobertura=cobertura, ferramentas=plano['ferramentas'])
        if self.chamadas_api >= self.limite_api:
            return self._salvar(pergunta, fatos +
                ['Teto local de chamadas à API atingido; fatos determinísticos preservados.'],
                evidencias, 'limite', cobertura=cobertura, ferramentas=plano['ferramentas'])
        payload = {'pergunta': pergunta, 'linha': self.linha, 'periodo': periodo,
                   'intencoes': list(plano['intencoes']), 'cobertura': cobertura,
                   'alvos_obrigatorios': list(plano['alvos']),
                   'evidencias': saida['payload_evidencias']}
        entrada = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str)
        if len(entrada) > MAX_PAYLOAD_CHARS:
            return self._salvar(pergunta, fatos +
                ['Contexto excessivo para a política econômica; divida a pergunta. '
                 'Nenhuma chamada paga realizada.'], evidencias, 'limite_contexto',
                cobertura=cobertura, ferramentas=plano['ferramentas'])
        multialvo = len(plano['alvos']) > 1
        texto_pedido = simplificar(pergunta)
        tres_acoes = bool(re.search(
            r'\b(?:proponha|sugira|liste|indique|apresente)\s+(?:3|tres)\s+'
            r'(?:acoes?|recomendacoes?|medidas?)\b', texto_pedido))
        # Apenas no fluxo planejado admitimos até três hipóteses curtas;
        # os comandos anteriores continuam validando, por padrão, no máximo duas.
        instrucoes_planejadas = INSTRUCOES.replace('duas hipóteses', 'até três hipóteses')
        instr = (instrucoes_planejadas + '\nA interpretação deve tratar TODOS os temas de intencoes, '
                 'sem omitir impacto, MTTR ou reincidencias quando solicitados. '
                 'Nao repita numeros: o Python ja apresenta os fatos. '
                 'Nao afirme causa-raiz. Cite modos tecnicos como informados. '
                 'Recomendacoes sobre MTTR devem propor verificacao do processo de diagnostico/reparo. '
                 'Cada recomendacao deve ser tecnica, testavel, proporcional a evidencia e sem afirmar causa-raiz. '
                 'Hipoteses no maximo tres, cada uma com frase curta.')
        if tres_acoes:
            instr += '\nO usuario pediu tres acoes praticas: forneca EXATAMENTE tres recomendacoes distintas.'
        if multialvo:
            instr += ('\nPara cada ID em alvos_obrigatorios, escreva uma analise distinta '
                      'em analises_por_alvo, com equipment_id identico ao do pedido. '
                      'Nao misture equipamentos; sem numeros na narrativa.')
        dados_evidencias = {}
        for item in saida['payload_evidencias']:
            dados_evidencias[item['id']] = {'ferramenta': item['consulta'],
                                           'registros': item['registros'], 'escopo': self.linha}
        if cliente is None:
            cliente = criar_cliente()
        self.chamadas_api += 1
        try:
            resposta = cliente.responses.create(
                model=self.modelo, instructions=instr,
                input=[{'role': 'user', 'content': entrada}],
                text={'format': {'type': 'json_schema', 'name': 'igmi_planejado',
                                 'strict': True,
                                 'schema': schema_multialvo() if multialvo else schema()}},
                max_output_tokens=650 if multialvo else 500, store=False,
            )
        except Exception as exc:
            return self._salvar(pergunta, fatos +
                [f'IA indisponível ({type(exc).__name__}); nenhum retry automático.'],
                evidencias, 'erro_api', cobertura=cobertura, ferramentas=plano['ferramentas'],
                chamadas=1)
        uso = _get(resposta, 'usage')
        ent = int(_get(uso, 'input_tokens', 0) or 0)
        sai = int(_get(uso, 'output_tokens', 0) or 0)
        self.tokens_entrada += ent
        self.tokens_saida += sai
        try:
            if _get(resposta, 'status') not in (None, 'completed'):
                raise RespostaInvalida('Resposta da API incompleta.')
            interpretacao = (validar_multialvo(_get(resposta, 'output_text'),
                                            plano['alvos'], dados_evidencias,
                                            max_hipoteses=3)
                            if multialvo else validar_interpretacao(
                                _get(resposta, 'output_text'), dados_evidencias,
                                max_hipoteses=3))
            if 'melhorias' in plano['intencoes']:
                if tres_acoes and len(interpretacao['recomendacoes']) != 3:
                    raise RespostaInvalida('O pedido de três ações práticas não foi atendido.')
                if not interpretacao['recomendacoes']:
                    raise RespostaInvalida('Recomendações para a melhoria foram omitidas.')
                if 'mttr' in plano['intencoes'] and not any(re.search(
                        r'\b(?:mttr|reparo|diagnostic\w*|tempo de|atendimento|intervencao)\b',
                        simplificar(item)) for item in interpretacao['recomendacoes']):
                    raise RespostaInvalida('Faltou proposta de investigação do MTTR.')
            for rec in interpretacao['recomendacoes']:
                if re.search(r'\b(?:implantar|implementar|adotar|instalar)\b.*\b(?:preditiv\w*|sensores?|monitoramento continuo)\b',
                             simplificar(rec)):
                    raise RespostaInvalida('Preditiva categórica sem dados de condição.')
            if 'melhorias' in cobertura:
                cobertura['melhorias'] = 'coberta'
                fatos = [x for x in fatos if not x.startswith('Cobertura melhorias:')]
            complemento = [interpretacao['resumo']]
            if multialvo:
                complemento.extend(f"{p['equipment_id']}: {p['analise']}"
                                   for p in interpretacao['analises_por_alvo'])
            complemento.extend('Hipótese (não comprovada): ' + x for x in interpretacao['hipoteses'])
            complemento.extend('Para avaliação humana: ' + x for x in interpretacao['recomendacoes'])
            complemento.extend('Limitação: ' + x for x in interpretacao['limitacoes'])
            status = 'validada' if all(v == 'coberta' for v in cobertura.values()) else 'parcial'
        except RespostaInvalida as exc:
            complemento = [f'Interpretação bloqueada: {exc}. Nenhuma segunda chamada paga.']
            status = 'bloqueada'
        return self._salvar(pergunta, fatos + complemento, evidencias, status,
                            cobertura=cobertura, ferramentas=plano['ferramentas'],
                            chamadas=1, tokens_entrada=ent, tokens_saida=sai)

    def perguntar(self, consultas, pergunta, *, autorizar_api=False, cliente=None):
        pergunta = limpar_texto(pergunta)
        # CLI reabre ConsultasDemo validado por turno. Identidade da carga invalida cache.
        assinatura = json.dumps(consultas.contexto, ensure_ascii=False, sort_keys=True, default=str)
        try:
            from pmb import config
            arquivo = config.WAREHOUSE.parent / 'demo.duckdb'
            if arquivo.is_file():
                st = arquivo.stat()
                assinatura += f'|{st.st_mtime_ns}|{st.st_size}'
        except (ImportError, OSError):
            pass
        if assinatura != self._assinatura:
            self._cache.clear()
            self.ultimo_equipamento = None
            self.ultimos_alvos = ()
            self._assinatura = assinatura
        meses = validar_escopo(consultas, self.linha, pergunta)
        alvos = identificar_alvos(pergunta, self.linha)
        referencia_singular = bool(re.search(r'\bess[ea]\s+equipamento\b', simplificar(pergunta)))
        referencias_ambiguas = bool(re.search(
            r'\b(?:ess[ea]s?|dess[ea]s?|justific\w*|relacionad\w*|daquel\w*)\b',
            simplificar(pergunta)))
        if not alvos and len(self.ultimos_alvos) > 1 and referencias_ambiguas:
            return self._salvar(pergunta, ['Sua pergunta pode se referir a: ' +
                ', '.join(self.ultimos_alvos) + '. Informe um ou ambos explicitamente.'],
                [], 'esclarecer')
        if referencia_singular and not alvos and len(self.ultimos_alvos) != 1:
            return self._salvar(pergunta, ['Qual equipamento? Informe o ID (ex.: LR-01-RB01).'], [], 'esclarecer')
        if referencia_singular and not alvos and len(self.ultimos_alvos) == 1:
            alvos = self.ultimos_alvos
        plano = planejar(pergunta, meses, alvos)
        if plano['multiplas']:
            return self._perguntar_planejado(consultas, pergunta, plano, meses,
                                             autorizar_api=autorizar_api, cliente=cliente)
        nome, interpretacao = intencao(pergunta, meses, self.ultimo_equipamento)
        if nome is None:
            return self._salvar(pergunta, ['Consulta fora do escopo. Use /ajuda para ver exemplos.'], [], 'fora_escopo')
        if interpretacao and not autorizar_api:
            return self._salvar(pergunta, ['Esta pergunta pede interpretação. Ative --autorizar-api e confirme '
                                             'a chamada paga, ou reformule como consulta objetiva.'], [], 'sem_autorizacao')
        if interpretacao and self.chamadas_api >= self.limite_api:
            return self._salvar(pergunta, ['Limite local de chamadas à API alcançado nesta sessão.'], [], 'limite')
        # Multialvo usa no máximo 30 linhas já filtradas para a linha em SQL fixo.
        multialvo = len(alvos) > 1
        if multialvo and nome not in ('consultar_reincidencias', 'consultar_equipamentos', 'consultar_os'):
            return self._salvar(pergunta,
                ['Para comparar esses equipamentos, cite falhas, reincidências ou OS; '
                 'esta consulta não permite filtro seguro por equipamento.'], [], 'esclarecer')
        registro = self._consulta(consultas, nome,
                                 limite=MAX_CONSULTA_ALVOS if multialvo else None)
        periodo = [str(consultas.contexto['periodo_inicio']), str(consultas.contexto['periodo_fim'])]
        if multialvo:
            fatos, evidencias, recortes, ausentes = preparar_multialvo(
                nome, registro, alvos, consultas.contexto, self.linha)
            self.ultimo_equipamento = None
            self.ultimos_alvos = alvos
            if ausentes:
                return self._salvar(pergunta, fatos +
                    ['Análise parcial: faltam evidências no recorte consultado para: ' +
                     ', '.join(ausentes) + '. Nenhuma chamada paga foi realizada.'],
                    evidencias, 'parcial_sem_dados')
            if not interpretacao:
                return self._salvar(pergunta, fatos, evidencias, 'dados')
            payload = {'pergunta': pergunta, 'linha': self.linha, 'periodo': periodo,
                       'alvos_obrigatorios': list(alvos), 'evidencias': recortes}
            formato = schema_multialvo()
            instrucoes = (INSTRUCOES + '\nPara CADA alvo em alvos_obrigatorios, gere uma analise '
                          'breve em analises_por_alvo, com equipment_id EXATAMENTE igual ao informado. '
                          'Nao omita nem misture os equipamentos. ''Os IDs literais do campo equipment_id sao permitidos, mesmo contendo digitos; ''SEM numeros no texto das analises ou recomendacoes.')
            evidencias_validacao = {e['id']: {'ferramenta': nome,
                'registros': [r for r in registro if _do_alvo(r, e['equipamento'])],
                'escopo': self.linha} for e in evidencias}
        else:
            fatos, equipamento = _formatar_resultado(
                nome, registro, self.linha, pergunta, meses, self.ultimo_equipamento)
            if alvos:
                self.ultimos_alvos = alvos
                self.ultimo_equipamento = alvos[0]
            elif equipamento:
                self.ultimo_equipamento = equipamento
                self.ultimos_alvos = (equipamento,)
            evidencias = [{'id': 'E1', 'ferramenta': nome, 'escopo': self.linha,
                           'periodo': periodo}]
            if not interpretacao:
                return self._salvar(pergunta, fatos, evidencias, 'dados')
            selecionados, _ = _selecionar_equipamento(registro if isinstance(registro, list) else [],
                                                     pergunta, self.ultimo_equipamento)
            amostra = recortar(nome, selecionados if isinstance(registro, list) else registro)
            payload = {'pergunta': pergunta, 'linha': self.linha,
                       'periodo': periodo, 'evidencia': {'id': 'E1', 'consulta': nome,
                                                        'registros': amostra}}
            formato = schema()
            instrucoes = INSTRUCOES
            evidencias_validacao = {'E1': {'ferramenta': nome,
                                           'registros': registro, 'escopo': self.linha}}
        if cliente is None:
            cliente = criar_cliente()
        self.chamadas_api += 1  # contabiliza tentativa, mesmo se ocorrer falha
        try:
            resposta = cliente.responses.create(
                model=self.modelo, instructions=instrucoes,
                input=[{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False,
                                                              separators=(',', ':'), default=str)}],
                text={'format': {'type': 'json_schema', 'name': 'igmi_qualitativo',
                                 'strict': True, 'schema': formato}},
                max_output_tokens=450, store=False,
            )
        except Exception as exc:
            return self._salvar(pergunta, fatos + [f'IA indisponível ({type(exc).__name__}); '
                                                  'fatos acima permanecem válidos.'],
                                evidencias, 'erro_api')
        uso = _get(resposta, 'usage')
        ent = int(_get(uso, 'input_tokens', 0) or 0)
        sai = int(_get(uso, 'output_tokens', 0) or 0)
        self.tokens_entrada += ent
        self.tokens_saida += sai
        try:
            if _get(resposta, 'status') not in (None, 'completed'):
                raise RespostaInvalida('A API retornou resposta incompleta.')
            dados = (validar_multialvo(_get(resposta, 'output_text'), alvos, evidencias_validacao)
                     if multialvo else validar_interpretacao(
                         _get(resposta, 'output_text'), evidencias_validacao))
            # Não há sensores/dados de condição nas ferramentas autorizadas do chat.
            # Não aprovar sugestão categórica de implantar preditiva sem avaliação.
            for rec in dados['recomendacoes']:
                r = simplificar(rec)
                if re.search(r'\b(?:implantar|implementar|adotar|instalar)\b.*\b(?:preditiv\w*|sensores?|monitoramento continuo)\b', r):
                    raise RespostaInvalida('Recomendação preditiva sem dados de condição e viabilidade.')
            complemento = [dados['resumo']]
            if multialvo:
                complemento += [f"{parte['equipment_id']}: {parte['analise']}"
                                for parte in dados['analises_por_alvo']]
            complemento += ['Hipótese (não comprovada): ' + x for x in dados['hipoteses']]
            complemento += ['Para avaliação humana: ' + x for x in dados['recomendacoes']]
            complemento += ['Limitação: ' + x for x in dados['limitacoes']]
            status = 'validada'
        except RespostaInvalida as exc:
            complemento = [f'Interpretação bloqueada: {exc}. Nenhuma segunda chamada feita.']
            status = 'bloqueada'
        return self._salvar(pergunta, fatos + complemento, evidencias, status,
                            tokens_entrada=ent, tokens_saida=sai, chamadas=1)

    def _salvar(self, pergunta, linhas, evidencias, status, *, tokens_entrada=0, tokens_saida=0,
                chamadas=0, cobertura=None, ferramentas=()):
        resultado = {'pergunta': pergunta, 'linha': self.linha, 'status': status,
                     'resposta': linhas, 'evidencias': evidencias,
                     'cobertura': dict(cobertura or {}),
                     'auditoria': {'chamadas_api': chamadas, 'tokens_entrada': tokens_entrada,
                                  'tokens_saida': tokens_saida, 'ferramentas': list(ferramentas)}}
        self.historico.append(resultado)
        return resultado

    def exportar_markdown(self, *, ultimos=None):
        """Exporta todos os turnos concluídos desta sessão, sem truncamento tácito."""
        linhas = ['# IGMI 0.3.2.1 — Conversa de Confiabilidade', '',
                  'Dados sintéticos; não constitui diagnóstico de causa-raiz.', '',
                  f'**Chamadas API na sessão:** {self.chamadas_api} · '
                  f'**Tokens reportados:** {self.tokens_entrada} entrada / {self.tokens_saida} saída', '']
        itens = self.historico if ultimos is None else self.historico[-ultimos:]
        for n, item in enumerate(itens, 1):
            linhas += [f"## Turno {n} — {item['status']}", '', '**Pergunta:**', '']
            linhas += ['> ' + limpar_texto(t) for t in item['pergunta'].splitlines()]
            linhas += ['', f"**Linha:** {item['linha']} · **Status:** {item['status']}", '',
                      '**Resposta:**', '']
            for resposta in item['resposta']:
                linhas += ['- ' + limpar_texto(resposta).replace('\n', ' ')]
            for e in item['evidencias']:
                alvo = f" · Equipamento: {e['equipamento']}" if e.get('equipamento') else ''
                linhas += [f"- Fonte {e['id']}: {e['ferramenta']} "
                           f"({e['escopo']}{alvo}, {e['periodo'][0]} a {e['periodo'][1]})"]
            if item.get('cobertura'):
                linhas.append('- Cobertura: ' + '; '.join(
                    f'{k}={v}' for k, v in item['cobertura'].items()))
            if item['auditoria'].get('ferramentas'):
                linhas.append('- Ferramentas: ' + ', '.join(item['auditoria']['ferramentas']))
            linhas += ['', f"API neste turno: {item['auditoria']['chamadas_api']} · Tokens: "
                      f"{item['auditoria']['tokens_entrada']}/{item['auditoria']['tokens_saida']}", '']
        return '\n'.join(linhas) + '\n'


def formatar_turno(r):
    linhas = [f"IGMI [{r['status']}; {r['linha']}; "
              f"{r['auditoria']['chamadas_api']} API]:"]
    linhas += ['  ' + x for x in r['resposta']]
    for e in r['evidencias']:
        alvo = f" · {e['equipamento']}" if e.get('equipamento') else ''
        linhas += [f"  Evidência {e['id']}: {e['ferramenta']}{alvo} "
                  f"({e['periodo'][0]} a {e['periodo'][1]})"]
    if r.get('cobertura'):
        linhas += ['  Cobertura: ' + ', '.join(f'{k}={v}' for k, v in r['cobertura'].items())]
    if r['auditoria']['chamadas_api']:
        linhas += [f"  Tokens: {r['auditoria']['tokens_entrada']}/"
                  f"{r['auditoria']['tokens_saida']}"]
    return '\n'.join(linhas)
