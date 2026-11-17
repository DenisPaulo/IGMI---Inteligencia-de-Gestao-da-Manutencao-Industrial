# IGMI 0.3.0 — Copiloto de Confiabilidade (CLI)

**Tipo de entrega:** patch incremental sobre o IGMI 0.2.1 (sem repositório completo).  
**Plataforma de referência:** Windows + VS Code + Git Bash.  
**Dados:** exclusivamente sintéticos da demonstração; análise não equivale a laudo de engenharia.

## Objetivo

Conversar com os indicadores de confiabilidade com **zero chamadas de API para consultas objetivas** e **no máximo uma tentativa de chamada à API por turno interpretativo**, autorizada explicitamente. Usar o banco analítico somente leitura e manter o cálculo numérico em Python/SQL.

## Implementação

- `igmi/copiloto.py`: sessão efêmera, roteamento determinístico, seleção de consultas, cache por linha/carga, formatação em Python, IA qualitativa opcional com validação existente na 0.2.1, auditoria de tokens por turno.
- `igmi/chat_cli.py`: terminal interativo no Git Bash, troca de linha, ajuda, exportação voluntária, confirmação de chamadas pagas e limites locais.
- `run.py`: **novo** comando `igmi-chat`, sem alterar `igmi` e `igmi-ia`.
- `igmi/__init__.py`: versão 0.3.0.
- `tests_igmi/test_copiloto.py`: testes sem chamadas pagas.
- `CHANGELOG.md`: histórico atualizado.

A interface **não usa SQL criado pelo modelo**. Os únicos métodos disponíveis são `consultar_kpis`, `consultar_equipamentos`, `consultar_reincidencias`, `consultar_pareto`, `consultar_tendencia`, `consultar_os` e `consultar_backlog`. A camada `ConsultasDemo` revalida 27 checks QD em cada abertura de banco e mantém conexão `read_only=True`.

**Atenção:** um indicador mensal pode ser comparado por mês quando vem de `consultar_tendencia`. KPIs agregados permanecem restritos ao **período completo** da demonstração (abril a setembro de 2026). Perguntas fora desse intervalo são recusadas.

## 1. Aplicar patch no Git Bash

1. **Faça backup da pasta do projeto** antes de substituir arquivos. Não misture com outro projeto/versão.
2. Abra o Git Bash na pasta **IGMI** que contém `run.py` da versão 0.2.1 já validada.
3. Coloque o ZIP dentro dessa pasta ou use o caminho absoluto para ele.
4. Extraia preservando os caminhos relativos, sem criar uma pasta adicional:

```bash
# Dentro da pasta que contém run.py
unzip -o IGMI_0.3.0_PATCH_SOMENTE_ALTERACOES.zip
```

Se o Git Bash não disponibilizar `unzip`, use WinRAR/7-Zip para extrair **na pasta atual**, substituindo os arquivos relativos indicados no manifesto.

O patch contém **somente arquivos alterados/adicionados**. Não inclui credenciais, dados, `warehouse`, `export`, `.venv`, bibliotecas ou qualquer arquivo de planta.

### Reversão

Para desfazer, restaure o backup de `run.py`, `igmi/__init__.py` e `CHANGELOG.md`, e opcionalmente apague os arquivos novos `igmi/copiloto.py`, `igmi/chat_cli.py`, `tests_igmi/test_copiloto.py` e `docs/IGMI_0.3.0.md`. **Não apague dados ou o warehouse.**

## 2. Dependências e base

Use seu ambiente virtual existente:

```bash
source .venv/Scripts/activate
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
python -m pip install -r requirements-ai.txt  # caso necessário
```

Se `warehouse/demo.duckdb` ainda não existir, gere a demo primeiro:

```bash
python run.py simular demo demo-preview
```

## 3. Testes offline (não consomem créditos)

```bash
python -m pytest -q tests_igmi
python run.py test
```

A primeira execução verifica somente o módulo IGMI; a segunda executa a suíte completa (exige DuckDB instalado e base/testes do repositório). **Não realiza API paga.**

### Resultado obtido no ambiente de construção

- `tests_igmi`: **60 passed, 7 subtests passed** (sem rede, sem chave de API).
- Suíte completa: **não foi possível executar**, pois `duckdb` não estava instalado neste ambiente (`ModuleNotFoundError`). Execute no Windows e reporte eventuais falhas.
- Integração com API real: **não executada** nesta entrega; requer sua autorização explícita.

## 4. Conversar sem custo de API

```bash
python run.py igmi-chat --linha LT3
```

Exemplo:

