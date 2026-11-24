# IGMI 0.3.3.1 — Documentação e nomenclatura pública

Patch incremental sobre a 0.3.3, com a identidade pública **IGMI — Inteligência de Gestão da Manutenção Industrial** e as linhas sintéticas **LR-01** e **LR-02**.

## Conteúdo desta entrega

- README alinhado à versão atual: tabela de evolução até 0.3.3.1 e links para os guias que existem em `docs/` (`IGMI_0.2.0.md`, `IGMI_0.2.1.md`, `IGMI_0.3.0.md`, `IGMI_0.3.2.1.md`, `IGMI_0.3.3.md` e este arquivo).
- Capturas do dashboard de demonstração em [`docs/img/`](img/), com os identificadores `LR-01` e `LR-02`. Regeneração (Chrome headless, sem API): `python run.py simular demo demo-preview && python tools/capturar_prints_demo.py`.
- Aba de comparação do dashboard demo (`#linha`) no formato único `LR-01 × LR-02` na navegação, no título, nas colunas da tabela e nas legendas dos gráficos.
- Prévia estática (`python run.py preview`) e prints de terminal com o nome IGMI; warehouse padrão do pipeline principal em `warehouse/igmi.duckdb` (sobrescrevível por `PMB_WAREHOUSE`).
- Coluna `link` de `gold.fato_os` no contrato da gold, sem URL de fornecedor. O dashboard de prévia continua sem títulos, descrições ou links de OS.
- O analista determinístico (`python run.py igmi`) calcula indicadores em Python. A interpretação com modelo de linguagem permanece opcional no copiloto (`igmi-chat`) e em `igmi-ia`, com confirmação literal `AUTORIZAR` e no máximo uma chamada por turno, sobre o warehouse sintético local.

Os nomes de apresentação **Linha Robotizada_1** e **Linha Robotizada_2** continuam no cadastro sintético (`seeds/demo/`) e no subtítulo do dashboard. O pacote interno `pmb/` é preservado por compatibilidade.

## Validação

```bash
source .venv/Scripts/activate   # no Windows / Git Bash
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
python -m pytest -q tests_igmi
python run.py simular demo demo-preview
python run.py test
python run.py all
```

Essas chamadas não usam a API de IA paga. A suíte e o pipeline demo devem passar no mesmo ambiente da CI (Ubuntu e Windows, Python 3.11+).

## Reversão

Prefira `git revert` para manter o histórico, em vez de sobrescrever a `main`. Não envie `.env`, credenciais ou banco real ao GitHub.
