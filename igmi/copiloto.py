"""IGMI 0.3.0: copiloto de consultas mínimas e IA opcional, sem SQL gerado.

A camada ConsultasDemo (criada por abrir_demo) valida todos os 27 QD e abre
DuckDB somente leitura. Instanciar/usar uma instância validada a cada turno.
"""
from __future__ import annotations

from datetime import date
import json
import re
import unicodedata

from igmi.exceptions import EscopoInvalido
from igmi.ia import IAIndisponivel, RespostaInvalida, _get, criar_cliente
from igmi.ia_economica import (
    INSTRUCOES, recortar, schema, validar_interpretacao, duracao_min, duracao_h,
    hora_decimal, porcentagem,
)

MAX_PERGUNTA = 360
MAX_ITENS = 3
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
    citadas = set(re.findall(r'\bLT\d+\b', pergunta.upper()))
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
    if re.search(r'\b(?:tendencia|mensal|evolucao|compar|meses?)\b', t) or (meses and re.search(r'\b(?:falhas?|paradas?)\b', t)):
        return 'consultar_tendencia', interpretacao
    if re.search(r'\b(?:reincid\w*|recorr\w*|repetit\w*|ventosas?|garra\w*|ferramenta do robo)\b', t):
        return 'consultar_reincidencias', interpretacao
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
    ids = re.findall(r'\bLT\d+-[A-Z0-9-]+\b', pergunta.upper())
    # IDs podem ser LT3-RB01 ou LT3-RB01-FER, sem aceitar fragmentos arbitrários.
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
        self.historico = []
        self._cache = {}
        self._assinatura = None

    def trocar_linha(self, nova_linha, consultas):
        consultas.validar_linha(nova_linha)
        if nova_linha != self.linha:
            self.linha = nova_linha
            self.ultimo_equipamento = None
            self._cache.clear()
            self._assinatura = None
        return self.linha

    def _consulta(self, consultas, nome):
        if nome not in FERRAMENTAS:
            raise EscopoInvalido('Ferramenta não autorizada.')
        key = (self.linha, nome)
        if key not in self._cache:
            metodo = getattr(consultas, nome)
            lim = FERRAMENTAS[nome]
            self._cache[key] = metodo(self.linha, lim) if lim is not None else metodo(self.linha)
        return self._cache[key]

    def perguntar(self, consultas, pergunta, *, autorizar_api=False, cliente=None):
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
            self._assinatura = assinatura
        meses = validar_escopo(consultas, self.linha, pergunta)
        if re.search(r'\bess[ea]\s+equipamento\b', simplificar(pergunta)) and not self.ultimo_equipamento:
            return self._salvar(pergunta, ['Qual equipamento? Informe o ID (ex.: LT3-RB01).'], [], 'esclarecer')
        nome, interpretacao = intencao(pergunta, meses, self.ultimo_equipamento)
        if nome is None:
            return self._salvar(pergunta, ['Consulta fora do escopo. Use /ajuda para ver exemplos.'], [], 'fora_escopo')
        if interpretacao and not autorizar_api:
            return self._salvar(pergunta, ['Esta pergunta pede interpretação. Ative --autorizar-api e confirme '
                                             'a chamada paga, ou reformule como consulta objetiva.'], [], 'sem_autorizacao')
        if interpretacao and self.chamadas_api >= self.limite_api:
            return self._salvar(pergunta, ['Limite local de chamadas à API alcançado nesta sessão.'], [], 'limite')
        registro = self._consulta(consultas, nome)
        fatos, equipamento = _formatar_resultado(nome, registro, self.linha, pergunta, meses, self.ultimo_equipamento)
        if equipamento:
            self.ultimo_equipamento = equipamento
        evidencias = [{'id': 'E1', 'ferramenta': nome, 'escopo': self.linha,
                       'periodo': [str(consultas.contexto['periodo_inicio']), str(consultas.contexto['periodo_fim'])]}]
        if not interpretacao:
            return self._salvar(pergunta, fatos, evidencias, 'dados')
        # Não enviar histórico, nem SQL, nem colunas não permitidas à API.
        selecionados, _ = _selecionar_equipamento(registro if isinstance(registro, list) else [],
                                                 pergunta, self.ultimo_equipamento)
        amostra = recortar(nome, selecionados if isinstance(registro, list) else registro)
        payload = {'pergunta': pergunta, 'linha': self.linha,
                   'periodo': evidencias[0]['periodo'], 'evidencia': {'id': 'E1', 'consulta': nome,
                                                                     'registros': amostra}}
        if cliente is None:
            cliente = criar_cliente()
        self.chamadas_api += 1  # contabiliza tentativa, mesmo se ocorrer falha
        try:
            resposta = cliente.responses.create(
                model=self.modelo, instructions=INSTRUCOES,
                input=[{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False,
                                                              separators=(',', ':'), default=str)}],
                text={'format': {'type': 'json_schema', 'name': 'igmi_qualitativo',
                                 'strict': True, 'schema': schema()}},
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
            dados = validar_interpretacao(_get(resposta, 'output_text'), {
                'E1': {'ferramenta': nome, 'registros': registro, 'escopo': self.linha}})
            # Não há sensores/dados de condição nas ferramentas autorizadas do chat.
            # Não aprovar sugestão categórica de implantar preditiva sem avaliação.
            for rec in dados['recomendacoes']:
                r = simplificar(rec)
                if re.search(r'\b(?:implantar|implementar|adotar|instalar)\b.*\b(?:preditiv\w*|sensores?|monitoramento continuo)\b', r):
                    raise RespostaInvalida('Recomendação preditiva sem dados de condição e viabilidade.')
            complemento = [dados['resumo']]
            complemento += ['Hipótese (não comprovada): ' + x for x in dados['hipoteses']]
            complemento += ['Para avaliação humana: ' + x for x in dados['recomendacoes']]
            complemento += ['Limitação: ' + x for x in dados['limitacoes']]
            status = 'validada'
        except RespostaInvalida as exc:
            complemento = [f'Interpretação bloqueada: {exc}. Nenhuma segunda chamada feita.']
            status = 'bloqueada'
        return self._salvar(pergunta, fatos + complemento, evidencias, status,
                            tokens_entrada=ent, tokens_saida=sai, chamadas=1)

    def _salvar(self, pergunta, linhas, evidencias, status, *, tokens_entrada=0, tokens_saida=0, chamadas=0):
        resultado = {'pergunta': pergunta, 'linha': self.linha, 'status': status,
                     'resposta': linhas, 'evidencias': evidencias,
                     'auditoria': {'chamadas_api': chamadas, 'tokens_entrada': tokens_entrada,
                                  'tokens_saida': tokens_saida}}
        self.historico.append(resultado)
        self.historico = self.historico[-20:]
        return resultado

    def exportar_markdown(self, *, ultimos=10):
        linhas = ['# IGMI 0.3.0 — Conversa de Confiabilidade', '',
                  'Dados sintéticos; não constitui diagnóstico de causa-raiz.', '',
                  f'**Chamadas API na sessão:** {self.chamadas_api} · '
                  f'**Tokens reportados:** {self.tokens_entrada} entrada / {self.tokens_saida} saída', '']
        for item in self.historico[-ultimos:]:
            linhas += [f"## {item['pergunta']}", '', f"Linha: {item['linha']} · Status: {item['status']}", '']
            linhas += ['- ' + r for r in item['resposta']]
            for e in item['evidencias']:
                linhas += [f"- Fonte {e['id']}: {e['ferramenta']} ({e['escopo']}, "
                           f"{e['periodo'][0]} a {e['periodo'][1]})"]
            linhas += ['', f"Tokens neste turno: {item['auditoria']['tokens_entrada']}/"
                       f"{item['auditoria']['tokens_saida']}", '']
        return '\n'.join(linhas) + '\n'


def formatar_turno(r):
    linhas = [f"IGMI [{r['status']}; {r['linha']}; "
              f"{r['auditoria']['chamadas_api']} API]:"]
    linhas += ['  ' + x for x in r['resposta']]
    for e in r['evidencias']:
        linhas += [f"  Evidência {e['id']}: {e['ferramenta']} "
                  f"({e['periodo'][0]} a {e['periodo'][1]})"]
    if r['auditoria']['chamadas_api']:
        linhas += [f"  Tokens: {r['auditoria']['tokens_entrada']}/"
                  f"{r['auditoria']['tokens_saida']}"]
    return '\n'.join(linhas)
