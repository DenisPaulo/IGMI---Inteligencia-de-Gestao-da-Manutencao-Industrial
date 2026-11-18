"""IGMI 0.3.2: múltiplas consultas, cobertura, economia e segurança (sem API real)."""
import json
from unittest import TestCase

from igmi.planejador import planejar, montar
from igmi.copiloto import SessaoCopiloto
from igmi.exceptions import EscopoInvalido
from test_copiloto import DadosFake, ClienteMultialvoFake

PERGUNTA_COMPLETA = (
    'Quero uma análise da confiabilidade da LR-01. Quais equipamentos mais impactam '
    'as paradas? Quais falhas são reincidentes no robô e na mesa de ventosas? '
    'O que devemos investigar para reduzir as quebras e o MTTR? '
    'Separe fatos, hipóteses e recomendações práticas.'
)


class DadosComMTTR(DadosFake):
    def consultar_equipamentos(self, linha, limite):
        dados = super().consultar_equipamentos(linha, limite)
        dados[0]['mttr_h'] = 1.31
        dados[1]['mttr_h'] = 0.91
        return dados


class ModeloAdequado(ClienteMultialvoFake):
    def __init__(self):
        super().__init__()
        dados = json.loads(self.respostas)
        dados['resumo'] = 'As paradas concentram-se no robô, e há reincidência também na mesa de ventosas.'
        dados['recomendacoes'] = ['Revisar os procedimentos de diagnóstico e reparo com a equipe.']
        self.respostas = json.dumps(dados, ensure_ascii=False)


