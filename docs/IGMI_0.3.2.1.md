# IGMI 0.3.2.1 — Estabilização das respostas e documentação

Patch incremental sobre **IGMI 0.3.2**. Trabalhe na branch `feature/igmi-0.3.2`, preservando a `main`. Não inclui warehouse, dados reais, credenciais ou dependências novas.

## Problema reproduzido

O teste com dados sintéticos da LR-01 enviou uma pergunta composta sobre ranking de paradas, reincidências, disponibilidade, MTTR e três ações práticas. A API foi chamada uma vez, mas a interpretação foi bloqueada: `Campo hipoteses fora do limite enxuto.` O relatório manteve os fatos, porém omitiu disponibilidade e repetiu o mesmo modo de reincidência em alertas distintos. O README principal também estava desatualizado.

## Correções

1. **Planejador:** `disponibilidade` marca a intenção de KPIs gerais, inclusive em perguntas combinadas com MTTR e reincidências. Usa valor calculado da GOLD, formatado em Python.
2. **Reincidências:** alertas do mesmo equipamento/modo/janela são exibidos em um grupo, preservando OS distintas. O agrupamento **não soma** contagens de janelas, que podem ser sobrepostas, e não apaga alertas reais.
3. **Validador:** somente perguntas multi-intenção no fluxo planejado podem ter até três hipóteses, mantendo as demais travas numéricas, terminológicas e estruturais. `igmi-ia` e os outros caminhos preservam o padrão anterior de duas hipóteses.
4. **Três ações explicitamente solicitadas:** a saída deve ter três recomendações; caso contrário, o sistema mantém os fatos e bloqueia a interpretação, sem nova chamada paga. Este controle verifica quantidade, não comprova adequação técnica de cada recomendação.
5. **README e changelog:** atualizado o estado real da plataforma, o fluxo Git Bash, os limites, os comandos offline/pagos e o roadmap.

**Segurança preservada:** DuckDB somente leitura; consultas autorizadas; 27 checks QD; nenhum SQL gerado pela IA, nenhuma edição de OS, nenhuma repetição automática paga e confirmação `AUTORIZAR` para usar a API. Os dados continuam 100% sintéticos.

## Como aplicar no Git Bash

Faça backup ou commit da versão anterior antes de sobrescrever arquivos. Com a branch correta e a árvore limpa:

```bash
git status --short
git branch --show-current
# copie o ZIP para a raiz, onde está run.py
unzip -o IGMI_0.3.2.1_PATCH_SOMENTE_ALTERACOES.zip
git diff --check
```

## Testes (sem API paga)

```bash
source .venv/Scripts/activate
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
python -m pytest -q tests_igmi
python run.py test
```

Confirme que todos os testes antigos continuam aprovados. Os novos testes cobrem disponibilidade, agrupamento sem somar ocorrências, aceitação de três hipóteses no modo planejado, bloqueio de uma quarta hipótese/valor inventado e exigência de três ações quando solicitadas. O teste `run.py test` **deve ser executado no Windows**; a suíte de integração não pôde ser validada no ambiente de preparação sem DuckDB.

## Validação manual offline e IA opcional

```bash
python run.py simular demo demo-preview
python run.py igmi-chat --linha LR-01
```

Pergunta factual offline de exemplo: `Como estão a disponibilidade e o MTTR da LR-01?` Deve exibir ambos os indicadores com zero tokens.

Teste pago **somente se houver saldo e autorização**:

```bash
python run.py igmi-chat --linha LR-01 --modelo "$IGMI_OPENAI_MODEL" \
  --autorizar-api --max-chamadas 1
```

No chat:

```text
/pergunta
Quero priorizar melhorias na confiabilidade da LR-01.
Quais equipamentos mais impactaram as horas de parada?
Quais reincidências merecem investigação prioritária?
Como estão o MTTR e a disponibilidade da linha?
Proponha três ações práticas, justificadas por evidências.
Separe fatos, hipóteses e recomendações.
/fim
```

Antes da API, o planejador deve apresentar ao menos `consultar_kpis`, `consultar_equipamentos` e `consultar_reincidencias`. Quando aparecer a confirmação, digite **`AUTORIZAR`** se desejar pagar por essa chamada. Os valores são calculados em Python; a interpretação pode ser bloqueada caso as regras continuem não atendidas. Sem repetição automática.

Exportação (antes de encerrar a sessão):

```text
/exportar export/igmi_chat_LR-01_0321.md
/sair
```

## Arquivos alterados no patch

- `igmi/__init__.py` — versão 0.3.2.1;
- `igmi/ia_economica.py` — limite de hipóteses configurável apenas para chamadores autorizados, padrão legado mantido;
- `igmi/copiloto.py` — instruções planejadas e verificação de três ações;
- `igmi/planejador.py` — intenção disponibilidade e agrupamento de alertas;
- `tests_igmi/test_planejador.py` — regressões offline;
- `README.md` e `CHANGELOG.md` — documentação;
- `docs/IGMI_0.3.2.1.md` — este guia.

## Reverter

**Antes do commit**, e somente se não houver alterações próprias nesses arquivos, restaure os arquivos versionados e remova o guia novo:

```bash
git restore -- README.md CHANGELOG.md igmi/__init__.py igmi/ia_economica.py \
  igmi/copiloto.py igmi/planejador.py tests_igmi/test_planejador.py
rm -i docs/IGMI_0.3.2.1.md
```

**Depois do commit**, prefira `git revert <hash_do_commit>` para preservar o histórico. Não use `git reset --hard` indiscriminadamente, nem `push --force`.

## Definição de pronto

Suíte local e de integração aprovadas, relatório LR-01 com disponibilidade, MTTR, ranking, reincidências sem repetição desnecessária, recomendações no número solicitado e consulta auditável. **Validação técnica por engenharia permanece obrigatória**, inclusive quando aparecer `IGMI [validada]`.
