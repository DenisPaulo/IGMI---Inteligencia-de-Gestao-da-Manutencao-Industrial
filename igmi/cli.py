"""CLI do IGMI: sem IA externa, gera relatório em .md ou .json."""
import argparse
import json
import sys
from pathlib import Path
from igmi.analista import analisar_confiabilidade, markdown
from igmi.consultas import abrir_demo
from igmi.exceptions import IGMIError


def main(argv=None):
    parser = argparse.ArgumentParser(description='IGMI — Analista de Confiabilidade (demo sintética)')
    parser.add_argument('--linha', required=True, help='Ex.: LR-01 ou LR-02')
    parser.add_argument('--formato', choices=('markdown', 'json'), default='markdown')
    parser.add_argument('--saida', type=Path, help='Caminho do arquivo; omitir para imprimir no terminal')
    args = parser.parse_args(argv)
    try:
        with abrir_demo() as consultas:
            resultado = analisar_confiabilidade(consultas, args.linha)
        conteudo = markdown(resultado) if args.formato == 'markdown' else json.dumps(
            resultado, ensure_ascii=False, indent=2, default=str) + '\n'
        if args.saida:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(conteudo, encoding='utf-8')
            print(f'IGMI: relatório gravado em {args.saida}')
        else:
            print(conteudo)
        return 0
    except (IGMIError, ValueError, ImportError) as exc:
        print(f'IGMI: {exc}', file=sys.stderr)
        return 2
