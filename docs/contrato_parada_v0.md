# Contrato v0 — CSV de parada da produção

> Validação atual em `pmb/parada.py`. A proposta seguinte é a v2 (`docs/contrato_parada_v2.md`).

Status: **provisório** (13/10/2026). Nesta entrega só existem o contrato, a validação (`pmb/parada.py`) e o registro da partição.
A `gold.fato_os` segue com `hora_parada_min` **nula** e, portanto, sem custo diário até as 3 perguntas abaixo serem respondidas.
Schema legível por máquina: `contrato/parada_v0.schema.json`.

## Colunas

| Coluna | Tipo | Regra |
|---|---|---|
| `os_ref` | texto (lido com `all_varchar`) | obrigatória; `^[0-9a-f]{8}$`; `11112222` continua texto, nunca número |
| `hora_lancada` | texto → decimal(6,2), **horas decimais** | obrigatória; > 0; ponto como separador (ex.: `0.33`); `hh:mm` ou minutos são rejeitados |
| `data_parada` | data `AAAA-MM-DD`, opcional | só calendário; fora do join |
| `_arquivo`, `_linha`, `_sha256`, `_loaded_at`, `data_carga` | gerados | rastreio |

O cabeçalho tem de ser exatamente `os_ref,hora_lancada,data_parada`.

## Regra de carga (provisória)

- Cada arquivo é tratado como **acumulado** e **substitui** o anterior na silver.
- Cada arquivo é guardado numa partição datada **imutável** `landing_parada/data_carga=AAAA-MM-DD/`, **fora do repositório** (variável `PMB_LANDING_PARADA`; a pasta está no `.gitignore`). Partição existente não é reescrita.
- O mesmo `_sha256` lido de novo não faz nada (`SEM_MUDANCA`).
- Arquivo novo com menos OS ou menos horas que o anterior **bloqueia** (provável arquivo incremental).
- Se a resposta 3 for "incremental", a silver passa a unir as partições, com dedupe por `os_ref` + `_arquivo` + `_linha`.
- Join só pelo id da OS (`os_ref` = `tasks.task_short_id` **ou** `task_legacy_id`, conforme a pergunta 1). `os_ref` sem OS vai para fila, sem custo.

## Perguntas para a produção

1. Qual código da OS vocês lançam (o de 8 caracteres da OS no sistema de manutenção)? Ele vem sempre?
2. A hora vem em horas decimais, minutos ou hh:mm?
3. Cada arquivo traz tudo desde o início ou só o período novo? Correção vem como linha nova ou substitui a antiga?
