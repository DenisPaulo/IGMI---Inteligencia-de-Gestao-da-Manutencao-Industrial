# IGMI 0.2.1 — Analista enxuto e precisão numérica

**Atualização incremental:** instalar por cima do IGMI 0.2.0 já funcional; não substituir a pasta inteira. A atualização contém somente seis arquivos novos/alterados. **Não há alterações em `run.py`, SQL, estrutura do DuckDB ou dados sintéticos.**

## Principais mudanças

- **Uma única chamada à API por análise:** Python escolhe até quatro consultas controladas (KPIs, equipamentos, reincidências e uma consulta contextual, se necessária); não há rodadas de `function_call` nem reenvio cumulativo de resultados.
- **Entrada reduzida:** o modelo recebe somente colunas úteis e até três registros por ferramenta; o relatório JSON mantém registros originais para auditoria. O tamanho exato da economia em tokens depende da pergunta e dos retornos reais.
- **Números calculados e formatados em Python:** a IA não produz fatos quantitativos. Por exemplo: `57,75 h = 57 h 45 min`, `1,31 h ≈ 1 h 19 min`, `1.568 min = 26 h 08 min`, disponibilidade `0,9847 = 98,47%`.
- **Termos do cadastro preservados nos fatos:** o modo `Ventosa danificada` é exibido literalmente. Uma interpretação que substitua ventosa por ventilação é bloqueada.
- **Validação conservadora:** textos da IA com números (inclusive diversas formas por extenso), terminologia problemática ou JSON inválido não são publicados como interpretação válida. Nesse caso, um relatório **com status `BLOQUEADA`** exibe somente os fatos determinísticos e a limitação, sem fazer outra chamada paga automaticamente.
- **Saída Markdown compacta:** resumo, fatos com IDs de evidência e tabela das fontes; para inspecionar os resultados completos das ferramentas use `--formato json`.

### Limites e honestidade da validação

O modo econômico reduz a superfície de erro, mas **não prova verdade semântica de toda frase em linguagem natural**. Hipóteses e recomendações ainda exigem revisão técnica. A verificação de números por extenso cobre formas comuns, não todas as expressões possíveis. Somente dados sintéticos são usados nesta etapa.

O comando anterior `python run.py igmi` continua determinístico e offline. O código legado `igmi/ia.py` não foi modificado, preservando os testes da versão anterior. A linha de comando `igmi-ia` agora seleciona o modo econômico automaticamente. A opção antiga `--limite-ferramentas` é aceita por compatibilidade, mas a seleção é fixa em no máximo quatro consultas.

## Instalação no Windows (Git Bash)

1. Feche qualquer execução do IGMI e faça **backup** da pasta atual.
2. Extraia o ZIP de atualização **dentro da pasta raiz do projeto** (onde está `run.py`). Preserve as subpastas e permita sobrescrever os arquivos correspondentes.
3. Mantenha o ambiente virtual existente. Nenhuma dependência nova é exigida.
4. No terminal Git Bash, ative o ambiente e rode:

```bash
source .venv/Scripts/activate
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
python -m pytest -q tests_igmi
python run.py test
```

> Antes de usar API paga, verifique se todos os testes estão OK. O modelo e a chave continuam configurados como na 0.2.0. A chave não deve constar em arquivo do projeto, Git ou screenshots.

## Primeira análise (pode consumir créditos)

```bash
export IGMI_OPENAI_MODEL="gpt-4.1-mini"
# Se necessário, configure OPENAI_API_KEY novamente por entrada silenciosa.
mkdir -p export
python run.py igmi-ia \
  --linha LR-01 \
  --pergunta "Analise a confiabilidade da LR-01 de abril a setembro de 2026. Identifique equipamentos prioritarios e reincidencias." \
  --modelo "$IGMI_OPENAI_MODEL" \
  --autorizar-api \
  --saida export/igmi_ia_LR-01_021.md
code export/igmi_ia_LR-01_021.md
```

O relatório informa `IA: VALIDADA` ou `IA: BLOQUEADA`, as consultas selecionadas, **uma chamada à API** e os tokens usados, conforme dados retornados pelo provedor. Para ver todas as evidências em JSON:

```bash
python run.py igmi-ia \
  --linha LR-01 \
  --pergunta "Analise a confiabilidade da LR-01 de abril a setembro de 2026." \
  --modelo "$IGMI_OPENAI_MODEL" --autorizar-api \
  --formato json --saida export/igmi_ia_LR-01_021.json
```

**ATENÇÃO:** o segundo comando é **outra chamada paga**. Para economizar, rode uma vez em `--formato json` e, se precisar, consulte-o em vez de chamar a API novamente.

## Validação técnica

- Os testes `tests_igmi` usam clientes simulados; **não fazem chamadas à API**.
- O projeto ainda precisa passar por `python run.py test` no Windows do usuário com DuckDB instalado.
- Sem SQL arbitrário, sem escrita no DuckDB, sem integração com equipamentos industriais e sem dados reais de planta.
- Respeitar créditos e os limites da organização/projeto na plataforma do provedor; `max_output_tokens` limita a saída por requisição, não determina um gasto monetário garantido.

## Arquivos da atualização

- `igmi/ia_economica.py` — NOVO: consultas pré-selecionadas, formatação determinística, validação, uma chamada de API e Markdown compacto;
- `igmi/ia_cli.py` — atualizado: CLI usa o modo econômico;
- `igmi/__init__.py` — versão 0.2.1;
- `tests_igmi/test_ia_economica.py` — NOVO: regressões, segurança, custo e formatação;
- `docs/IGMI_0.2.1.md` — NOVO: este guia;
- `CHANGELOG.md` — atualizado: histórico da versão.
