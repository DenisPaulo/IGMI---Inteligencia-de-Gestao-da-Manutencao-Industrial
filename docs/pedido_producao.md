# O que pedimos à produção: export de paradas

> **Tudo neste documento é FICTÍCIO.** Ids `SINT-…`, OS `ffff…`, datas e durações foram inventados para simular o export.
> **Nomes de colunas e formatos são provisórios** (contrato v2 proposto, `docs/contrato_parada_v2.md`). Valem os da sua amostra real.
> A simulação completa está em `dados_sinteticos/parada_v2/` e roda com `python run.py all && python run.py parada`.

## Formato que esperamos (exemplo fictício)

```csv
id_lancamento,os_ref,hora_inicio,duracao_min,acao
SINT-L0001,ffff0001,2026-10-01T08:10,60,incluir
SINT-L0002,ffff0005,2026-10-01T13:05,30,incluir
SINT-L0003,ffff0002,2026-10-01T11:00,45,incluir
SINT-L0005,ffff0001,2026-10-01T09:45,30,incluir
```

| Coluna (provisória) | O que é | Formato esperado |
|---|---|---|
| `id_lancamento` | número próprio do lançamento | texto; único em cada arquivo |
| `os_ref` | ID de 8 caracteres da OS no Mobility | 8 caracteres `0-9a-f` |
| `hora_inicio` | início da parada, hora local da fábrica | `AAAA-MM-DDTHH:MM` |
| `duracao_min` | duração da parada | minutos inteiros > 0 |
| `acao` | `incluir` ou `excluir` | só se o sistema tiver status/ação |

Duas paradas da mesma OS no mesmo dia vêm como **duas linhas com ids diferentes** (no exemplo, `SINT-L0001` e `SINT-L0005`). O pipeline guarda as duas e soma só na visão diária.

## Como cada cenário deve aparecer no arquivo

| Cenário | Como deve vir | O que o pipeline faz (simulado) |
|---|---|---|
| **Correção** | a mesma linha, **com o mesmo `id_lancamento`**, no próximo export, já com o valor certo. Ex.: `SINT-L0001,ffff0001,2026-10-01T08:10,50,incluir` | substitui a versão anterior (60 → 50 min); a anterior vai para a trilha de auditoria; se reduz, gera alerta para revisão |
| **Exclusão** | se existir status/ação: `SINT-L0004,,,,excluir`. Se não existir, nos digam como vocês excluem | tira o lançamento da conta e mantém o histórico; exclusão de um id que nunca recebemos vira alerta |
| **Export completo** | de vez em quando, um arquivo com **todos** os lançamentos vigentes, no mesmo formato | id que sumiu vira **candidato a exclusão** numa fila, para alguém confirmar; nunca é apagado sozinho |
| **Arquivo com erro** | — | o arquivo inteiro é rejeitado e nada é gravado (ex.: id vazio ou repetido, OS fora do padrão, data `01/10/2026`, duração `1.5`) |

## O pedido (6 itens)

1. Um **export de amostra anonimizado**, com algumas linhas, de preferência incluindo uma correção e uma exclusão.
2. Os **nomes exatos das colunas** como saem do sistema: número do lançamento, ID da OS, início e duração.
3. O **encoding** (UTF-8 ou Latin-1/Windows-1252) e o **separador** (vírgula ou ponto e vírgula).
4. O formato da **data/hora de início** (ex.: `dd/mm/aaaa hh:mm` ou `aaaa-mm-dd hh:mm`) e da **duração** (minutos inteiros, `hh:mm` ou decimal).
5. Se cada export é **incremental** (só o período novo) ou **completo**, e se é possível gerar um completo de vez em quando.
6. Como aparece um **lançamento excluído**: some do export, vem com status/ação, ou de outro jeito.
