"""Testes sem banco/LLM para o núcleo de segurança e o renderizador."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from igmi.analista import analisar_confiabilidade, markdown
from igmi.consultas import ConsultasDemo, _limite, _linhas, abrir_demo
from igmi.exceptions import EscopoInvalido, QualidadeBloqueada, WarehouseAusente


class Relacao:
    def __init__(self, columns, rows):
        self.description = [(c,) for c in columns]
        self._rows = rows

    def fetchall(self):
        return self._rows


class BancoFalso:
    def __init__(self):
        self.executados = []

    def execute(self, sql, parametros):
        self.executados.append((sql, parametros))
        if 'FROM meta.carga' in sql:
            return Relacao(['status', 'data_carga'], [('OK', '2026-10-01')])
        if 'FROM cat.parametros_demo' in sql:
            return Relacao(['chave', 'valor'], [
                ('periodo_inicio', '2026-04-01'), ('periodo_fim', '2026-09-30'),
                ('pareto_medida', 'parada_min')])
        if 'FROM gold.dim_linha' in sql:
            return Relacao(['linha_id'], [('LT3',), ('LT56',)])
        if 'FROM gold.kpi_linha' in sql:
            return Relacao(['escopo', 'os_total'], [('LT3', 10)])
        return Relacao(['teste'], [])


class ConsultasTest(unittest.TestCase):
    def _abrir(self, status='OK', n=27):
        checks = [{'id': f'QD{i:02}', 'ok': status == 'OK'} for i in range(1, n+1)]
        context = patch('pmb.demo_quality.run', return_value=checks)
        context.start()
        self.addCleanup(context.stop)
        banco = BancoFalso()
        return ConsultasDemo(banco), banco

    def test_consulta_kpi_com_parametro_vinculado(self):
        consultas, banco = self._abrir()
        self.assertEqual(consultas.consultar_kpis('LT3')['os_total'], 10)
        sql, params = banco.executados[-1]
        self.assertIn('WHERE escopo = ?', sql)
        self.assertEqual(params, ['LT3'])
        self.assertEqual(consultas.contexto['checks_ok'], 27)

    def test_bloqueio_com_qualquer_check_reprovado(self):
        with patch('pmb.demo_quality.run', return_value=[{'id': 'QD01', 'ok': False}]+[
                {'id': f'QD{i:02}', 'ok': True} for i in range(2, 28)]):
            with self.assertRaises(QualidadeBloqueada):
                ConsultasDemo(BancoFalso())

    def test_bloqueio_se_numero_checks_muda(self):
        with patch('pmb.demo_quality.run', return_value=[{'id': 'QD01', 'ok': True}] * 26):
            with self.assertRaises(QualidadeBloqueada):
                ConsultasDemo(BancoFalso())

    def test_injecao_de_linha_nao_executa_sql(self):
        consultas, banco = self._abrir()
        with self.assertRaises(EscopoInvalido):
            consultas.consultar_kpis("LT3' OR 1=1 --")
        self.assertFalse(any('OR 1=1' in sql for sql, _ in banco.executados))

    def test_limites(self):
        for x in (0, -1, 31, True, '3'):
            with self.assertRaises(ValueError):
                _limite(x)
        self.assertEqual(_limite(30), 30)

    def test_warehouse_ausente_bloqueia_sem_abrir_banco(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(WarehouseAusente):
                with abrir_demo(Path(d) / 'inexistente.duckdb'):
                    pass

    def test_linhas_serializa_corretamente(self):
        class Stub:
            def execute(self, sql, p):
                self.s = sql, p
                return Relacao(['n'], [(7,)])
        s = Stub()
        self.assertEqual(_linhas(s, 'SELECT ?', [7]), [{'n': 7}])
        self.assertEqual(s.s[1], [7])


class FakeAnalise:
    contexto = dict(periodo_inicio='2026-04-01', periodo_fim='2026-09-30',
                    data_carga='2026-10-01', pareto_medida='parada_min',
                    checks_ok=27, checks_total=27)

    def consultar_kpis(self, linha):
        return dict(os_total=1, falhas=1, falhas_com_parada=1, parada_h=2,
                    mttr_h=2, mtbf_h=100, disponibilidade=0.99,
                    os_abertas=1, os_envelhecidas=1, pm_compliance=0.9, aderencia=0.8)

    def consultar_equipamentos(self, linha):
        return [dict(equipment_id='LT3-ABC', criticidade='A', falhas=1, parada_h=2)]

    def consultar_pareto(self, linha):
        return [dict(modo_id='XX-1', modo_nome='Teste', valor=120, pct_acumulado=100)]

    def consultar_reincidencias(self, linha):
        return []

    def consultar_os(self, linha):
        return [dict(task_short_id='dd000001', equipment_id='LT3-ABC', modo_id='XX-1', parada_min=120)]

    def consultar_tendencia(self, linha):
        return [dict(mes='2026-04', falhas=1, parada_h=2, disponibilidade=0.99)]

    def consultar_backlog(self, linha):
        return dict(os_abertas=1, os_envelhecidas=1, horas_restantes=3)

    def consultar_qualidade(self):
        return [dict(indicador='teste', n=0, base=1)]


class AnalistaTest(unittest.TestCase):
    def test_relatorio_com_evidencias_e_limites(self):
        r = analisar_confiabilidade(FakeAnalise(), 'LT3')
        saida = markdown(r)
        self.assertIn('dd000001', saida)
        self.assertIn('2026-04-01 a 2026-09-30', saida)
        self.assertIn('27/27 checks OK', saida)
        self.assertIn('não comprovadas', saida)
        self.assertIn('sem IA generativa', saida)
        self.assertIn('LT3-ABC', saida)
        self.assertEqual(r['tipo'], 'analise_deterministica_sem_llm')


if __name__ == '__main__':
    unittest.main()