class TestPlanejador(TestCase):
    def test_plano_completo_todas_intencoes_e_tres_ferramentas(self):
        p = planejar(PERGUNTA_COMPLETA, (), ('LR-01-RB01', 'LR-01-MS01'))
        self.assertEqual(p['intencoes'], ('geral', 'impacto', 'reincidencias', 'mttr', 'melhorias'))
        self.assertEqual(p['ferramentas'], ('consultar_kpis', 'consultar_equipamentos',
                                           'consultar_reincidencias'))
        self.assertTrue(p['interpretativa'])
        self.assertTrue(p['multiplas'])

    def test_backlog_sem_plano_composto(self):
        p = planejar('Como está o backlog?')
        self.assertEqual(p['ferramentas'], ('consultar_backlog',))
        self.assertFalse(p['multiplas'])

    def test_mttr_e_reincidencias_duas_intencoes_sem_ia(self):
        p = planejar('Qual é o MTTR e quais reincidências na mesa de ventosas?',
                     (), ('LR-01-MS01',))
        self.assertEqual(p['ferramentas'], ('consultar_kpis', 'consultar_equipamentos',
                                           'consultar_reincidencias'))
        self.assertFalse(p['interpretativa'])
        db = DadosComMTTR()
        resposta = SessaoCopiloto('LR-01').perguntar(
            db, 'Qual é o MTTR e quais reincidências na mesa de ventosas?')
        txt = ' '.join(resposta['resposta'])
        self.assertEqual(resposta['status'], 'dados')
        self.assertIn('MTTR', txt)
        self.assertIn('Ventosa danificada', txt)
        self.assertEqual(resposta['auditoria']['chamadas_api'], 0)

    def test_pergunta_completa_offline_evidencias_precisas(self):
        db = DadosComMTTR()
        resposta = SessaoCopiloto('LR-01').perguntar(db, PERGUNTA_COMPLETA)
        texto = ' '.join(resposta['resposta'])
        self.assertEqual(resposta['status'], 'sem_autorizacao')
        self.assertEqual(resposta['auditoria']['chamadas_api'], 0)
        self.assertIn('57 h 45 min', texto)
        self.assertIn('98,47%', texto)
        self.assertIn('26 h 08 min', texto)
        self.assertIn('MTTR LR-01-RB01: 1,31 h (aprox. 1 h 19 min)', texto)
        self.assertIn('LR-01-MS01', texto)
        self.assertIn('dd00009c', texto)
        self.assertIn('dd000090', texto)
        self.assertEqual(db.chamadas, [('kpi', 'LR-01'), ('equip', 'LR-01', 30), ('rec', 'LR-01', 30)])
        self.assertEqual(resposta['cobertura']['impacto'], 'coberta')
        self.assertEqual(resposta['cobertura']['reincidencias'], 'coberta')
        self.assertEqual(resposta['cobertura']['mttr'], 'coberta')

    def test_api_uma_unica_chamada_e_resposta_cobre_alvos(self):
        db = DadosComMTTR()
        cliente = ModeloAdequado()
        sessao = SessaoCopiloto('LR-01', modelo='mock', limite_api=1)
        r = sessao.perguntar(db, PERGUNTA_COMPLETA, autorizar_api=True, cliente=cliente)
        self.assertEqual(r['status'], 'validada', r['resposta'])
        self.assertEqual(len(cliente.calls), 1)
        self.assertEqual(sessao.chamadas_api, 1)
        self.assertEqual(r['cobertura']['melhorias'], 'coberta')
        payload = json.loads(cliente.calls[0]['input'][0]['content'])
        self.assertLessEqual(len(cliente.calls[0]['input'][0]['content']), 5800)
        self.assertEqual(payload['intencoes'], ['geral', 'impacto', 'reincidencias',
                                                 'mttr', 'melhorias'])
        self.assertEqual(payload['alvos_obrigatorios'], ['LR-01-RB01', 'LR-01-MS01'])
        self.assertNotIn('NUNCA_ENVIAR', str(payload))
        self.assertEqual(r['auditoria']['ferramentas'], ['consultar_kpis',
                             'consultar_equipamentos', 'consultar_reincidencias'])
        # Reenvio de uma pergunta quando já atingiu limite NÃO realiza segunda API.
        r2 = sessao.perguntar(db, PERGUNTA_COMPLETA, autorizar_api=True, cliente=cliente)
        self.assertEqual(r2['status'], 'limite')
        self.assertEqual(len(cliente.calls), 1)

    def test_ausencia_de_mesa_na_reincidencia_nao_cobra(self):
        class SemMesa(DadosComMTTR):
            def consultar_reincidencias(self, linha, limite):
                return super().consultar_reincidencias(linha, limite)[:1]
        client = ModeloAdequado()
        r = SessaoCopiloto('LR-01').perguntar(
            SemMesa(), PERGUNTA_COMPLETA, autorizar_api=True, cliente=client)
        self.assertEqual(r['status'], 'parcial_sem_dados')
        self.assertEqual(r['cobertura']['reincidencias'], 'parcial')
        self.assertEqual(len(client.calls), 0)
        self.assertIn('LR-01-MS01', ' '.join(r['resposta']))

    def test_ausencia_mttr_nao_inventa_nem_cobra(self):
        client = ModeloAdequado()
        r = SessaoCopiloto('LR-01').perguntar(
            DadosFake(), PERGUNTA_COMPLETA, autorizar_api=True, cliente=client)
        self.assertEqual(r['status'], 'parcial_sem_dados')
        self.assertEqual(r['cobertura']['mttr'], 'parcial')
        self.assertEqual(len(client.calls), 0)

    def test_injecao_e_linha_cruzada_bloqueadas_antes_consultas(self):
        for p in ('Analise LR-01 e LR-02 e o MTTR', 'Analise LR-01; DROP TABLE gold.falhas'):
            db = DadosComMTTR()
            with self.assertRaises(EscopoInvalido):
                SessaoCopiloto('LR-01').perguntar(db, p)
            self.assertEqual(db.chamadas, [])

    def test_modelo_omitiu_alvo_bloqueia_sem_repetir(self):
        cliente = ModeloAdequado()
        dados = json.loads(cliente.respostas)
        dados['analises_por_alvo'] = dados['analises_por_alvo'][:1]
        cliente.respostas = json.dumps(dados, ensure_ascii=False)
        r = SessaoCopiloto('LR-01').perguntar(
            DadosComMTTR(), PERGUNTA_COMPLETA, autorizar_api=True, cliente=cliente)
        self.assertEqual(r['status'], 'bloqueada')
        self.assertEqual(len(cliente.calls), 1)
        self.assertIn('26 h 08 min', ' '.join(r['resposta']))

    def test_exportacao_contém_cobertura_e_pergunta_inteira(self):
        s = SessaoCopiloto('LR-01')
        s.perguntar(DadosComMTTR(), PERGUNTA_COMPLETA)
        md = s.exportar_markdown()
        self.assertIn('## Turno 1', md)
        self.assertIn('Cobertura: ', md)
        self.assertIn('consultar_kpis', md)
        self.assertIn('MTTR?', md)
        self.assertNotIn('NUNCA_ENVIAR', md)

    def test_repeticao_mesma_carga_reusa_tres_consultas(self):
        db = DadosComMTTR()
        s = SessaoCopiloto('LR-01')
        s.perguntar(db, PERGUNTA_COMPLETA)
        s.perguntar(db, PERGUNTA_COMPLETA)
        self.assertEqual(len(db.chamadas), 3)
        db.contexto['data_carga'] = '2026-10-04'
        s.perguntar(db, PERGUNTA_COMPLETA)
        self.assertEqual(len(db.chamadas), 6)



