"""IGMI 0.2.1: testes do modo econômico, todos sem internet ou API paga."""
import json
from unittest import TestCase
from unittest.mock import patch

from igmi.ia import RespostaInvalida
from igmi.ia_economica import (
    conversar_economico, criar_fatos, duracao_h, duracao_min, ferramentas,
    hora_decimal, markdown_economico, porcentagem, validar_interpretacao,
)
from igmi.exceptions import EscopoInvalido


class DadosFalsos:
    contexto = {'periodo_inicio': '2026-04-01', 'periodo_fim': '2026-09-30',
                'data_carga': '2026-10-01', 'checks_ok': 27, 'checks_total': 27}

    def validar_linha(self, linha):
        if linha != 'LT3':
            raise EscopoInvalido('Linha não cadastrada')

    def consultar_kpis(self, linha):
        return {'escopo': linha, 'os_total': 117, 'falhas': 66, 'falhas_com_parada': 54,
                'parada_h': 57.75, 'disponibilidade': 0.9847, 'mttr_h': 1.07,
                'mtbf_h': 56.2, 'custo_parada': 17325, 'informacao_privada': 'NAO_ENVIAR'}

    def consultar_equipamentos(self, linha, limite):
        return [{'equipment_id': 'LT3-RB01', 'nome': 'Robô de reagrupagem LT3',
                 'criticidade': 'A', 'falhas': 25, 'parada_min': 1568, 'mttr_h': 1.31,
                 'campo_extra': 'NAO_ENVIAR'}]

    def consultar_reincidencias(self, linha, limite):
        return [{'equipment_id': 'LT3-MS01-VEN', 'modo_nome': 'Ventosa danificada',
                 'ocorrencias': 3, 'janela_dias': 15, 'os_lista': 'dd000090, dd000095, dd000099'}]

    def consultar_pareto(self, linha, limite):
        return [{'modo_nome': 'Ferramenta não pega a peça', 'medida': 'parada_min', 'valor': 936}]

    def consultar_tendencia(self, linha):
        return [{'mes': '2026-07', 'falhas': 17, 'parada_h': 17.67}]

    def consultar_backlog(self, linha):
        return {'os_abertas': 8, 'os_envelhecidas': 5, 'horas_restantes': 13.52}

    def consultar_os(self, linha, limite):
        return [{'task_short_id': 'dd0000d6', 'equipment_id': 'LT3-RB01-EIX',
                 'modo_id': 'RB-VIB', 'parada_min': 171}]


class ClienteFalso:
    def __init__(self, texto=None, status='completed'):
        self.calls = []
        self.responses = self
        self.texto = texto or json.dumps({
            'resumo': 'A concentração das paradas recomenda investigar a ferramenta do robô.',
            'hipoteses': ['Desgaste na garra pode contribuir para reincidências.'],
            'recomendacoes': ['Inspecionar a garra com a equipe técnica.'],
            'limitacoes': ['A causa-raiz não foi comprovada.'],
        }, ensure_ascii=False)
        self.status = status

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {'status': self.status, 'output_text': self.texto,
                'usage': {'input_tokens': 620, 'output_tokens': 170}}


class TesteFormato(TestCase):
    def test_hora_decimal_nao_e_hora_e_minuto(self):
        self.assertEqual(duracao_h(57.75), '57 h 45 min')
        self.assertEqual(duracao_h(1.31), '1 h 19 min')
        self.assertEqual(duracao_min(1568), '26 h 08 min')
        self.assertEqual(duracao_h(26.13), '26 h 08 min')
        self.assertEqual(hora_decimal(1.31), '1,31 h')

    def test_porcentagem_usa_fracao_correta(self):
        self.assertEqual(porcentagem(0.9847), '98,47%')
        with self.assertRaises(RespostaInvalida):
            porcentagem(1.9847)
        with self.assertRaises(RespostaInvalida):
            duracao_min(-12)

    def test_fatos_exatos_nao_dependem_do_modelo(self):
        r = conversar_economico(DadosFalsos(), linha='LT3', pergunta='Analise LT3 abril a setembro 2026',
                                modelo='modelo-mock', cliente=ClienteFalso())
        fatos = ' '.join(f['descricao'] for f in r['analise']['fatos'])
        for trecho in ('57 h 45 min', '98,47%', '26 h 08 min', '1 h 19 min',
                       'Ventosa danificada', 'dd000090'):
            self.assertIn(trecho, fatos)
        self.assertNotIn('57 h 75 min', fatos)
        self.assertNotIn('ventilação danificada', fatos)


