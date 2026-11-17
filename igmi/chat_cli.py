"""Chat local para Windows Git Bash: consultas offline e IA opcional com consentimento."""
import argparse
import os
from pathlib import Path
import sys

from igmi.consultas import abrir_demo
from igmi.copiloto import SessaoCopiloto, formatar_turno, intencao, validar_escopo
from igmi.exceptions import IGMIError

AJUDA = """Comandos: /ajuda, /linha LT3, /periodo, /resumo, /exportar [arquivo.md], /sair
Exemplos offline:
  Qual equipamento mais parou?
  Quais reincidencias aparecem na ferramenta do robo?
  Compare as falhas de junho e julho.
  Quais OS justificam essa conclusao?
  Como esta o backlog?
Exemplo opcional com IA: O que podemos investigar primeiro?
Para IA: iniciar com --autorizar-api; cada chamada solicita confirmacao.
KPIs cobrem o periodo completo; comparacoes mensais usam a tabela mensal.
"""


def main(argv=None, *, entrada=input, saida=print, abrir=abrir_demo, cliente=None):
    parser = argparse.ArgumentParser(description='IGMI 0.3.0 — copiloto econômico no Git Bash')
    parser.add_argument('--linha', default='LT3')
    parser.add_argument('--modelo', default=os.getenv('IGMI_OPENAI_MODEL', ''))
    parser.add_argument('--autorizar-api', action='store_true',
                        help='Permite oferecer uma chamada paga por turno, com confirmação adicional')
    parser.add_argument('--max-chamadas', type=int, default=3, help='Teto local de tentativas na sessão (0 a 10)')
    args = parser.parse_args(argv)
    if not 0 <= args.max_chamadas <= 10:
        parser.error('--max-chamadas deve ficar entre 0 e 10')
    # Compatibilidade com terminais Windows cp1252, sem alterar a codificação do warehouse.
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (ValueError, OSError):
            pass
    sessao = SessaoCopiloto(args.linha, modelo=args.modelo, limite_api=args.max_chamadas)
    try:
        with abrir() as con:
            con.validar_linha(sessao.linha)
            c = con.contexto
            saida(f"IGMI | {sessao.linha} | {c['periodo_inicio']} a {c['periodo_fim']} | "
                  f"Qualidade {c['checks_ok']}/{c['checks_total']} | IA opcional")
        saida('Digite /ajuda para comandos ou /sair para encerrar.')
        while True:
            try:
                texto = entrada('> ').strip()
            except (EOFError, KeyboardInterrupt):
                saida('\nIGMI encerrado. Nenhum histórico foi salvo automaticamente.')
                return 0
            if not texto:
                continue
            if texto == '/sair':
                saida('IGMI encerrado.')
                return 0
            if texto == '/ajuda':
                saida(AJUDA)
                continue
            if texto.startswith('/linha'):
                partes = texto.split()
                if len(partes) != 2:
                    saida('Uso: /linha LT3')
                    continue
                try:
                    with abrir() as con:
                        saida('Linha atual: ' + sessao.trocar_linha(partes[1].upper(), con))
                except (IGMIError, ValueError, ImportError) as exc:
                    saida(f'IGMI: {exc}')
                continue
            if texto == '/periodo':
                try:
                    with abrir() as con:
                        c = con.contexto
                        saida(f"Carga {c['data_carga']}; periodo {c['periodo_inicio']} a {c['periodo_fim']}; "
                              f"qualidade {c['checks_ok']}/{c['checks_total']} (escopo global dos checks).")
                except (IGMIError, ValueError, ImportError) as exc:
                    saida(f'IGMI: {exc}')
                continue
            if texto == '/resumo':
                saida(f"Turnos: {len(sessao.historico)}; API: {sessao.chamadas_api}/{sessao.limite_api}; "
                      f"tokens reportados: {sessao.tokens_entrada}/{sessao.tokens_saida}.")
                continue
            if texto.startswith('/exportar'):
                partes = texto.split(maxsplit=1)
                destino = Path(partes[1]) if len(partes) == 2 else Path('export') / f'igmi_chat_{sessao.linha}.md'
                if destino.suffix.lower() != '.md':
                    saida('Use extensão .md para exportar.')
                    continue
                try:
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(sessao.exportar_markdown(), encoding='utf-8')
                    saida(f'Arquivo gerado: {destino}')
                except OSError:
                    saida('Falha de escrita ao exportar. Verifique o destino.')
                continue
            if texto.startswith('/'):
                saida('Comando desconhecido. Digite /ajuda.')
                continue
            try:
                with abrir() as con:
                    meses = validar_escopo(con, sessao.linha, texto)
                    _, interpretativa = intencao(texto, meses, sessao.ultimo_equipamento)
                    permitido = False
                    if interpretativa and args.autorizar_api and sessao.chamadas_api < sessao.limite_api:
                        if not args.modelo:
                            saida('Defina IGMI_OPENAI_MODEL ou informe --modelo para usar IA.')
                        else:
                            resposta = entrada('Autorizar UMA chamada paga à API neste turno? [s/N] ')
                            permitido = resposta.strip().lower() in ('s', 'sim')
                            if not permitido:
                                saida('Chamada não autorizada; nenhum crédito consumido por este turno.')
                                continue
                    resultado = sessao.perguntar(con, texto, autorizar_api=permitido, cliente=cliente)
                saida(formatar_turno(resultado))
            except (IGMIError, ValueError, ImportError) as exc:
                saida(f'IGMI: {exc}')
    except (IGMIError, ValueError, ImportError) as exc:
        saida(f'IGMI: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
