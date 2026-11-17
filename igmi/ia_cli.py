"""CLI exclusiva da integração opcional e paga com IA — não altera igmi/cli.py."""
import argparse
import json
import os
import sys
from pathlib import Path

from igmi.consultas import abrir_demo
from igmi.exceptions import IGMIError
from igmi.ia_economica import conversar_economico, markdown_economico


def main(argv=None):
    parser = argparse.ArgumentParser(description='IGMI 0.2.1 — analista econômico com IA (usa API paga)')
    parser.add_argument('--linha', required=True, help='Linha cadastrada, ex.: LT3 ou LT56')
    parser.add_argument('--pergunta', required=True, help='Pergunta sobre o período fechado da demo')
    parser.add_argument('--inicio', help='AAAA-MM-DD; apenas período completo')
    parser.add_argument('--fim', help='AAAA-MM-DD; apenas período completo')
    parser.add_argument('--modelo', default=os.getenv('IGMI_OPENAI_MODEL', ''),
                        help='Modelo da API (ou configure IGMI_OPENAI_MODEL)')
    parser.add_argument('--limite-ferramentas', type=int, default=4,
                        help='Compatibilidade: modo econômico usa no máximo quatro consultas')
    parser.add_argument('--formato', choices=('markdown', 'json'), default='markdown')
    parser.add_argument('--saida', type=Path, help='Arquivo destino; por padrão imprime no terminal')
    parser.add_argument('--autorizar-api', action='store_true',
                        help='Obrigatório para consentir com uma chamada real e potencialmente cobrada')
    args = parser.parse_args(argv)
    if not args.autorizar_api:
        parser.error('Para consultar a API paga, informe --autorizar-api. '
                     'Modo offline: python run.py igmi --linha LT3')
    if not 1 <= args.limite_ferramentas <= 8:
        parser.error('--limite-ferramentas deve estar entre 1 e 8 (legado).')
    if args.limite_ferramentas != 4:
        print('IGMI: modo econômico seleciona até quatro consultas; opção legada ignorada.',
              file=sys.stderr)
    try:
        with abrir_demo() as consultas:
            resultado = conversar_economico(
                consultas, linha=args.linha, pergunta=args.pergunta, modelo=args.modelo,
                inicio=args.inicio, fim=args.fim)
        conteudo = (json.dumps(resultado, ensure_ascii=False, indent=2) + '\n'
                    if args.formato == 'json' else markdown_economico(resultado))
        if args.saida:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(conteudo, encoding='utf-8')
            print(f'IGMI 0.2.1: análise gravada em {args.saida}')
        else:
            print(conteudo)
        return 0
    except (IGMIError, ValueError, ImportError) as exc:
        print(f'IGMI IA: {exc}', file=sys.stderr)
        return 2
