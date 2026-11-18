"""IGMI 0.3.1 — CLI Git Bash: composição explícita e consentimento por turno."""
import argparse
import os
from pathlib import Path
import sys

from igmi.consultas import abrir_demo
from igmi.planejador import planejar
from igmi.copiloto import (
    MAX_PERGUNTA, SessaoCopiloto, formatar_turno, identificar_alvos,
    intencao, limpar_texto, validar_escopo,
)
from igmi.exceptions import IGMIError

MAX_LINHAS = 12
AJUDA = """Comandos: /ajuda, /pergunta, /fim, /cancelar, /linha LR-01, /periodo,
  /resumo, /exportar [arquivo.md], /sair
Pergunta longa: digite /pergunta, escreva até 12 linhas e finalize com /fim.
  /cancelar descarta a composição. Fora desse modo, cada Enter envia uma pergunta.
Exemplos offline (zero tokens):
  Qual equipamento mais parou?
  Quais reincidencias aparecem na ferramenta do robo?
  Compare as falhas de junho e julho.
  Como esta o backlog?
Exemplo interpretativo: O que podemos investigar primeiro?
Para IA: --autorizar-api apenas HABILITA o pedido de consentimento.
  Cada pergunta paga exige digitar AUTORIZAR exatamente após a composição.
  CANCELAR ou qualquer outro texto não autoriza cobrança.
  Resumos da API não são usados para cálculos nem diagnósticos de causa raiz.
Para salvar: /exportar export/igmi_chat_LR-01.md (nunca é automático).
KPIs cobrem o período completo; comparações mensais usam a tabela mensal.
"""


def compor_pergunta(entrada, saida):
    """Coleta todas as linhas antes de permitir que a CLI ofereça uso pago."""
    saida(f'Modo de pergunta longa (máximo {MAX_LINHAS} linhas e {MAX_PERGUNTA} caracteres). '
          'Finalize com /fim ou descarte com /cancelar.')
    partes = []
    while True:
        try:
            linha = entrada('... ')
        except (EOFError, KeyboardInterrupt, StopIteration):
            saida('Composição cancelada. Nenhuma chamada à API.')
            return None
        if linha.strip() == '/cancelar':
            saida('Pergunta descartada. Nenhuma chamada à API.')
            return None
        if linha.strip() == '/fim':
            texto = limpar_texto('\n'.join(partes))
            if not texto:
                saida('Pergunta vazia; nada executado.')
                return None
            if len(texto) > MAX_PERGUNTA:
                saida(f'Pergunta tem {len(texto)} caracteres; máximo {MAX_PERGUNTA}. '
                      'Divida a pergunta e tente novamente.')
                return None
            return texto
        partes.append(linha)
        if len(partes) > MAX_LINHAS or len('\n'.join(partes)) > MAX_PERGUNTA:
            saida(f'Limite excedido ({MAX_LINHAS} linhas ou {MAX_PERGUNTA} caracteres). '
                  'Descartando o restante da composição até /fim ou /cancelar; nada será executado.')
            # Consome o restante da colagem: uma linha residual não pode virar
            # confirmação ou próxima pergunta quando o limite foi excedido.
            while True:
                try:
                    resto = entrada('... descartar> ')
                except (EOFError, KeyboardInterrupt, StopIteration):
                    return None
                if resto.strip() in ('/fim', '/cancelar'):
                    return None


