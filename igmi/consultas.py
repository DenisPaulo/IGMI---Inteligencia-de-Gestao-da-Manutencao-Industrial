"""Ferramentas fixas e parametrizadas para a GOLD demo (acesso somente leitura).

Não há SQL livre, execução arbitrária de comandos, chamadas externas nem escrita.
Todas as 27 regras QD existentes são checadas antes de liberar uma consulta.
"""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from igmi.exceptions import EscopoInvalido, QualidadeBloqueada, WarehouseAusente

LIMITE_MAXIMO = 30


def _serializar(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _linhas(con, sql, parametros=()):
    """SQL é definido exclusivamente por código; parametros são sempre vinculados."""
    rel = con.execute(sql, list(parametros))
    nomes = [col[0] for col in rel.description]
    return [dict(zip(nomes, map(_serializar, row))) for row in rel.fetchall()]


def _limite(n):
    if type(n) is not int or not 1 <= n <= LIMITE_MAXIMO:
        raise ValueError(f"limite deve ser inteiro entre 1 e {LIMITE_MAXIMO}")
    return n


class ConsultasDemo:
    """Instância validada; não expor con nem consultas SQL livres ao LLM."""

    def __init__(self, con):
        from pmb import demo_quality
        self._con = con
        checks = demo_quality.run(con, demo_quality.CHECKS)
        reprovados = [r['id'] for r in checks if not r['ok']]
        if len(checks) != 27 or len({r["id"] for r in checks}) != 27 or reprovados:
            raise QualidadeBloqueada(
                f"Análise interrompida: {len(checks)}/27 checks disponíveis; "
                f"reprovados={','.join(reprovados) or 'contagem inválida'}"
            )
        carga = _linhas(con, "SELECT status, CAST(data_carga AS VARCHAR) data_carga FROM meta.carga")
        if len(carga) != 1 or carga[0]['status'] != 'OK':
            raise QualidadeBloqueada('Carga não está em estado OK')
        params = _linhas(con, "SELECT chave, valor FROM cat.parametros_demo WHERE "
                             "chave IN ('periodo_inicio','periodo_fim','pareto_medida')")
        p = {r['chave']: r['valor'] for r in params}
        if not {'periodo_inicio', 'periodo_fim', 'pareto_medida'} <= p.keys():
            raise QualidadeBloqueada('Período ou medida do Pareto não identificados')
        self.contexto = {
            'origem': 'warehouse demo sintético', 'data_carga': carga[0]['data_carga'],
            'periodo_inicio': p['periodo_inicio'], 'periodo_fim': p['periodo_fim'],
            'pareto_medida': p['pareto_medida'], 'checks_ok': 27, 'checks_total': 27,
        }

    def linhas_disponiveis(self):
        return [r['linha_id'] for r in _linhas(self._con, 'SELECT linha_id FROM gold.dim_linha ORDER BY linha_id')]

    def validar_linha(self, linha):
        disponiveis = self.linhas_disponiveis()
        if not isinstance(linha, str) or linha not in disponiveis:
            raise EscopoInvalido(f"Linha {linha!r} não encontrada. Válidas: {', '.join(disponiveis)}")
        return linha

    def consultar_kpis(self, linha):
        self.validar_linha(linha)
        rows = _linhas(self._con, """SELECT escopo, os_total, falhas, falhas_com_parada,
            parada_h, tempo_programado_h, disponibilidade, mttr_h, mtbf_h,
            pct_planejada, pct_reativa, custo_parada, os_abertas, os_envelhecidas,
            pm_compliance, aderencia FROM gold.kpi_linha WHERE escopo = ?""", [linha])
        return rows[0] if rows else None

    def consultar_equipamentos(self, linha, limite=5):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT equipment_id, nome, linha_id, classe_id,
            criticidade, falhas, falhas_com_parada, parada_min, parada_h,
            mttr_h, mtbf_h, disponibilidade, custo_parada FROM gold.kpi_equipamento
            WHERE linha_id = ? ORDER BY parada_h DESC, falhas DESC, equipment_id LIMIT ?""",
            [linha, _limite(limite)])

    def consultar_pareto(self, linha, limite=12):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT ordem, modo_id, modo_nome, medida, valor,
            os_n, pct, pct_acumulado FROM gold.pareto_modo WHERE escopo = ?
            ORDER BY ordem LIMIT ?""", [linha, _limite(limite)])

    def consultar_reincidencias(self, linha, limite=10):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT equipment_id, equipamento_nome,
            equipamento_n2_nome, modo_id, modo_nome, criticidade, prioridade,
            ocorrencias, janela_dias, CAST(disparado_em AS VARCHAR) disparado_em,
            os_gatilho, os_lista FROM gold.alertas_reincidencia WHERE linha_id = ?
            ORDER BY disparado_em DESC, equipment_id LIMIT ?""", [linha, _limite(limite)])

    def consultar_os(self, linha, limite=10):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT task_short_id, equipment_id, equipamento_n2_nome,
            tipo_id, modo_id, status, CAST(aberta_em AS VARCHAR) aberta_em,
            parada_min FROM gold.falhas WHERE linha_id = ?
            ORDER BY parada_min DESC, aberta_em DESC, task_id LIMIT ?""", [linha, _limite(limite)])

    def consultar_tendencia(self, linha):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT mes, linha_id, falhas, parada_h,
            disponibilidade, pct_reativa FROM gold.kpi_mensal WHERE linha_id = ? ORDER BY mes""", [linha])

    def consultar_backlog(self, linha):
        self.validar_linha(linha)
        return _linhas(self._con, """SELECT count(*) os_abertas,
            count(*) FILTER (WHERE envelhecida) os_envelhecidas,
            round(coalesce(sum(horas_restantes), 0), 2) horas_restantes
            FROM gold.backlog_os WHERE linha_id = ?""", [linha])[0]

    def consultar_qualidade(self):
        return _linhas(self._con, 'SELECT indicador, n, base FROM gold.qualidade_dado ORDER BY indicador')


@contextmanager
def abrir_demo(warehouse=None):
    """Não cria warehouse silenciosamente; abre apenas em modo read_only."""
    from pmb import config
    destino = Path(warehouse or (config.WAREHOUSE.parent / "demo.duckdb"))
    if not destino.is_file():
        raise WarehouseAusente(f"Warehouse ausente: {destino}. Execute 'python run.py simular demo' primeiro.")
    import duckdb
    con = duckdb.connect(str(destino), read_only=True)
    try:
        yield ConsultasDemo(con)
    finally:
        con.close()
