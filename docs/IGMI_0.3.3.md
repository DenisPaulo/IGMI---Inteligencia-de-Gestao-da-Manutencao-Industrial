# IGMI 0.3.3 — Linhas fictícias para demonstração pública

## Objetivo

Padronizar a identidade das duas linhas da **planta inteiramente sintética** sem alterar a lógica de confiabilidade, os indicadores ou a segurança do projeto.

| Identificador técnico | Nome de apresentação |
|---|---|
| `LR-01` | **Linha Robotizada_1** |
| `LR-02` | **Linha Robotizada_2** |

A alteração afeta os prefixos de equipamentos (`LR-01-RB01` etc.), subconjuntos, planos preventivos (`PM-LR-01-...`), centros de custo sintéticos, CSVs da demo, simulador, CLI, documentação, templates de dashboard, testes e a CI. IDs históricos de ordens sintéticas permanecem estáveis.

**Importante:** esta é uma *pseudonimização/renomeação de um cenário fictício*, não uma garantia de anonimização. Alterar arquivos atuais não apaga versões anteriores no histórico público do GitHub, forks ou caches. Se identificadores anteriores tiverem valor confidencial, avalie com a organização uma estratégia apropriada antes de promover o repositório no LinkedIn. Não reescreva a história do Git com `push --force` sem planejamento e alinhamento dos colaboradores.

## Instalação — Git Bash, na branch de desenvolvimento

Faça backup ou registre alterações locais antes de aplicar o patch.

```bash
git branch --show-current
git status --short
# Esperado: feature/igmi-0.3.3, árvore limpa
unzip -o IGMI_0.3.3_PATCH_SOMENTE_ALTERACOES.zip

source .venv/Scripts/activate
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
python -m pytest -q tests_igmi
python run.py simular demo demo-preview
python run.py test
```

As chamadas acima não usam a API de IA paga. O pipeline demo recria `warehouse/demo.duckdb` de forma local, usando exclusivamente dados sintéticos; não execute essa recriação sobre um banco real nem sobre arquivos que deseje preservar.

## Atenção: remover as capturas antigas antes de publicar

O ZIP não remove arquivos existentes, e screenshots anteriores podem exibir identificadores legados **dentro dos pixels**, mesmo quando o código foi alterado. **Não renomeie as imagens antigas:** gere capturas novas a partir do dashboard atualizado.

Após regenerar o dashboard e confirmar que o Chromium/Chrome está disponível:

```bash
# Retira do repositório as capturas antigas, sem afetar o código do dashboard
git rm -f -- docs/img/demo_*.png

# Recria imagens com a nomenclatura atual (não consome API)
python tools/capturar_prints_demo.py

# Confirme visualmente os nomes das duas linhas e os gráficos
git add docs/img
```

Se não tiver Chrome/Chromium, mantenha as capturas antigas removidas e deixe a documentação sem imagens até conseguir refazê-las. Não envie prints desatualizados ao LinkedIn. O README nesta versão não incorpora capturas antigas.

## Testes de aceitação

```bash
python run.py igmi --linha LR-01 --formato markdown --saida export/igmi_LR-01.md
python run.py igmi --linha LR-02 --formato markdown --saida export/igmi_LR-02.md
python run.py igmi-chat --linha LR-01
# Experimente: Qual equipamento mais parou?
# Dentro do chat: /linha LR-02
# Depois: /resumo e /sair
```

O Copiloto foi preservado com perguntas multilinha (`/pergunta` … `/fim`), exportação Markdown e confirmação literal `AUTORIZAR` antes de qualquer chamada paga. Não é necessário ativar a API para validar a migração.

Confira também as referências antigas no texto e nos nomes de arquivos; esta busca não detecta texto incorporado em pixels de imagens:

```bash
git grep -n -E 'L[T]3|L[T]56' -- ':!docs/img/**'
git ls-files | grep -E 'L[T]3|L[T]56'
git diff --check
```

A ausência de resultados nos dois primeiros comandos (após a limpeza das imagens) indica que os nomes antigos não estão mais presentes nos arquivos rastreados em texto ou nos caminhos rastreados. As imagens devem ser revisadas visualmente.

## Regressões conhecidas do ZIP-base

O ZIP da branch continha um CLI anterior à composição multilinha, além de uma fixture de teste multialvo ausente. O patch restaura o CLI com `/pergunta`, `/fim`, `/cancelar` e `AUTORIZAR`, atualiza a prévia de consultas compostas e recupera os testes correspondentes. Os componentes de cálculo permanecem independentes da IA.

## O que foi validado nesta entrega

- Regeneração determinística: **256 OS, 354 atividades e 105 paradas**, exatamente iguais aos CSVs sintéticos com novos prefixos.
- **99 testes IGMI e 7 subtestes** aprovados localmente sem serviços externos.
- Consulta explícita a dois alvos do mesmo prefixo técnico e seleção correta do equipamento pai.
- Chaves estrangeiras da hierarquia e dos planos preventivos verificadas nos seeds.

**Limitação:** a suíte completa do pipeline, incluindo os 18 checks principais e os 27 QD da demo, deve ser executada no Windows com DuckDB. Aqui não foi possível instalar o DuckDB por indisponibilidade da rede. Nenhum resultado dessa suíte foi presumido.

## Registrar a atualização

```bash
git add -A
git diff --cached --check
git status --short
git commit -m "refactor: IGMI 0.3.3 - nomes ficticios das linhas"
git push -u origin feature/igmi-0.3.3
```

Revisar o diff e a lista de imagens antes de criar o Pull Request. Nunca enviar `.env`, credenciais ou banco real ao GitHub.

## Reversão

Antes de commitar, `git restore .` recupera apenas arquivos **rastreados** modificados; arquivos novos devem ser revisados e removidos separadamente. Se já houver commit, prefira `git revert <hash-do-commit>` para manter o histórico, em vez de sobrescrever a `main`. Não execute `git clean -fd` indiscriminadamente.