def main(argv=None, *, entrada=input, saida=print, abrir=abrir_demo, cliente=None):
    parser = argparse.ArgumentParser(description='IGMI 0.3.1 — Copiloto robusto no Git Bash')
    parser.add_argument('--linha', default='LR-01')
    parser.add_argument('--modelo', default=os.getenv('IGMI_OPENAI_MODEL', ''))
    parser.add_argument('--autorizar-api', action='store_true',
                        help='Permite OFERECER uma chamada paga; requer AUTORIZAR por turno')
    parser.add_argument('--max-chamadas', type=int, default=3,
                        help='Teto local de tentativas na sessão (0 a 10)')
    args = parser.parse_args(argv)
    if not 0 <= args.max_chamadas <= 10:
        parser.error('--max-chamadas deve ficar entre 0 e 10')
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
        saida('Digite /ajuda para comandos, /pergunta para texto longo ou /sair.')
        while True:
            try:
                texto = limpar_texto(entrada('> '))
            except (EOFError, KeyboardInterrupt, StopIteration):
                saida('\nIGMI encerrado. Nenhum histórico foi salvo automaticamente.')
                return 0
            if texto == '/pergunta':
                texto = compor_pergunta(entrada, saida)
                if texto is None:
                    continue
            if not texto:
                continue
            if texto == '/sair':
                saida('IGMI encerrado.')
                return 0
            if texto == '/ajuda':
                saida(AJUDA)
                continue
            if texto in ('/fim', '/cancelar'):
                saida('Use /pergunta para iniciar uma pergunta longa.')
                continue
            if texto in ('AUTORIZAR', 'sim', 's', 'SIM', 'S'):
                saida('Confirmações fora do pedido explícito de autorização não executam API.')
                continue
            if texto == '/linha' or texto.startswith('/linha '):
                partes = texto.split()
                if len(partes) != 2:
                    saida('Uso: /linha LR-01')
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
                        saida(f"Carga {c['data_carga']}; período {c['periodo_inicio']} a {c['periodo_fim']}; "
                              f"qualidade {c['checks_ok']}/{c['checks_total']} (escopo global dos checks).")
                except (IGMIError, ValueError, ImportError) as exc:
                    saida(f'IGMI: {exc}')
                continue
            if texto == '/resumo':
                saida(f'Turnos: {len(sessao.historico)}; API: {sessao.chamadas_api}/{sessao.limite_api}; '
                      f'tokens reportados: {sessao.tokens_entrada}/{sessao.tokens_saida}.')
                continue
            if texto == '/exportar' or texto.startswith('/exportar '):
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
                    saida('Falha ao exportar. Verifique o destino.')
                continue
            if texto.startswith('/'):
                saida('Comando desconhecido. Digite /ajuda.')
                continue
            if limpar_texto(texto).lower() in ('relatório md', 'relatorio md', 'salvar relatório',
                                               'salvar relatorio', 'exportar conversa'):
                saida('Para gerar o relatório Markdown, digite /exportar [arquivo.md]. '
                      'Nenhum arquivo foi criado automaticamente.')
                continue
            try:
                with abrir() as con:
                    meses = validar_escopo(con, sessao.linha, texto)
                    alvos = identificar_alvos(texto, sessao.linha)
                    ferramenta, interpretativa = intencao(texto, meses, sessao.ultimo_equipamento)
                    plano = planejar(texto, meses, alvos)
                    if plano['multiplas']:
                        ferramenta = ', '.join(plano['ferramentas']) or 'nenhuma consulta adicional'
                        interpretativa = plano['interpretativa']
                    permitido = False
                    if interpretativa and args.autorizar_api and sessao.chamadas_api < sessao.limite_api:
                        if not args.modelo:
                            saida('Defina IGMI_OPENAI_MODEL ou informe --modelo.')
                        elif cliente is None and not os.getenv('OPENAI_API_KEY'):
                            saida('OPENAI_API_KEY ausente. Configure a chave no Git Bash.')
                        else:
                            c = con.contexto
                            saida(f"IGMI: linha {sessao.linha}; período {c['periodo_inicio']} a "
                                  f"{c['periodo_fim']}; consulta {ferramenta}; "
                                  f"alvos {', '.join(alvos) if alvos else 'linha inteira'}; "
                                  'no máximo UMA chamada paga neste turno (consome créditos).')
                            try:
                                resposta = entrada('Digite AUTORIZAR ou CANCELAR: ')
                            except (EOFError, KeyboardInterrupt, StopIteration):
                                saida('Autorização interrompida; nenhuma chamada à API.')
                                continue
                            if resposta.strip() != 'AUTORIZAR':
                                saida('Chamada cancelada; nenhum crédito consumido neste turno.')
                                continue
                            permitido = True
                    resultado = sessao.perguntar(con, texto, autorizar_api=permitido, cliente=cliente)
                saida(formatar_turno(resultado))
            except (IGMIError, ValueError, ImportError) as exc:
                saida(f'IGMI: {exc}')
    except (IGMIError, ValueError, ImportError) as exc:
        saida(f'IGMI: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