```text
> Qual equipamento mais parou?
> Quais reincidencias aparecem na ferramenta do robo?
> Compare as falhas de junho e julho de 2026.
> Quais OS justificam essa conclusao?
> Como esta o backlog?
> /resumo
> /exportar export/igmi_chat_LT3.md
> /linha LT56
> /sair
```

**Somente consultas objetivas são respondidas offline**. O relatório exibe evidência `E1`, consulta, linha e período. A consulta de OS lista **as maiores paradas**, não todo o histórico; a de equipamentos e reincidências usa resultados limitados. A conversa não é armazenada automaticamente: `/exportar` é explícito.

## 5. Conversar usando a API, se desejar

A chave deve estar na variável de ambiente `OPENAI_API_KEY`, **nunca em arquivos versionados, prints ou mensagens**. A versão 0.3.0 pode ser executada offline sem chave.

```bash
export IGMI_OPENAI_MODEL="gpt-4.1-mini"
# OPENAI_API_KEY deve estar previamente configurada no Git Bash com segurança.
python run.py igmi-chat --linha LT3 --modelo "$IGMI_OPENAI_MODEL" --autorizar-api --max-chamadas 3
```

Exemplo:

```text
> O que podemos investigar primeiro?
Autorizar UMA chamada paga à API neste turno? [s/N] s
IGMI [validada; LT3; 1 API]: ...
```

- O parâmetro `--autorizar-api` **não dispara API sozinho**; há uma segunda confirmação por pergunta interpretativa.
- Responda `n` para cancelar sem gasto naquele turno.
- `--max-chamadas 3` limita **tentativas** por sessão (inclui tentativas com erro).
- O teto de saída é `max_output_tokens=450` e **não há retry pago automático**.
- Resultados da GOLD são filtrados por allowlist e amostra de até 3 linhas antes do envio.
- O texto da conversa anterior **não é enviado** ao modelo.
- Perguntas fora de escopo e consultas diretas não usam IA.
- Uma chamada pode gerar cobrança mesmo que a resposta seja rejeitada; limites financeiros do provedor devem continuar configurados.
- Se ocorrer `401`, `403`, `429` ou falha de rede, é exibido um erro sem revelar a chave. O sistema conserva os fatos determinísticos.

**Importante:** `validada` significa que a saída passou pelos validadores implementados, não que suas hipóteses constituam diagnóstico técnico. Não há garantia absoluta contra erros semânticos da IA.

## 6. Status, limites e auditoria

`/resumo` apresenta chamadas/tokens da sessão; `/exportar` inclui, quando solicitado, a linha, status de cada resposta, consulta e período das evidências. Cada resposta aceita no máximo **uma chamada paga** e o cache só é reaproveitado enquanto a assinatura da carga/arquivo permanecer válida. A carga é reaberta e passa por 27 Quality Checks por turno (o que privilegia confiança, mas pode adicionar latência).

A versão 0.2.1 consumiu **929 tokens** em uma análise específica, com três ferramentas; o modo 0.3.0 foi projetado para consumir **zero tokens nas perguntas objetivas** e menos contexto por pergunta interpretativa. O consumo real de chamadas pagas deverá ser medido no Windows; **não há promessa de valor fixo por pergunta**.

### Limitações intencionais

- Não é um sistema de controle industrial, não executa comandos em CLP/robôs nem grava OS.
- Não há suporte a períodos móveis, comparação entre linhas na mesma pergunta nem acesso a dados reais.
- O roteador usa regras simples. Perguntas desconhecidas retornam orientação e podem exigir reformulação.
- O contexto de seguimento retém no máximo a última referência inequívoca a equipamento; não é uma memória generativa.
- Os dados da consulta são limitados; a resposta não promete lista exaustiva.
- As recomendações da IA devem ser avaliadas por especialista. Medidas preditivas exigem dados de condição e estudo de viabilidade.

## 7. Checklist de aceite no Windows

1. `python run.py igmi-chat --linha LT3` abre e identifica período/qualidade.
2. A pergunta “Qual equipamento mais parou?” retorna resultados **offline** e referencia E1.
3. “Compare as falhas de junho e julho de 2026” utiliza `consultar_tendencia`.
4. `/linha LT56` troca o escopo e invalida referência anterior.
5. `/resumo` exibe **zero** chamadas para perguntas diretas.
6. `/exportar` gera Markdown em UTF-8 no destino indicado.
7. `python run.py test` não apresenta regressões.
8. Se houver autorização, teste uma pergunta interpretativa, confirme **uma** chamada, e registre tokens para comparar com a base de 929 da versão 0.2.1.