def test_cli_mostra_todas_as_consultas_e_confirma_uma_vez():
    from igmi.chat_cli import main
    from test_copiloto import ContextoCLI
    cliente = ModeloAdequado()
    saidas = []
    entradas = iter(['/pergunta',
                     'Quero uma análise da confiabilidade da LR-01.',
                     'Quais equipamentos mais impactam as paradas?',
                     'Quais falhas são reincidentes no robô e na mesa de ventosas?',
                     'O que investigar para reduzir as quebras e o MTTR?',
                     'Separe fatos, hipóteses e recomendações práticas.',
                     '/fim', 'AUTORIZAR', '/resumo', '/sair'])
    rc = main(['--linha', 'LR-01', '--modelo', 'mock', '--autorizar-api',
               '--max-chamadas', '1'], entrada=lambda _: next(entradas),
              saida=saidas.append, abrir=lambda: ContextoCLI(DadosComMTTR()),
              cliente=cliente)
    assert rc == 0
    assert len(cliente.calls) == 1
    assert any('consultar_kpis, consultar_equipamentos, consultar_reincidencias' in s for s in saidas)
    assert any('IGMI [validada' in s for s in saidas)
    assert any('API: 1/1' in s for s in saidas)


def test_recomendacao_ausente_mttr_bloqueada_sem_retry():
    cliente = ModeloAdequado()
    dados = json.loads(cliente.respostas)
    dados['recomendacoes'] = ['Examinar equipamento com a engenharia.']
    cliente.respostas = json.dumps(dados, ensure_ascii=False)
    r = SessaoCopiloto('LR-01').perguntar(
        DadosComMTTR(), PERGUNTA_COMPLETA, autorizar_api=True, cliente=cliente)
    assert r['status'] == 'bloqueada'
    assert len(cliente.calls) == 1
    assert 'MTTR' in ' '.join(r['resposta'])


def test_payload_acima_limite_nao_consome_creditos(monkeypatch):
    import igmi.copiloto as modulo
    monkeypatch.setattr(modulo, 'MAX_PAYLOAD_CHARS', 50)
    cliente = ModeloAdequado()
    r = SessaoCopiloto('LR-01').perguntar(
        DadosComMTTR(), PERGUNTA_COMPLETA, autorizar_api=True, cliente=cliente)
    assert r['status'] == 'limite_contexto'
    assert r['auditoria']['chamadas_api'] == 0
    assert cliente.calls == []

# IGMI 0.3.2.1 — regressões do relatório exportado em 17/11/2026.

def test_disponibilidade_solicitada_em_pergunta_composta_nao_omitida():
    pergunta = ('Quais equipamentos mais impactaram as horas de parada? '
                'Como estão o MTTR e a disponibilidade da LR-01?')
    p = planejar(pergunta)
    assert 'geral' in p['intencoes']
    assert p['ferramentas'] == ('consultar_kpis', 'consultar_equipamentos')
    r = SessaoCopiloto('LR-01').perguntar(DadosComMTTR(), pergunta)
    assert r['status'] == 'dados'
    assert 'disponibilidade 98,47%' in ' '.join(r['resposta'])
    assert r['cobertura']['geral'] == 'coberta'
    assert r['auditoria']['chamadas_api'] == 0