class TesteEconomiaESeguranca(TestCase):
    def setUp(self):
        self.dados = DadosFalsos()
        self.cliente = ClienteFalso()
        self.kw = {'consultas': self.dados, 'linha': 'LT3',
                   'pergunta': 'Analise a confiabilidade da LT3 de abril a setembro de 2026.',
                   'modelo': 'modelo-mock'}

    def test_uma_chamada_api_com_amostra_enxuta(self):
        r = conversar_economico(**self.kw, cliente=self.cliente)
        self.assertEqual(r['versao'], '0.2.1')
        self.assertEqual(r['status_ia'], 'validada')
        self.assertEqual(len(self.cliente.calls), 1)
        self.assertEqual(r['auditoria']['chamadas_api'], 1)
        self.assertEqual(r['auditoria']['tokens_entrada'], 620)
        self.assertEqual(self.cliente.calls[0]['max_output_tokens'], 650)
        self.assertEqual(self.cliente.calls[0]['store'], False)
        self.assertNotIn('tools', self.cliente.calls[0])
        enviado = self.cliente.calls[0]['input'][0]['content']
        self.assertNotIn('NAO_ENVIAR', enviado)
        self.assertNotIn('custo_parada', enviado)
        self.assertNotIn('OPENAI_API_KEY', enviado)
        self.assertIn('E1', markdown_economico(r))
        self.assertNotIn('```json', markdown_economico(r))

    def test_selecao_controlada_de_consultas(self):
        self.assertEqual(ferramentas('Analise LT3'),
                         ['consultar_kpis', 'consultar_equipamentos', 'consultar_reincidencias'])
        self.assertIn('consultar_pareto', ferramentas('Pareto LT3'))
        self.assertIn('consultar_tendencia', ferramentas('Tendência LT3'))
        self.assertIn('consultar_backlog', ferramentas('Backlog LT3'))
        self.assertIn('consultar_os', ferramentas('Relacione as OS LT3'))
        self.assertLessEqual(len(ferramentas('Analise LT3')), 4)

    def test_numero_inventado_e_por_extenso_sao_bloqueados_sem_retry(self):
        for trecho in ('A linha teve 149 falhas.', 'A linha teve cento e quarenta paradas.',
                       'A linha teve cinquenta por cento de reatividade.'):
            with self.subTest(trecho=trecho):
                payload = json.loads(self.cliente.texto)
                payload['resumo'] = trecho
                cliente = ClienteFalso(json.dumps(payload, ensure_ascii=False))
                r = conversar_economico(**self.kw, cliente=cliente)
                self.assertEqual(r['status_ia'], 'bloqueada')
                self.assertEqual(r['analise']['hipoteses'], [])
                self.assertEqual(len(cliente.calls), 1)
                self.assertIn('57 h 45 min', markdown_economico(r))
                self.assertIn('BLOQUEADA', markdown_economico(r))
                self.assertNotIn(trecho, markdown_economico(r))

    def test_termo_incorreto_e_bloqueado(self):
        p = json.loads(self.cliente.texto)
        p['hipoteses'] = ['Ventilação danificada pode explicar falhas.']
        r = conversar_economico(**self.kw, cliente=ClienteFalso(json.dumps(p, ensure_ascii=False)))
        self.assertEqual(r['status_ia'], 'bloqueada')

    def test_pergunta_invalida_bloqueada_antes_da_api(self):
        with self.assertRaises(EscopoInvalido):
            conversar_economico(**{**self.kw, 'pergunta': 'Analise hoje'}, cliente=self.cliente)
        with self.assertRaises(EscopoInvalido):
            conversar_economico(**{**self.kw, 'linha': 'LT56'}, cliente=self.cliente)
        self.assertEqual(self.cliente.calls, [])

    def test_sem_kpis_sem_api(self):
        class DadosSemKPI(DadosFalsos):
            def consultar_kpis(self, linha):
                return None
        with self.assertRaisesRegex(RespostaInvalida, 'KPIs obrigatórios'):
            conversar_economico(**{**self.kw, 'consultas': DadosSemKPI()}, cliente=self.cliente)
        self.assertEqual(len(self.cliente.calls), 0)

    def test_resposta_incompleta_nao_aprovada(self):
        r = conversar_economico(**self.kw, cliente=ClienteFalso(status='incomplete'))
        self.assertEqual(r['status_ia'], 'bloqueada')
        self.assertEqual(r['auditoria']['chamadas_api'], 1)

    def test_sem_sql_dinamico_e_sem_ferramentas_do_modelo(self):
        r = conversar_economico(**self.kw, cliente=self.cliente)
        self.assertEqual(r['auditoria']['ferramentas'],
                         ['consultar_kpis', 'consultar_equipamentos', 'consultar_reincidencias'])
        self.assertFalse('sql' in self.cliente.calls[0])
        self.assertIn('Dados sintéticos', markdown_economico(r))

if __name__ == '__main__':
    import unittest
    unittest.main()