def test_alertas_do_mesmo_modo_nao_somam_ocorrencias_ou_repetem_modo():
    class DadosAlertas(DadosComMTTR):
        def consultar_reincidencias(self, linha, limite):
            base = super().consultar_reincidencias(linha, limite)
            outro = {**base[0], 'os_lista': 'dd00008f, dd000093, dd000091',
                     'disparado_em': '2026-06-11 08:00:00'}
            base[0]['disparado_em'] = '2026-07-06 11:36:00'
            return [base[0], outro, base[1]]

    p = ('Quais os equipamentos de maior impacto? Quais reincidencias da LR-01? '
         'Como esta a disponibilidade?')
    r = SessaoCopiloto('LR-01').perguntar(DadosAlertas(), p)
    assert r['status'] == 'dados'
    texto = ' '.join(r['resposta'])
    assert texto.count("modo 'Ferramenta não pega a peça'") == 1
    assert '2 alertas de reincidência' in texto
    assert 'não somar ocorrências' in texto
    assert 'dd00009c' in texto and 'dd00008f' in texto
    assert r['auditoria']['chamadas_api'] == 0


def test_tres_hipoteses_e_tres_acoes_aceitas_sem_retry_e_com_numeros_bloqueados():
    pergunta = ('Quero priorizar melhorias na confiabilidade da LR-01. '
                'Quais equipamentos mais impactaram as horas de parada? '
                'Quais reincidências merecem investigação prioritária? '
                'Como estão o MTTR e a disponibilidade da linha? '
                'Proponha três ações práticas, justificadas por evidências. '
                'Separe fatos, hipóteses e recomendações.')
    cliente = ModeloAdequado()
    dados = json.loads(cliente.respostas)
    dados.pop('analises_por_alvo')  # pergunta sem IDs de equipamento explícitos
    dados['hipoteses'] = [
        'O histórico sugere verificar desgaste da ferramenta, sem concluir causa.',
        'A reincidência da ventosa pode ter relação com condições de uso.',
        'O diagnóstico do reparo pode merecer revisão com os técnicos.',
    ]
    dados['recomendacoes'] = [
        'Verificar a ferramenta do robô, comparando registros e inspeção.',
        'Revisar o diagnóstico e o processo de reparo para avaliar o MTTR.',
        'Inspecionar ventosas e validar registros com a equipe de manutenção.',
    ]
    cliente.respostas = json.dumps(dados, ensure_ascii=False)
    r = SessaoCopiloto('LR-01', modelo='mock', limite_api=1).perguntar(
        DadosComMTTR(), pergunta, autorizar_api=True, cliente=cliente)
    assert r['status'] == 'validada', r['resposta']
    assert 'disponibilidade 98,47%' in ' '.join(r['resposta'])
    assert r['cobertura']['melhorias'] == 'coberta'
    assert r['auditoria']['chamadas_api'] == 1
    assert len(cliente.calls) == 1
    assert 'três hipóteses' in cliente.calls[0]['instructions']
    assert 'EXATAMENTE tres recomendacoes' in cliente.calls[0]['instructions']

    # Mais hipóteses do que o limite da versão, ou um valor inventado, segue bloqueado.
    for hipoteses in [dados['hipoteses'] + ['Nova suposição sem evidência.'],
                      ['A linha tem cento e quarenta falhas.']]:
        cliente2 = ModeloAdequado()
        dados2 = {**dados, 'hipoteses': hipoteses}
        cliente2.respostas = json.dumps(dados2, ensure_ascii=False)
        bloqueio = SessaoCopiloto('LR-01', modelo='mock').perguntar(
            DadosComMTTR(), pergunta, autorizar_api=True, cliente=cliente2)
        assert bloqueio['status'] == 'bloqueada'
        assert len(cliente2.calls) == 1
        assert '98,47%' in ' '.join(bloqueio['resposta'])


def test_pedido_tres_acoes_com_duas_e_bloqueado_com_fatos_preservados():
    pergunta = ('Quero uma análise da confiabilidade da LR-01, disponibilidade e MTTR; '
                'quais equipamentos mais impactam paradas e reincidências no robô e mesa? '
                'Proponha três ações práticas para avaliação técnica.')
    cliente = ModeloAdequado()
    dados = json.loads(cliente.respostas)
    dados['recomendacoes'] = [
        'Investigar diagnóstico e reparo para melhorar MTTR.',
        'Inspecionar ventosas com a equipe de manutenção.',
    ]
    cliente.respostas = json.dumps(dados, ensure_ascii=False)
    r = SessaoCopiloto('LR-01', modelo='mock').perguntar(
        DadosComMTTR(), pergunta, autorizar_api=True, cliente=cliente)
    assert r['status'] == 'bloqueada'
    assert len(cliente.calls) == 1
    assert 'três ações' in ' '.join(r['resposta'])
    assert '98,47%' in ' '.join(r['resposta'])
